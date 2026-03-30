from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.org import Organization, OnboardingConfig
from app.models.user import User
from app.schemas.onboarding import (
    AccountPayload, RepoPayload, JiraPayload, JiraTestPayload,
    SlackPayload, SlackTestPayload,
    DocsPayload, CapabilitiesPayload, GuardrailsPayload,
    AgentPayload, AgentProfilePayload, ContextPayload, GitHubTokenPayload, GitHubTokenTestPayload,
    OnboardingStatus, OnboardingConfigOut,
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
    config.fork_repo_url = payload.fork_repo_url
    config.repo_provider = payload.provider
    config.repo_name = payload.repo_name
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
    config.jira_email = payload.email
    # Only overwrite token if a new one was provided
    if payload.api_token:
        config.jira_api_token = payload.api_token
    config.jira_status_mappings = payload.status_mappings
    await db.commit()
    return {"ok": True}


@router.post("/test-jira")
async def test_jira(
    payload: JiraTestPayload,
    user_data: dict = Depends(get_current_user),
):
    """Validate Jira credentials and confirm the project key exists."""
    import httpx
    import base64

    creds = base64.b64encode(f"{payload.email}:{payload.api_token}".encode()).decode()
    headers = {
        "Authorization": f"Basic {creds}",
        "Accept": "application/json",
    }
    base = payload.workspace_url.rstrip("/")

    async with httpx.AsyncClient() as client:
        # 1. Verify credentials by fetching current user
        me_resp = await client.get(f"{base}/rest/api/3/myself", headers=headers)
        if me_resp.status_code == 401:
            return {"ok": False, "error": "Invalid email or API token"}
        if not me_resp.is_success:
            return {"ok": False, "error": f"Could not reach Jira at {base}"}

        display_name = me_resp.json().get("displayName", payload.email)

        # 2. Confirm the project key exists and is accessible
        proj_resp = await client.get(f"{base}/rest/api/3/project/{payload.project_key}", headers=headers)
        if proj_resp.status_code == 404:
            return {"ok": False, "error": f"Project '{payload.project_key}' not found — check the key (e.g. KR, ACME)"}
        if proj_resp.status_code == 403:
            return {"ok": False, "error": f"No access to project '{payload.project_key}'"}
        if not proj_resp.is_success:
            return {"ok": False, "error": "Could not verify project key"}

        project_name = proj_resp.json().get("name", payload.project_key)
        return {"ok": True, "user": display_name, "project": project_name}


@router.post("/slack")
async def save_slack(
    payload: SlackPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.slack_channel_id = payload.channel_id
    config.slack_channel_name = payload.channel_name
    # Only overwrite token if a new one was provided
    if payload.bot_token:
        config.slack_bot_token = payload.bot_token
    await db.commit()
    return {"ok": True}


@router.post("/test-slack")
async def test_slack(
    payload: SlackTestPayload,
    user_data: dict = Depends(get_current_user),
):
    """Validate a Slack bot token and confirm it can see the given channel."""
    import httpx
    headers = {"Authorization": f"Bearer {payload.bot_token}"}

    async with httpx.AsyncClient() as client:
        # 1. Validate the token itself
        auth_resp = await client.post("https://slack.com/api/auth.test", headers=headers)
        auth_data = auth_resp.json()
        if not auth_data.get("ok"):
            return {"ok": False, "error": auth_data.get("error", "Invalid bot token")}

        # 2. Try to resolve the channel name — skip if channels:read scope is missing
        channel = payload.channel_name.lstrip("#")
        list_resp = await client.get(
            "https://slack.com/api/conversations.list",
            headers=headers,
            params={"exclude_archived": "true", "limit": 200},
        )
        list_data = list_resp.json()

        if list_data.get("ok"):
            # channels:read is available — verify the channel actually exists
            channels = list_data.get("channels", [])
            match = next((c for c in channels if c["name"] == channel), None)
            if not match:
                return {"ok": False, "error": f"Channel #{channel} not found — invite the bot first: /invite @{auth_data.get('user', 'YourApp')}"}

        # 3. Send a test message to confirm chat:write works
        msg_resp = await client.post(
            "https://slack.com/api/chat.postMessage",
            headers={**headers, "Content-Type": "application/json"},
            json={
                "channel": f"#{channel}",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                ":white_check_mark: *Kronode connected successfully!*\n"
                                "Your agent will post progress updates here after each task run — "
                                "PR links, status changes, and summaries."
                            ),
                        },
                    }
                ],
                "text": "✅ Kronode connected successfully!",
            },
        )
        msg_data = msg_resp.json()
        if not msg_data.get("ok"):
            err = msg_data.get("error", "unknown")
            if err == "not_in_channel":
                return {"ok": False, "error": f"Bot is not in #{channel} — run /invite @{auth_data.get('user', 'YourApp')} in Slack"}
            if err == "channel_not_found":
                return {"ok": False, "error": f"Channel #{channel} not found — check the name and that the bot is invited"}
            return {"ok": False, "error": f"Could not post to #{channel}: {err}"}

        return {"ok": True, "workspace": auth_data.get("team"), "bot": auth_data.get("user")}


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


