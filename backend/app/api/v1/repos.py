"""Repository management — discover, list, toggle, ingest."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.org import OnboardingConfig
from app.models.repository import Repository

logger = logging.getLogger(__name__)

router = APIRouter()


class DiscoverRequest(BaseModel):
    provider: str = "github"  # github / bitbucket / gitlab
    org_name: str  # GitHub org / Bitbucket workspace / GitLab group


class RepoToggle(BaseModel):
    active: bool


async def _get_org_id(user_data: dict, db: AsyncSession) -> int:
    user = (await db.execute(
        select(User).where(User.clerk_id == user_data["user_id"])
    )).scalar_one_or_none()
    if not user or not user.org_id:
        raise HTTPException(status_code=400, detail="No organization found")
    return user.org_id


@router.post("/repos/discover")
async def discover_repos(
    payload: DiscoverRequest,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Discover all repos in a GitHub org / Bitbucket workspace / GitLab group."""
    org_id = await _get_org_id(user_data, db)

    # Get token from config
    config = (await db.execute(
        select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
    )).scalar_one_or_none()
    if not config or not config.github_access_token:
        raise HTTPException(status_code=400, detail="No git token configured. Add one in settings first.")

    # Save org name
    config.git_org_name = payload.org_name
    config.repo_provider = payload.provider

    # Discover repos
    from app.services.git_providers import get_git_provider
    git = get_git_provider(payload.provider)
    discovered = await git.list_org_repos(payload.org_name, config.github_access_token)

    # Sort by last activity (most recent first)
    discovered.sort(key=lambda r: r.get("pushed_at", ""), reverse=True)

    # Upsert into repositories table
    existing = (await db.execute(
        select(Repository).where(Repository.org_id == org_id)
    )).scalars().all()
    existing_urls = {r.repo_url for r in existing}

    new_count = 0
    for i, repo in enumerate(discovered):
        if repo["repo_url"] not in existing_urls:
            # Auto-activate top 5 by activity, rest inactive
            db.add(Repository(
                org_id=org_id,
                repo_url=repo["repo_url"],
                repo_provider=payload.provider,
                repo_name=repo["repo_name"],
                default_branch=repo.get("default_branch", "main"),
                active=i < 5,
            ))
            new_count += 1

    await db.commit()

    # Return full list with metadata from discovery
    all_repos = (await db.execute(
        select(Repository).where(Repository.org_id == org_id).order_by(Repository.repo_name)
    )).scalars().all()

    # Build metadata lookup from discovered repos
    meta_by_url = {r["repo_url"]: r for r in discovered}

    return {
        "discovered": len(discovered),
        "new": new_count,
        "total": len(all_repos),
        "repos": [
            {
                "id": r.id,
                "repo_url": r.repo_url,
                "repo_name": r.repo_name,
                "repo_provider": r.repo_provider,
                "default_branch": r.default_branch,
                "active": r.active,
                "last_ingested_at": r.last_ingested_at.isoformat() if r.last_ingested_at else None,
                "language": meta_by_url.get(r.repo_url, {}).get("language", ""),
                "pushed_at": meta_by_url.get(r.repo_url, {}).get("pushed_at", ""),
                "description": meta_by_url.get(r.repo_url, {}).get("description", ""),
            }
            for r in all_repos
        ],
    }


@router.get("/repos")
async def list_repos(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all repos for the current org."""
    org_id = await _get_org_id(user_data, db)

    repos = (await db.execute(
        select(Repository).where(Repository.org_id == org_id).order_by(Repository.repo_name)
    )).scalars().all()

    return {
        "repos": [
            {
                "id": r.id,
                "repo_url": r.repo_url,
                "repo_name": r.repo_name,
                "repo_provider": r.repo_provider,
                "default_branch": r.default_branch,
                "active": r.active,
                "last_ingested_at": r.last_ingested_at.isoformat() if r.last_ingested_at else None,
            }
            for r in repos
        ],
    }


@router.patch("/repos/{repo_id}")
async def toggle_repo(
    repo_id: int,
    payload: RepoToggle,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Toggle a repo active/inactive."""
    org_id = await _get_org_id(user_data, db)

    repo = (await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.org_id == org_id)
    )).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo.active = payload.active
    await db.commit()
    return {"ok": True, "repo_name": repo.repo_name, "active": repo.active}


@router.post("/repos/{repo_id}/ingest")
async def ingest_repo(
    repo_id: int,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Trigger convention extraction + doc ingestion for a specific repo."""
    org_id = await _get_org_id(user_data, db)

    repo = (await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.org_id == org_id)
    )).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")

    from app.pipeline.task_queue import run_convention_extraction, run_doc_ingestion
    run_convention_extraction.delay(org_id, 200)

    doc_source = repo.repo_provider if repo.repo_provider in ("bitbucket", "gitlab") else "git"
    run_doc_ingestion.delay(org_id, doc_source)

    return {"ok": True, "repo_name": repo.repo_name, "queued": ["convention_extraction", "doc_ingestion"]}
