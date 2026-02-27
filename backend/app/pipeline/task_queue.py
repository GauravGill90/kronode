import asyncio

from app.celery_app import celery_app


@celery_app.task(name="run_pipeline", bind=True, max_retries=0)
def run_pipeline(self, task_id: str):
    from app.pipeline.pipeline import run_pipeline as _run_pipeline
    asyncio.run(_run_pipeline(task_id))


@celery_app.task(name="run_resume_pipeline")
def run_resume_pipeline(task_id: str, clarification_answer: str):
    from app.pipeline.pipeline import resume_pipeline
    asyncio.run(resume_pipeline(task_id, clarification_answer))


@celery_app.task(name="poll_pr_outcomes")
def poll_pr_outcomes():
    asyncio.run(_poll_pr_outcomes())


@celery_app.task(name="run_pr_revision")
def run_pr_revision(task_id: str):
    asyncio.run(_run_pr_revision(task_id))


async def _poll_pr_outcomes():
    import logging
    from sqlalchemy import select, and_ as sa_and, text

    from app.core.database import AsyncSessionLocal
    from app.models.memory import MemoryRecord
    from app.models.org import OnboardingConfig
    from app.models.task import Task

    logger = logging.getLogger(__name__)
    logger.info("[PollPR] Starting PR outcome poll")

    # Find in_review tasks with a pr_url but no merged pr_outcome record yet.
    # Tasks stay in_review until the PR merges — only then do they become done.
    # LEFT JOIN excludes rows where merged=true already exists — still polls open PRs.
    async with AsyncSessionLocal() as db:
        stmt = (
            select(Task.id, Task.org_id, Task.jira_ticket_id, Task.result)
            .where(
                sa_and(
                    Task.status == "in_review",
                    Task.result.isnot(None),
                    text("result->>'pr_url' IS NOT NULL"),
                )
            )
            .outerjoin(
                MemoryRecord,
                sa_and(
                    MemoryRecord.task_id == Task.id,
                    MemoryRecord.record_type == "pr_outcome",
                    text("(memory_records.content->>'merged')::boolean = true"),
                ),
            )
            .where(MemoryRecord.id.is_(None))  # no merged pr_outcome exists yet
            .limit(50)
        )
        rows = (await db.execute(stmt)).all()

    logger.info(f"[PollPR] {len(rows)} open PR(s) to check")

    for task_id, org_id, jira_ticket_id, result in rows:
        pr_url = (result or {}).get("pr_url")
        if not pr_url:
            continue

        # Load org config for tokens
        try:
            async with AsyncSessionLocal() as db:
                cfg = (await db.execute(
                    select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
                )).scalar_one_or_none()
            if not cfg or not cfg.github_access_token:
                continue
        except Exception as exc:
            logger.warning(f"[PollPR] Config load failed for org {org_id}: {exc}")
            continue

        # Check PR status via GitHub API
        try:
            from app.services.github_service import get_pr_status
            status = await get_pr_status(pr_url, cfg.github_access_token)
        except Exception as exc:
            logger.warning(f"[PollPR] get_pr_status failed for {pr_url}: {exc}")
            continue

        # ── Handle merged ──────────────────────────────────────────────────────
        if status["merged"]:
            try:
                from datetime import datetime, timezone as _tz
                async with AsyncSessionLocal() as db:
                    existing = (await db.execute(
                        select(MemoryRecord).where(
                            sa_and(
                                MemoryRecord.task_id == task_id,
                                MemoryRecord.record_type == "pr_outcome",
                            )
                        )
                    )).scalar_one_or_none()
                    if existing:
                        existing.content = {**existing.content, "merged": True}
                    else:
                        db.add(MemoryRecord(
                            org_id=org_id,
                            task_id=task_id,
                            record_type="pr_outcome",
                            content={"pr_url": pr_url, "merged": True},
                            source=pr_url,
                        ))

                    # Task is truly done — PR merged
                    task_obj = await db.get(Task, task_id)
                    if task_obj and task_obj.status == "in_review":
                        task_obj.status = "done"
                        task_obj.completed_at = datetime.now(_tz.utc)

                    await db.commit()
                    logger.info(f"[PollPR] pr_outcome merged=True, task {task_id} → done")

                # Emit a terminal event so the task stream closes cleanly
                from app.pipeline.pipeline import emit_event
                import uuid as _uuid
                await emit_event(
                    _uuid.UUID(str(task_id)), "pipeline", "completed",
                    f"PR merged — task complete. {pr_url}",
                    {"pr_url": pr_url},
                )
            except Exception as exc:
                logger.warning(f"[PollPR] pr_outcome update failed for task {task_id}: {exc}")

            # Transition Jira to Done
            if (jira_ticket_id and cfg.jira_workspace_url
                    and cfg.jira_email and cfg.jira_api_token):
                try:
                    from app.services.jira_service import update_ticket_status
                    await update_ticket_status(
                        workspace_url=cfg.jira_workspace_url,
                        email=cfg.jira_email,
                        api_token=cfg.jira_api_token,
                        ticket_id=jira_ticket_id,
                        status="Done",
                        pr_url=pr_url,
                    )
                    logger.info(f"[PollPR] {jira_ticket_id} → Done")
                except Exception as exc:
                    logger.warning(f"[PollPR] Jira Done failed for {jira_ticket_id}: {exc}")

        # ── Handle changes requested ───────────────────────────────────────────
        if status["changes_requested"] and (status["review_comments"] or status.get("inline_comments")):
            try:
                async with AsyncSessionLocal() as db:
                    existing = (await db.execute(
                        select(MemoryRecord).where(
                            sa_and(
                                MemoryRecord.task_id == task_id,
                                MemoryRecord.record_type == "pitfall",
                            )
                        )
                    )).scalar_one_or_none()
                    if not existing:
                        db.add(MemoryRecord(
                            org_id=org_id,
                            task_id=task_id,
                            record_type="pitfall",
                            content={
                                "review_comments": status["review_comments"],
                                "inline_comments": status.get("inline_comments", []),
                            },
                            source=pr_url,
                        ))
                        await db.commit()
                        logger.info(
                            f"[PollPR] Wrote pitfall record for task {task_id} "
                            f"({len(status['review_comments'])} review + "
                            f"{len(status.get('inline_comments', []))} inline comment(s))"
                        )

                        # Notify Slack — only on first detection (same gate as pitfall write)
                        if cfg.slack_bot_token and cfg.slack_channel_id:
                            try:
                                from app.services.slack_service import post_notification
                                agent_name = cfg.agent_name or "Kronode"
                                comment_lines: list[str] = []
                                for c in status["review_comments"]:
                                    comment_lines.append(f"• {c}")
                                for ic in status.get("inline_comments", []):
                                    path = ic.get("path", "")
                                    body = ic.get("body", "")
                                    comment_lines.append(f"• `{path}`: {body}")
                                comments_block = "\n".join(comment_lines[:10])  # cap at 10
                                if len(comment_lines) > 10:
                                    comments_block += f"\n_…and {len(comment_lines) - 10} more_"
                                blocks = [
                                    {
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": (
                                                f":red_circle: *{agent_name}'s PR needs changes* — "
                                                f"a reviewer requested revisions.\n<{pr_url}|View PR>"
                                            ),
                                        },
                                    },
                                    {
                                        "type": "section",
                                        "text": {"type": "mrkdwn", "text": comments_block or "_No comment body provided._"},
                                    },
                                    {
                                        "type": "context",
                                        "elements": [{"type": "mrkdwn", "text": f"Task: `{task_id}`"}],
                                    },
                                ]
                                await post_notification(
                                    channel_id=cfg.slack_channel_id,
                                    message=f"{agent_name}'s PR needs changes: {pr_url}",
                                    bot_token=cfg.slack_bot_token,
                                    blocks=blocks,
                                )
                                logger.info(f"[PollPR] Slack 'changes requested' notification sent for task {task_id}")
                            except Exception as slack_exc:
                                logger.warning(f"[PollPR] Slack changes-requested notify failed: {slack_exc}")

                        # Queue revision agent to address the comments
                        try:
                            run_pr_revision.delay(str(task_id))
                            logger.info(f"[PollPR] Queued run_pr_revision for task {task_id}")
                        except Exception as queue_exc:
                            logger.warning(f"[PollPR] Failed to queue run_pr_revision: {queue_exc}")
            except Exception as exc:
                logger.warning(f"[PollPR] pitfall write failed for task {task_id}: {exc}")

    logger.info("[PollPR] Poll complete")


