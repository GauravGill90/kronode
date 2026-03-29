import asyncio
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, and_ as sa_and

from app.core.database import AsyncSessionLocal
from app.models.task import Task, TaskEvent
from app.models.org import OnboardingConfig
from app.models.user import User  # noqa: F401 — registers 'users' table in SA metadata so FK resolution works in worker


AGENT_CHAIN = [
    "ticket_interpreter",   # parse raw ticket into structured task
    "context_builder",
    "clarification_agent",
    "planner_agent",
    "plan_approval_agent",  # post plan for human approval, pause pipeline
    "guardrails_agent",     # runs after planner so it can check files_affected
    "coder_agent",
    "tester_agent",
    "execution_verifier",
    "reviewer_agent",
    "memory_agent",
]


async def emit_event(
    task_id: uuid.UUID,
    agent_name: str,
    event_type: str,
    message: str,
    payload: dict | None = None,
):
    async with AsyncSessionLocal() as db:
        event = TaskEvent(
            task_id=task_id,
            agent_name=agent_name,
            event_type=event_type,
            message=message,
            payload=payload,
        )
        db.add(event)
        await db.commit()


async def run_pipeline(task_id_str: str):
    task_id = uuid.UUID(task_id_str)

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Task).where(Task.id == task_id))
        task = result.scalar_one_or_none()
        if not task:
            return

        result = await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.org_id == task.org_id)
        )
        config = result.scalar_one_or_none()

        task.status = "running"
        await db.commit()

    context = {
        "task_id": task_id_str,
        "description": task.description,
        "jira_ticket_id": task.jira_ticket_id,
        "org_id": task.org_id,
        "project_context": config.project_context if config else "",
        "repo_url": config.repo_url if config else "",
        "fork_repo_url": config.fork_repo_url if config else None,
        "github_access_token": config.github_access_token if config else None,
        "guardrails": config.guardrails if config else {},
        "capabilities": config.capabilities if config else {},
        "agent_name": config.agent_name if config else "Agent",
        # Jira
        "jira_workspace_url": config.jira_workspace_url if config else None,
        "jira_project_key": config.jira_project_key if config else None,
        "jira_email": config.jira_email if config else None,
        "jira_api_token": config.jira_api_token if config else None,
        # Slack
        "slack_channel_id": config.slack_channel_id if config else None,
        "slack_bot_token": config.slack_bot_token if config else None,
    }

    # Load composable skills and inject into context
    from app.skills.composer import compose_skills
    async with AsyncSessionLocal() as db:
        skill_set = await compose_skills(task.org_id, db)
    context["agent_profile"] = ", ".join(skill_set.skill_names) or "none"
    context["profile_injection"] = skill_set.system_prompt
    context["profile_priority_extensions"] = skill_set.context_priorities
    context["allowed_dirs"] = list(skill_set.allowed_dirs)
    context["allowed_extensions"] = list(skill_set.allowed_extensions)

    # Org coding standards (injected between profile and agent system prompt)
    context["coding_standards"] = (config.coding_standards or "") if config else ""

    # Check for cached conventions in memory_records (< 7 days old) to skip Haiku extraction
    cached_conventions = None
    try:
        from app.models.memory import MemoryRecord
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(MemoryRecord)
                .where(sa_and(
                    MemoryRecord.org_id == task.org_id,
                    MemoryRecord.record_type == "convention",
                ))
                .order_by(MemoryRecord.id.desc())
                .limit(1)
            )
            rec = result.scalar_one_or_none()
            if rec:
                age = datetime.now(timezone.utc) - rec.created_at.replace(tzinfo=timezone.utc)
                if age < timedelta(days=7):
                    cached_conventions = rec.content.get("conventions") if rec.content else None
    except Exception:
        pass  # memory_records table may not exist yet — safe to skip
    context["cached_conventions"] = cached_conventions

    # If the task came from a Jira ticket, enrich the description with the full ticket body
    if (
        context.get("jira_ticket_id")
        and context.get("jira_workspace_url")
        and context.get("jira_email")
        and context.get("jira_api_token")
    ):
        try:
            from app.services.jira_service import fetch_ticket_detail
            ticket = await fetch_ticket_detail(
                workspace_url=context["jira_workspace_url"],
                email=context["jira_email"],
                api_token=context["jira_api_token"],
                ticket_id=context["jira_ticket_id"],
            )
            if ticket:
                summary = ticket["summary"]
                body = ticket["description"].strip()
                context["jira_ticket"] = ticket
                # Build a rich description the agents can use
                context["description"] = (
                    f"[{context['jira_ticket_id']}] {summary}"
                    + (f"\n\n{body}" if body else "")
                )
                await emit_event(
                    task_id, "pipeline", "started",
                    f"Loaded Jira ticket {context['jira_ticket_id']}: {summary}",
                    {"ticket_url": ticket["url"]},
                )
        except Exception as exc:
            import logging as _logging
            _logging.getLogger(__name__).warning(f"[Pipeline] Failed to fetch Jira ticket detail: {exc}")

    try:
        from app.core.config import settings as _settings

        if _settings.bypass_llm:
            # Skip all LLM agents — go straight to coder which will use its hardcoded bypass payload
            await emit_event(task_id, "pipeline", "started", "BYPASS_LLM mode: skipping router/context/planner, running coder only")
            routing = {"complexity": "bypass", "agents": ["coder_agent"]}
            context["routing"] = routing
            context["planner_agent"] = {
                "subtasks": [{"order": 1, "description": context["description"], "agent": "coder_agent", "files_affected": []}],
                "definition_of_done": ["PR opened successfully"],
                "risk_flags": [],
                "estimated_files": 1,
            }
        else:
            # Step 1: Route the task
            from app.agents.router_agent import RouterAgent
            router = RouterAgent()
            await emit_event(task_id, "router", "started", "Analysing task and selecting agents...")
            routing = await router.run(context)
            context["routing"] = routing

            # Simple fast-path: skip context builder and planner for trivial tasks
            if routing["complexity"] == "simple":
                routing["agents"] = ["coder_agent", "memory_agent"]
                await emit_event(
                    task_id, "router", "completed",
                    "Simple task — fast path: skipping context builder and planner.", routing,
                )
            else:
                await emit_event(
                    task_id, "router", "completed",
                    f"Task classified as {routing['complexity']}. Running {len(routing['agents'])} agents.", routing,
                )

        # Run the selected agent chain
        MAX_REVISIONS = 2
        revision_count = 0
        agent_map = _build_agent_map()
        skip_flags = _get_skip_flags()
        agent_list = list(routing["agents"])
        i = 0
        while i < len(agent_list):
            agent_name = agent_list[i]
            if agent_name not in agent_map:
                i += 1
                continue
            if skip_flags.get(agent_name):
                await emit_event(task_id, agent_name, "completed", f"{agent_name} skipped (disabled in config).")
                i += 1
                continue

            # Cancellation check — user may have cancelled between agents
            async with AsyncSessionLocal() as db:
                current = await db.get(Task, task_id)
                if current and current.status == "cancelled":
                    await emit_event(task_id, "pipeline", "failed", "Task cancelled by user")
                    return

            agent_cls = agent_map[agent_name]
            agent = agent_cls()

            await emit_event(task_id, agent_name, "started", f"{agent.display_name} starting...")
            result = await agent.run(context)
            context[agent_name] = result

            if result.get("blocked"):
                await emit_event(task_id, agent_name, "failed", result.get("reason", "Blocked"))
                async with AsyncSessionLocal() as db:
                    task_obj = await db.get(Task, task_id)
                    task_obj.status = "paused"
                    task_obj.error = result.get("reason")
                    await db.commit()
                return

            if result.get("waiting"):
                async with AsyncSessionLocal() as db:
                    task_obj = await db.get(Task, task_id)
                    task_obj.status = "waiting_clarification"
                    task_obj.result = {
                        "context_snapshot": context,
                        "thread_ts": result["thread_ts"],
                        "slack_channel_id": result.get("slack_channel_id"),
                        "questions": result.get("questions", []),
                        "resume_from": "planner_agent",
                    }
                    await db.commit()
                await emit_event(
                    task_id, agent_name, "waiting",
                    "Waiting for Slack clarification...",
                    {"questions": result.get("questions", [])},
                )
                return

            await emit_event(task_id, agent_name, "completed", result.get("summary", f"{agent.display_name} complete."), result)

            # Reviewer → Coder retry loop
            if agent_name == "reviewer_agent" and result.get("needs_revision") and revision_count < MAX_REVISIONS:
                revision_count += 1
                changes = result.get("changes_requested", [])
                await emit_event(
                    task_id, "pipeline", "progress",
                    f"Reviewer requested changes (revision {revision_count}/{MAX_REVISIONS}): {'; '.join(changes[:3])}",
                    {"revision": revision_count, "changes_requested": changes},
                )
                # Inject review feedback into context for the coder
                context["review_feedback"] = {
                    "changes_requested": changes,
                    "verdict": result.get("verdict", ""),
                    "revision_number": revision_count,
                }
                # Jump back to coder_agent
                coder_idx = agent_list.index("coder_agent") if "coder_agent" in agent_list else None
                if coder_idx is not None:
                    i = coder_idx
                    continue

            i += 1

        # Determine final status
        coder_result = context.get("coder_agent", {})
        reviewer_result = context.get("reviewer_agent", {})
        has_pr = bool(coder_result.get("pr_url"))
        coder_failed = bool(coder_result.get("error")) or not coder_result.get("files_changed")
        reviewer_rejected = reviewer_result.get("approved") is False

        if has_pr:
            final_status = "in_review"
        elif coder_failed or reviewer_rejected:
            final_status = "failed"
        else:
            final_status = "done"

        # Notify integrations (Slack + Jira) — non-blocking, errors don't fail pipeline
        if final_status != "failed":
            await _notify_integrations(task_id, task.description, task.jira_ticket_id, context)

        async with AsyncSessionLocal() as db:
            task_obj = await db.get(Task, task_id)
            task_obj.status = final_status
            task_obj.result = coder_result
            if final_status == "failed":
                task_obj.error = coder_result.get("error") or "Coder failed to produce changes after all retries"
            if final_status in ("done", "failed"):
                task_obj.completed_at = datetime.now(timezone.utc)
            await db.commit()

    except Exception as exc:
        await emit_event(task_id, "pipeline", "failed", str(exc))
        async with AsyncSessionLocal() as db:
            task_obj = await db.get(Task, task_id)
            task_obj.status = "failed"
            task_obj.error = str(exc)
            await db.commit()
        raise