@router.post("/agent-profile")
async def save_agent_profile(
    payload: AgentProfilePayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, _, config = await _get_or_create_org(user_data, db)
    config.agent_profile = payload.profile_key
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
    config.coding_standards = payload.coding_standards or None
    await db.commit()
    return {"ok": True}


@router.post("/github-token")
async def save_github_token(
    payload: GitHubTokenPayload,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _, org, config = await _get_or_create_org(user_data, db)
    config.github_access_token = payload.token
    await db.commit()

    # Trigger self-onboarding if repo is also configured
    if config.repo_url and payload.token:
        try:
            from app.pipeline.task_queue import run_self_onboarding
            run_self_onboarding.delay(org.id)
        except Exception:
            pass  # non-critical — onboarding can run later

    return {"ok": True}


@router.post("/ingest-docs")
async def trigger_doc_ingestion(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger doc ingestion (markdown files from connected repo)."""
    _, org, config = await _get_or_create_org(user_data, db)
    if not config.repo_url or not config.github_access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No repo or GitHub token configured")
    from app.pipeline.task_queue import run_doc_ingestion
    doc_source = "bitbucket" if config.repo_provider == "bitbucket" else "git"
    run_doc_ingestion.delay(org.id, doc_source)
    return {"ok": True, "message": f"Doc ingestion queued for org {org.id}"}


@router.post("/refresh-all")
async def refresh_all_ingestion(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Refresh everything: self-onboarding (stack detection + PR patterns), convention extraction, and doc ingestion."""
    _, org, config = await _get_or_create_org(user_data, db)
    if not config.repo_url or not config.github_access_token:
        raise HTTPException(status_code=400, detail="No repo or GitHub token configured")

    queued = []
    from app.pipeline.task_queue import run_self_onboarding, run_convention_extraction, run_doc_ingestion
    run_self_onboarding.delay(org.id)
    queued.append("self-onboarding")
    run_convention_extraction.delay(org.id, 200)
    queued.append("convention extraction (200 PRs)")
    doc_source = "bitbucket" if config.repo_provider == "bitbucket" else "git"
    run_doc_ingestion.delay(org.id, doc_source)
    queued.append("doc ingestion")

    return {"ok": True, "queued": queued, "message": f"Queued {len(queued)} jobs for org {org.id}"}


@router.get("/ingestion-status")
async def get_ingestion_status(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check how much data has been ingested for this org."""
    from sqlalchemy import func
    from app.models.doc_chunk import DocChunk
    from app.models.convention import Convention
    from app.models.memory import MemoryRecord

    _, org, config = await _get_or_create_org(user_data, db)
    oid = org.id

    doc_count = (await db.execute(select(func.count()).select_from(DocChunk).where(DocChunk.org_id == oid))).scalar() or 0
    conv_count = (await db.execute(select(func.count()).select_from(Convention).where(Convention.org_id == oid))).scalar() or 0
    pattern_count = (await db.execute(select(func.count()).select_from(MemoryRecord).where(MemoryRecord.org_id == oid, MemoryRecord.record_type == "pattern"))).scalar() or 0

    return {
        "org_id": oid,
        "doc_chunks": doc_count,
        "conventions": conv_count,
        "reviewer_patterns": pattern_count,
        "repo_url": config.repo_url,
    }


@router.post("/test-github-token")
async def test_github_token(
    payload: GitHubTokenTestPayload,
    user_data: dict = Depends(get_current_user),
):
    """Validate a GitHub PAT and confirm it has access to the given repo."""
    import httpx
    import re

    headers = {
        "Authorization": f"Bearer {payload.token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient() as client:
        # 1. Validate token — get the authenticated user
        user_resp = await client.get("https://api.github.com/user", headers=headers)
        if user_resp.status_code == 401:
            return {"ok": False, "error": "Invalid token — make sure it starts with ghp_ and hasn't expired"}
        if not user_resp.is_success:
            return {"ok": False, "error": "Could not reach GitHub API"}
        login = user_resp.json().get("login", "")

        # 2. Extract owner/repo from URL and verify access
        match = re.search(r"github\.com[/:]([^/]+)/([^/\.]+)", payload.repo_url)
        if not match:
            return {"ok": False, "error": "Could not parse repo URL — expected https://github.com/owner/repo"}
        owner, repo = match.group(1), match.group(2)

        repo_resp = await client.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers)
        if repo_resp.status_code == 404:
            return {"ok": False, "error": f"Repo {owner}/{repo} not found — check the URL and that the token has 'repo' scope"}
        if repo_resp.status_code == 403:
            return {"ok": False, "error": "Token doesn't have access to this repo — add 'repo' scope"}
        if not repo_resp.is_success:
            return {"ok": False, "error": "Could not verify repo access"}

        return {"ok": True, "login": login, "repo": f"{owner}/{repo}"}


@router.post("/test-bitbucket-token")
async def test_bitbucket_token(
    payload: GitHubTokenTestPayload,
    user_data: dict = Depends(get_current_user),
):
    """Validate a Bitbucket API token and confirm it has access to the given repo."""
    import httpx

    from app.services.bitbucket_service import _auth_headers, _parse_repo

    headers = _auth_headers(payload.token)

    try:
        workspace, repo_slug = _parse_repo(payload.repo_url)
    except Exception:
        return {"ok": False, "error": "Could not parse repo URL — expected https://bitbucket.org/workspace/repo"}

    async with httpx.AsyncClient(timeout=15) as client:
        # Verify repo access (workspace tokens can't call /2.0/user, so skip user check)
        repo_resp = await client.get(
            f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}",
            headers=headers,
        )
        if repo_resp.status_code == 401:
            return {"ok": False, "error": "Invalid token — check that it hasn't expired"}
        if repo_resp.status_code == 404:
            return {"ok": False, "error": f"Repo {workspace}/{repo_slug} not found — check the URL and token permissions"}
        if repo_resp.status_code == 403:
            return {"ok": False, "error": "Token doesn't have access to this repo — check Repositories: Read permission"}
        if not repo_resp.is_success:
            return {"ok": False, "error": "Could not verify repo access"}

        repo_data = repo_resp.json()
        owner = repo_data.get("owner", {}).get("display_name", workspace)
        return {"ok": True, "login": owner, "repo": f"{workspace}/{repo_slug}"}


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


@router.get("/config", response_model=OnboardingConfigOut)
async def get_config(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the full onboarding config so the frontend can hydrate its store."""
    user, org, config = await _get_or_create_org(user_data, db)
    return OnboardingConfigOut(
        agent_name=config.agent_name,
        agent_avatar=config.agent_avatar,
        agent_profile=config.agent_profile,
        repo_url=config.repo_url,
        fork_repo_url=config.fork_repo_url,
        repo_provider=config.repo_provider,
        repo_name=config.repo_name,
        has_github_token=bool(config.github_access_token),
        capabilities=config.capabilities,
        guardrails=config.guardrails,
        project_context=config.project_context,
        coding_standards=config.coding_standards,
        user_name=user.name,
        user_role=user.role,
        company_name=org.name if org.name != "My Organization" else None,
        jira_workspace_url=config.jira_workspace_url,
        jira_project_key=config.jira_project_key,
        jira_email=config.jira_email,
        has_jira_token=bool(config.jira_api_token),
        slack_channel_id=config.slack_channel_id,
        slack_channel_name=config.slack_channel_name,
        has_slack_token=bool(config.slack_bot_token),
    )