async def _run_pr_revision(task_id_str: str):
    import logging
    import uuid
    from sqlalchemy import select, and_ as sa_and

    from app.core.database import AsyncSessionLocal
    from app.models.memory import MemoryRecord
    from app.models.org import OnboardingConfig
    from app.models.task import Task
    from app.pipeline.pipeline import emit_event

    logger = logging.getLogger(__name__)
    task_id = uuid.UUID(task_id_str)
    logger.info(f"[PRRevision] Starting revision for task {task_id}")

    async with AsyncSessionLocal() as db:
        task = await db.get(Task, task_id)
        if not task:
            logger.warning(f"[PRRevision] Task {task_id} not found")
            return

        cfg = (await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.org_id == task.org_id)
        )).scalar_one_or_none()

        pitfall = (await db.execute(
            select(MemoryRecord).where(
                sa_and(
                    MemoryRecord.task_id == task_id,
                    MemoryRecord.record_type == "pitfall",
                )
            )
        )).scalar_one_or_none()

    if not cfg or not pitfall:
        logger.warning(f"[PRRevision] Missing config or pitfall record for task {task_id}")
        return

    coder_result = task.result or {}
    branch_name = coder_result.get("branch_name")
    pr_url = coder_result.get("pr_url")
    original_files = coder_result.get("files", [])

    if not branch_name or not cfg.repo_url or not cfg.github_access_token:
        logger.warning(f"[PRRevision] Missing branch/repo/token for task {task_id}")
        return

    review_comments = pitfall.content.get("review_comments", [])
    inline_comments = pitfall.content.get("inline_comments", [])

    from app.profiles import get_profile
    profile_key = cfg.agent_profile or "fullstack"
    profile = get_profile(profile_key)

    context = {
        "task_id": task_id_str,
        "description": task.description,
        "org_id": task.org_id,
        "repo_url": cfg.repo_url,
        "github_access_token": cfg.github_access_token,
        "slack_channel_id": cfg.slack_channel_id,
        "slack_bot_token": cfg.slack_bot_token,
        "agent_name": cfg.agent_name or "Kronode",
        "branch_name": branch_name,
        "pr_url": pr_url,
        "review_comments": review_comments,
        "inline_comments": inline_comments,
        "original_files": original_files,
        "profile_injection": profile.SYSTEM_PROMPT_INJECTION,
        "coding_standards": cfg.coding_standards or "",
    }

    from app.agents.pr_revision_agent import PRRevisionAgent
    agent = PRRevisionAgent()

    await emit_event(task_id, "pr_revision_agent", "started", "Reviewing PR comments...")
    result = await agent.run(context)

    if result.get("needs_clarification"):
        await emit_event(
            task_id, "pr_revision_agent", "waiting",
            result.get("summary", "Clarification needed for PR comments."),
            {"questions": result.get("questions", [])},
        )
        return

    files = result.get("files", [])
    if not files:
        await emit_event(task_id, "pr_revision_agent", "completed",
                         result.get("summary", "No file changes needed."))
        return

    # Commit revised files to the existing branch — PR updates automatically
    try:
        from app.services.github_service import add_files_to_branch
        commit_message = result.get("commit_message", "fix: address PR review comments")
        ok = await add_files_to_branch(
            repo_url=cfg.repo_url,
            branch_name=branch_name,
            files=files,
            commit_message=commit_message,
            token=cfg.github_access_token,
        )
        if ok:
            await emit_event(
                task_id, "pr_revision_agent", "completed",
                f"Pushed {len(files)} revised file(s) to `{branch_name}` — PR updated.",
                {"files_changed": [f["path"] for f in files], "pr_url": pr_url},
            )
            logger.info(f"[PRRevision] {len(files)} file(s) pushed to {branch_name} for task {task_id}")
        else:
            await emit_event(task_id, "pr_revision_agent", "failed",
                             "GitHub push failed — check logs.")
    except Exception as exc:
        logger.warning(f"[PRRevision] Push failed for task {task_id}: {exc}")
        await emit_event(task_id, "pr_revision_agent", "failed", f"Push failed: {exc}")


