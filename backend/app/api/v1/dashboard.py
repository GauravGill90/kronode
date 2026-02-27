from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.org import Organization, OnboardingConfig
from app.models.task import Task
from app.models.user import User
from app.schemas.dashboard import DashboardOut, AgentConfig, IntegrationStatus, TaskSummary

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

    return DashboardOut(
        agent=agent,
        integrations=integrations,
        recent_tasks=[TaskSummary.model_validate(t) for t in tasks],
        onboarding_complete=bool(config and config.completed_at),
    )
