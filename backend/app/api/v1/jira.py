from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.org import OnboardingConfig
from app.models.user import User

router = APIRouter()


async def _get_config(user_data: dict, db: AsyncSession) -> OnboardingConfig:
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()
    if not user or not user.org_id:
        raise HTTPException(status_code=400, detail="Onboarding not complete")
    result = await db.execute(select(OnboardingConfig).where(OnboardingConfig.org_id == user.org_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=400, detail="Onboarding not complete")
    return config


@router.get("/jira/tickets")
async def get_jira_tickets(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    config = await _get_config(user_data, db)

    if not (config.jira_workspace_url and config.jira_project_key and config.jira_email and config.jira_api_token):
        return {"tickets": [], "configured": False}

    from app.services.jira_service import fetch_project_tickets
    tickets = await fetch_project_tickets(
        workspace_url=config.jira_workspace_url,
        email=config.jira_email,
        api_token=config.jira_api_token,
        project_key=config.jira_project_key,
    )
    return {"tickets": tickets, "configured": True}