@celery_app.task(name="poll_clarifications")
def poll_clarifications():
    asyncio.run(_poll_clarifications())


async def _poll_clarifications():
    import logging
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.org import OnboardingConfig
    from app.models.task import Task
    from app.services.slack_service import get_thread_replies

    logger = logging.getLogger(__name__)
    logger.info("[PollClarification] Starting clarification poll")

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(Task).where(Task.status == "waiting_clarification").limit(20)
        )).scalars().all()

    logger.info(f"[PollClarification] {len(rows)} task(s) waiting for clarification")

    for task in rows:
        snapshot = (task.result or {})
        thread_ts = snapshot.get("thread_ts")
        context_snap = snapshot.get("context_snapshot", {})

        if not thread_ts:
            logger.warning(f"[PollClarification] Task {task.id} has no thread_ts — skipping")
            continue

        # Prefer the real channel ID stored at post time (C0XXXXXXX) over the name in config
        slack_channel = snapshot.get("slack_channel_id") or context_snap.get("slack_channel_id")
        slack_token = context_snap.get("slack_bot_token")

        if not slack_channel or not slack_token:
            logger.warning(f"[PollClarification] Task {task.id} has no Slack creds — skipping")
            continue

        # Check for timeout (24h with no reply)
        age = datetime.now(timezone.utc) - task.created_at.replace(tzinfo=timezone.utc)
        if age > timedelta(hours=24):
            logger.info(f"[PollClarification] Task {task.id} timed out — queuing resume without clarification")
            try:
                run_resume_pipeline.delay(str(task.id), "")
            except Exception as exc:
                logger.warning(f"[PollClarification] Timeout resume queue failed for {task.id}: {exc}")
            continue

        # Poll Slack thread for replies
        try:
            replies = await get_thread_replies(
                channel_id=slack_channel,
                thread_ts=thread_ts,
                bot_token=slack_token,
            )
        except Exception as exc:
            logger.warning(f"[PollClarification] get_thread_replies failed for {task.id}: {exc}")
            continue

        if not replies:
            logger.info(f"[PollClarification] No reply yet for task {task.id}")
            continue

        answer = "\n".join(replies)
        logger.info(f"[PollClarification] Got reply for task {task.id}: {answer[:80]}")
        try:
            run_resume_pipeline.delay(str(task.id), answer)
            logger.info(f"[PollClarification] Queued resume for task {task.id}")
        except Exception as exc:
            logger.warning(f"[PollClarification] Failed to queue resume for {task.id}: {exc}")

    logger.info("[PollClarification] Poll complete")