async def _notify_integrations(
    task_id: uuid.UUID,
    description: str,
    jira_ticket_id: str | None,
    context: dict,
) -> None:
    """
    Fire-and-forget notifications to Slack and Jira after a successful pipeline run.
    Errors are logged but never raise — they must not fail the pipeline.
    """
    coder_result = context.get("coder_agent", {})
    pr_url = coder_result.get("pr_url")
    branch = coder_result.get("branch_name", "N/A")
    agent_name = context.get("agent_name", "Agent")

    # ── Slack ──────────────────────────────────────────────────────────────────
    slack_token = context.get("slack_bot_token")
    slack_channel = context.get("slack_channel_id")
    if slack_token and slack_channel:
        try:
            from app.services.slack_service import post_notification
            pr_line = f" — <{pr_url}|View PR>" if pr_url else ""
            message = f"✅ *{agent_name}* finished: _{description[:120]}_{pr_line}"
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message},
                },
                {
                    "type": "context",
                    "elements": [{"type": "mrkdwn", "text": f"Branch: `{branch}`  •  Task: `{task_id}`"}],
                },
            ]
            await post_notification(channel_id=slack_channel, message=message, bot_token=slack_token, blocks=blocks)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Slack notification failed: {exc}")

    # ── Jira ───────────────────────────────────────────────────────────────────
    jira_workspace = context.get("jira_workspace_url")
    jira_email = context.get("jira_email")
    jira_token = context.get("jira_api_token")
    if jira_workspace and jira_email and jira_token and jira_ticket_id:
        try:
            from app.services.jira_service import update_ticket_status
            await update_ticket_status(
                workspace_url=jira_workspace,
                email=jira_email,
                api_token=jira_token,
                ticket_id=jira_ticket_id,
                status="In Review",
                pr_url=pr_url,
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning(f"Jira update failed: {exc}")


async def resume_pipeline(task_id_str: str, clarification_answer: str) -> None:
    """Resume a pipeline that was paused at waiting_clarification or waiting_approval."""
    task_id = uuid.UUID(task_id_str)

    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task or task.status != "waiting_clarification":
            return

        snapshot = task.result or {}
        context = snapshot.get("context_snapshot", {})
        resume_from = snapshot.get("resume_from", "planner_agent")

        task.status = "running"
        task.result = None
        await db.commit()

    context["clarification_answer"] = clarification_answer

    await emit_event(
        task_id, "clarification_agent", "completed",
        f"Clarification received — resuming from {resume_from}.",
        {"answer": clarification_answer[:200]},
    )

    try:
        agent_map = _build_agent_map()
        start_idx = AGENT_CHAIN.index(resume_from) if resume_from in AGENT_CHAIN else 0
        agents_to_run = AGENT_CHAIN[start_idx:]

        routing = context.get("routing", {})
        selected_agents = routing.get("agents", AGENT_CHAIN)

        skip_flags = _get_skip_flags()
        for agent_name in agents_to_run:
            if agent_name not in selected_agents:
                continue
            if agent_name not in agent_map:
                continue
            if skip_flags.get(agent_name):
                await emit_event(task_id, agent_name, "completed", f"{agent_name} skipped (disabled in config).")
                continue

            async with AsyncSessionLocal() as db:
                current = await db.get(Task, task_id)
                if current and current.status == "cancelled":
                    await emit_event(task_id, "pipeline", "failed", "Task cancelled by user")
                    return

            agent_cls = agent_map[agent_name]
            agent = agent_cls()

            await emit_event(task_id, agent_name, "started", f"{agent.display_name} starting...")
            result = await agent.run(context)
            context[agent_name] = result

            if result.get("blocked"):
                await emit_event(task_id, agent_name, "failed", result.get("reason", "Blocked"))
                async with AsyncSessionLocal() as db:
                    task_obj = await db.get(Task, task_id)
                    task_obj.status = "paused"
                    task_obj.error = result.get("reason")
                    await db.commit()
                return

            await emit_event(task_id, agent_name, "completed", result.get("summary", f"{agent.display_name} complete."), result)

        task_desc = context.get("description", "")
        jira_ticket_id = context.get("jira_ticket_id")
        await _notify_integrations(task_id, task_desc, jira_ticket_id, context)

        coder_result = context.get("coder_agent", {})
        has_pr = bool(coder_result.get("pr_url"))
        async with AsyncSessionLocal() as db:
            from datetime import datetime, timezone
            task_obj = await db.get(Task, task_id)
            task_obj.status = "in_review" if has_pr else "done"
            task_obj.result = coder_result
            if not has_pr:
                task_obj.completed_at = datetime.now(timezone.utc)
            await db.commit()

    except Exception as exc:
        await emit_event(task_id, "pipeline", "failed", str(exc))
        async with AsyncSessionLocal() as db:
            task_obj = await db.get(Task, task_id)
            task_obj.status = "failed"
            task_obj.error = str(exc)
            await db.commit()
        raise


def _build_agent_map() -> dict:
    from app.agents.ticket_interpreter import TicketInterpreterAgent
    from app.agents.context_builder import ContextBuilderAgent
    from app.agents.guardrails_agent import GuardrailsAgent
    from app.agents.clarification_agent import ClarificationAgent
    from app.agents.planner_agent import PlannerAgent
    from app.agents.plan_approval_agent import PlanApprovalAgent
    from app.agents.coder_agent import CoderAgent
    from app.agents.tester_agent import TesterAgent
    from app.agents.execution_verifier import ExecutionVerifierAgent
    from app.agents.reviewer_agent import ReviewerAgent
    from app.agents.memory_agent import MemoryAgent

    return {
        "ticket_interpreter": TicketInterpreterAgent,
        "context_builder": ContextBuilderAgent,
        "guardrails_agent": GuardrailsAgent,
        "clarification_agent": ClarificationAgent,
        "planner_agent": PlannerAgent,
        "plan_approval_agent": PlanApprovalAgent,
        "coder_agent": CoderAgent,
        "tester_agent": TesterAgent,
        "execution_verifier": ExecutionVerifierAgent,
        "reviewer_agent": ReviewerAgent,
        "memory_agent": MemoryAgent,
    }


def _get_skip_flags() -> dict[str, bool]:
    """Map agent names to their skip flags from settings."""
    from app.core.config import settings as _s
    return {
        "ticket_interpreter": _s.skip_ticket_interpreter,
        "context_builder": _s.skip_context_builder,
        "clarification_agent": _s.skip_clarification,
        "planner_agent": _s.skip_planner,
        "plan_approval_agent": _s.skip_plan_posting,
        "guardrails_agent": _s.skip_guardrails,
        "coder_agent": _s.skip_coder,
        "tester_agent": _s.skip_tester,
        "execution_verifier": _s.skip_execution_verifier,
        "reviewer_agent": _s.skip_reviewer,
        "memory_agent": _s.skip_memory,
    }
