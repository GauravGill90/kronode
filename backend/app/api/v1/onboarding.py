from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_org_id
from app.models.org import OnboardingConfig
from app.schemas.onboarding import (
    ConfluencePayload,
    ConfluenceTestPayload,
    ConfluenceTestResult,
    ConfluenceSpaceResult,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ── helpers ───────────────────────────────────────────────────────────────────


async def _get_onboarding_config(
    org_id: int, db: AsyncSession
) -> OnboardingConfig:
    """Return the OnboardingConfig row for the org, creating it if missing."""
    result = await db.execute(
        select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
    )
    config = result.scalar_one_or_none()
    if config is None:
        config = OnboardingConfig(org_id=org_id)
        db.add(config)
        await db.flush()
    return config


async def _get_valid_atlassian_token(
    config: OnboardingConfig,
) -> Optional[str]:
    """
    Placeholder for the Atlassian OAuth token refresh helper.
    The full token acquisition/refresh flow is a separate story.
    Returns the stored token or None if unavailable.
    """
    # In a full implementation this would:
    # 1. Check token expiry
    # 2. Refresh via Atlassian token endpoint if expired
    # 3. Persist the refreshed token
    # For now we read a token column if it exists on the model.
    # The Atlassian OAuth story will add `atlassian_access_token`.
    token: Optional[str] = getattr(config, "atlassian_access_token", None)
    return token


async def _fetch_space_info(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    space_key: str,
) -> Dict[str, Any]:
    """Fetch space metadata from Confluence Cloud API v2."""
    url = f"{base_url.rstrip('/')}/wiki/api/v2/spaces"
    resp = await client.get(
        url,
        params={"keys": space_key, "limit": 1},
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        timeout=10.0,
    )
    if resp.status_code == 401:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Atlassian token is invalid or expired. Please reconnect your Atlassian account.",
        )
    resp.raise_for_status()
    data = resp.json()
    results = data.get("results", [])
    if not results:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Space '{space_key}' not found in Confluence. Check the space key and try again.",
        )
    return results[0]


async def _fetch_page_count(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    space_id: str,
    include_labels: Optional[List[str]],
) -> int:
    """Return total page count for a space, optionally filtered by labels."""
    if include_labels:
        # Use CQL search to count pages with the given labels
        label_clauses = " OR ".join(
            [f'label = "{lbl}"' for lbl in include_labels]
        )
        cql = f"space.key in (\"{space_id}\") AND ({label_clauses}) AND type = page"
        url = f"{base_url.rstrip('/')}/wiki/rest/api/content/search"
        resp = await client.get(
            url,
            params={"cql": cql, "limit": 0},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json().get("totalSize", 0)
    else:
        url = f"{base_url.rstrip('/')}/wiki/api/v2/spaces/{space_id}/pages"
        resp = await client.get(
            url,
            params={"limit": 1},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        # Confluence v2 returns _links.next or meta.hasMore; total is in the meta block
        meta = data.get("_links", {})
        # Fall back to counting results list if total unavailable
        total = data.get("total", len(data.get("results", [])))
        return total


# ── GET /onboarding/config ────────────────────────────────────────────────────


class OnboardingConfigResponse(BaseModel):
    repo_url: Optional[str] = None
    repo_provider: Optional[str] = None
    jira_project_key: Optional[str] = None
    jira_workspace_url: Optional[str] = None
    jira_status_mappings: Optional[Dict[str, Any]] = None
    slack_channel_id: Optional[str] = None
    slack_channel_name: Optional[str] = None
    confluence_base_url: Optional[str] = None
    confluence_space_keys: Optional[List[str]] = None
    confluence_include_labels: Optional[List[str]] = None
    docs_provider: Optional[str] = None
    docs_scope: Optional[str] = None
    capabilities: Optional[Dict[str, Any]] = None
    guardrails: Optional[Dict[str, Any]] = None
    agent_name: Optional[str] = None
    agent_avatar: Optional[str] = None
    project_context: Optional[str] = None
    completed_at: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/config", response_model=OnboardingConfigResponse)
async def get_onboarding_config(
    org_id: int = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingConfigResponse:
    config = await _get_onboarding_config(org_id, db)
    await db.commit()
    return OnboardingConfigResponse.model_validate(config)


# ── POST /onboarding/confluence ───────────────────────────────────────────────


@router.post("/confluence", response_model=OnboardingConfigResponse)
async def save_confluence_config(
    payload: ConfluencePayload,
    org_id: int = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> OnboardingConfigResponse:
    config = await _get_onboarding_config(org_id, db)
    config.confluence_base_url = payload.base_url
    config.confluence_space_keys = payload.space_keys
    config.confluence_include_labels = payload.include_labels or []
    await db.commit()
    await db.refresh(config)
    return OnboardingConfigResponse.model_validate(config)


# ── POST /onboarding/test-confluence ─────────────────────────────────────────


@router.post("/test-confluence", response_model=ConfluenceTestResult)
async def test_confluence_connection(
    payload: ConfluenceTestPayload,
    org_id: int = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
) -> ConfluenceTestResult:
    config = await _get_onboarding_config(org_id, db)

    # 1. Retrieve a valid Atlassian token
    token = await _get_valid_atlassian_token(config)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "No Atlassian account connected. "
                "Please complete the Atlassian OAuth flow before testing Confluence."
            ),
        )

    space_results: List[ConfluenceSpaceResult] = []

    async with httpx.AsyncClient() as client:
        for key in payload.space_keys:
            # 2. Validate each space key exists
            space_data = await _fetch_space_info(
                client, payload.base_url, token, key
            )
            space_id = space_data["id"]
            space_name = space_data.get("name", key)

            # 3. Count pages (with optional label filter)
            page_count = await _fetch_page_count(
                client,
                payload.base_url,
                token,
                space_id,
                payload.include_labels,
            )

            space_results.append(
                ConfluenceSpaceResult(
                    key=key,
                    name=space_name,
                    page_count=page_count,
                )
            )

    return ConfluenceTestResult(connected=True, spaces=space_results)
