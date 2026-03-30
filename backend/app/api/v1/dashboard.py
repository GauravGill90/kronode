from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.org import Organization, OnboardingConfig
from app.models.task import Task
from app.models.user import User
from app.schemas.dashboard import DashboardOut, AgentConfig, IntegrationStatus, TaskSummary, PRStats

router = APIRouter()


@router.get("/dashboard", response_model=DashboardOut)
async def get_dashboard(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()

    if not user or not user.org_id:
        return DashboardOut(
            user_name=None,
            agent=None,
            integrations=IntegrationStatus(),
            recent_tasks=[],
            onboarding_complete=False,
        )

    result = await db.execute(select(OnboardingConfig).where(OnboardingConfig.org_id == user.org_id))
    config = result.scalar_one_or_none()

    result = await db.execute(
        select(Task)
        .where(Task.org_id == user.org_id)
        .order_by(desc(Task.created_at))
        .limit(10)
    )
    tasks = result.scalars().all()

    # Compute PR stats across all tasks for this org
    pr_stats = await _compute_pr_stats(db, user.org_id)

    agent = None
    integrations = IntegrationStatus()

    if config:
        if config.agent_name:
            agent = AgentConfig(
                agent_name=config.agent_name,
                agent_avatar=config.agent_avatar or "avatar-1",
                capabilities=config.capabilities,
                guardrails=config.guardrails,
            )
        integrations = IntegrationStatus(
            github=bool(config.repo_url and config.github_access_token),
            jira=bool(config.jira_project_key),
            slack=bool(config.slack_channel_id),
            docs=bool(config.docs_provider),
        )

    task_summaries = []
    for t in tasks:
        ts = TaskSummary.model_validate(t)
        # Enrich with PR data from result JSONB
        if t.result:
            ts.pr_url = t.result.get("pr_url") or t.pr_url
            ts.cost_usd = t.result.get("cost_usd")
            ts.num_turns = t.result.get("num_turns")
        elif t.pr_url:
            ts.pr_url = t.pr_url
        task_summaries.append(ts)

    return DashboardOut(
        user_name=user.name,
        agent=agent,
        integrations=integrations,
        recent_tasks=task_summaries,
        pr_stats=pr_stats,
        onboarding_complete=bool(config and config.completed_at),
    )


async def _compute_pr_stats(db: AsyncSession, org_id: int) -> PRStats:
    """Compute PR acceptance rate and cost stats for an org."""
    # Get all tasks that have a PR (either in result or pr_url field)
    result = await db.execute(
        select(Task.status, Task.result, Task.pr_url)
        .where(Task.org_id == org_id)
    )
    rows = result.all()

    merged = 0
    in_review = 0
    rejected = 0
    failed = 0
    total_cost = 0.0
    total_turns = 0
    cost_count = 0

    for status, task_result, pr_url in rows:
        has_pr = bool(pr_url or (task_result and task_result.get("pr_url")))
        if not has_pr:
            if status == "failed":
                failed += 1
            continue

        if status == "done":
            merged += 1
        elif status == "in_review":
            in_review += 1
        elif status == "failed":
            rejected += 1
        elif status == "cancelled":
            rejected += 1

        # Accumulate cost/turn stats
        if task_result:
            cost = task_result.get("cost_usd")
            turns = task_result.get("num_turns")
            if cost:
                total_cost += cost
                cost_count += 1
            if turns:
                total_turns += turns

    total_prs = merged + in_review + rejected
    decided = merged + rejected  # PRs with a final outcome

    return PRStats(
        total_prs=total_prs,
        merged=merged,
        in_review=in_review,
        rejected=rejected,
        failed=failed,
        acceptance_rate=round(merged / decided, 2) if decided > 0 else None,
        avg_cost_usd=round(total_cost / cost_count, 4) if cost_count > 0 else None,
        avg_turns=round(total_turns / cost_count, 1) if cost_count > 0 else None,
    )
