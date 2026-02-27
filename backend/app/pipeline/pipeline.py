import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.task import Task, TaskEvent
from app.models.org import OnboardingConfig


AGENT_CHAIN = [
    "context_builder",
    "guardrails_agent",
    "clarification_agent",
    "planner_agent",
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
        "guardrails": config.guardrails if config else {},
        "capabilities": config.capabilities if config else {},
        "agent_name": config.agent_name if config else "Agent",
    }

    try:
        # Step 1: Route the task
        from app.agents.router_agent import RouterAgent
        router = RouterAgent()
        await emit_event(task_id, "router", "started", "Analysing task and selecting agents...")
        routing = await router.run(context)
        context["routing"] = routing
        await emit_event(task_id, "router", "completed", f"Task classified as {routing['complexity']}. Running {len(routing['agents'])} agents.", routing)

        # Run the selected agent chain
        agent_map = _build_agent_map()
        for agent_name in routing["agents"]:
            if agent_name not in agent_map:
                continue

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

        # Mark done
        async with AsyncSessionLocal() as db:
            task_obj = await db.get(Task, task_id)
            task_obj.status = "done"
            task_obj.result = context.get("coder_agent")
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
    from app.agents.context_builder import ContextBuilderAgent
    from app.agents.guardrails_agent import GuardrailsAgent
    from app.agents.clarification_agent import ClarificationAgent
    from app.agents.planner_agent import PlannerAgent
    from app.agents.coder_agent import CoderAgent
    from app.agents.tester_agent import TesterAgent
    from app.agents.execution_verifier import ExecutionVerifierAgent
    from app.agents.reviewer_agent import ReviewerAgent
    from app.agents.memory_agent import MemoryAgent

    return {
        "context_builder": ContextBuilderAgent,
        "guardrails_agent": GuardrailsAgent,
        "clarification_agent": ClarificationAgent,
        "planner_agent": PlannerAgent,
        "coder_agent": CoderAgent,
        "tester_agent": TesterAgent,
        "execution_verifier": ExecutionVerifierAgent,
        "reviewer_agent": ReviewerAgent,
        "memory_agent": MemoryAgent,
    }
