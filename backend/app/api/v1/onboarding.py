from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.org import Organization, OnboardingConfig
from app.models.user import User
from app.schemas.onboarding import (
    AccountPayload, RepoPayload, JiraPayload, SlackPayload,
    DocsPayload, CapabilitiesPayload, GuardrailsPayload,
    AgentPayload, ContextPayload, OnboardingStatus,
)

router = APIRouter()


async def _get_or_create_org(user_data: dict, db: AsyncSession) -> tuple[User, Organization, OnboardingConfig]:
    result = await db.execute(select(User).where(User.clerk_id == user_data["user_id"]))
    user = result.scalar_one_or_none()

    if not user:
        org = Organization(name="My Organization")
        db.add(org)
        await db.flush()
        user = User(clerk_id=user_data["user_id"], email="", org_id=org.id)
        db.add(user)
        config = OnboardingConfig(org_id=org.id)
        db.add(config)
        await db.commit()
        await db.refresh(user)
        await db.refresh(org)
        await db.refresh(config)
    else:
        result = await db.execute(select(Organization).where(Organization.id == user.org_id))
        org = result.scalar_one()
        result = await db.execute(select(OnboardingConfig).where(OnboardingConfig.org_id == org.id))
        config = result.scalar_one_or_none()
        if not config:
            config = OnboardingConfig(org_id=org.id)
            db.add(config)
            await db.commit()
            await db.refresh(config)

    return user, org, config


@router.post("/account")
async def save_account(
    payload: AccountPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, org, config = await _get_or_create_org(user_data, db)
    user.name = payload.name
    user.role = payload.role
    org.name = payload.company_name
    await db.commit()
    return {"ok": True}


@router.post("/repo")
async def save_repo(
    payload: RepoPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.repo_url = payload.repo_url
    config.repo_provider = payload.provider
    await db.commit()
    return {"ok": True}


@router.post("/jira")
async def save_jira(
    payload: JiraPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.jira_workspace_url = payload.workspace_url
    config.jira_project_key = payload.project_key
    config.jira_status_mappings = payload.status_mappings
    await db.commit()
    return {"ok": True}


@router.post("/slack")
async def save_slack(
    payload: SlackPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.slack_channel_id = payload.channel_id
    config.slack_channel_name = payload.channel_name
    await db.commit()
    return {"ok": True}


@router.post("/docs")
async def save_docs(
    payload: DocsPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.docs_provider = payload.provider
    config.docs_scope = payload.scope
    await db.commit()
    return {"ok": True}


@router.post("/capabilities")
async def save_capabilities(
    payload: CapabilitiesPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.capabilities = payload.model_dump()
    await db.commit()
    return {"ok": True}


@router.post("/guardrails")
async def save_guardrails(
    payload: GuardrailsPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.guardrails = payload.model_dump()
    await db.commit()
    return {"ok": True}


@router.post("/agent")
async def save_agent(
    payload: AgentPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.agent_name = payload.agent_name
    config.agent_avatar = payload.agent_avatar
    await db.commit()
    return {"ok": True}


@router.post("/context")
async def save_context(
    payload: ContextPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.project_context = payload.project_context
    await db.commit()
    return {"ok": True}


@router.post("/complete")
async def complete_onboarding(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    _, _, config = await _get_or_create_org(user_data, db)
    config.completed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"ok": True}


@router.get("/status", response_model=OnboardingStatus)
async def get_status(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    completed = config.completed_at is not None

    step = 0
    if config.repo_url:
        step = 2
    if config.jira_project_key:
        step = 3
    if config.slack_channel_id:
        step = 4
    if config.capabilities:
        step = 6
    if config.guardrails:
        step = 7
    if config.agent_name:
        step = 8
    if config.project_context:
        step = 9
    if completed:
        step = 12

    return OnboardingStatus(
        completed=completed,
        current_step=step,
        agent_name=config.agent_name,
    )
