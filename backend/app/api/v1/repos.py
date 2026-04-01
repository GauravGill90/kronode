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


class DocIndexRequest(BaseModel):
    provider: str  # confluence / notion / gdrive
    source_url: str  # Confluence space URL, Notion workspace, GDrive folder
    token: str  # email:api_token for Confluence, integration token for Notion, etc.


@router.post("/docs/index")
async def index_doc_source(
    payload: DocIndexRequest,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Index page titles from a doc source (Confluence, Notion, GDrive) without ingesting content.

    Pages are fetched on demand when get_doc is called.
    """
    org_id = await _get_org_id(user_data, db)

    from app.services.doc_providers import get_provider
    from app.models.doc_index import DocIndex

    provider = get_provider(payload.provider)
    pages = await provider.fetch_index(payload.source_url, payload.token)

    if not pages:
        return {"ok": False, "error": "No pages found. Check the URL and token."}

    # Upsert index entries
    existing = (await db.execute(
        select(DocIndex).where(DocIndex.org_id == org_id, DocIndex.source_type == payload.provider)
    )).scalars().all()
    existing_refs = {e.source_ref for e in existing}

    new_count = 0
    for page in pages:
        if page["source_ref"] not in existing_refs:
            db.add(DocIndex(
                org_id=org_id,
                source_type=payload.provider,
                source_ref=page["source_ref"],
                source_url=page.get("source_url", ""),
                title=page["title"],
                last_modified=page.get("last_modified", ""),
                author=page.get("author", ""),
            ))
            new_count += 1

    await db.commit()

    return {
        "ok": True,
        "indexed": len(pages),
        "new": new_count,
        "pages": [
            {"title": p["title"], "source_ref": p["source_ref"], "last_modified": p.get("last_modified", "")}
            for p in pages
        ],
    }


@router.get("/docs/index")
async def list_doc_index(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all indexed doc pages for the org."""
    org_id = await _get_org_id(user_data, db)

    from app.models.doc_index import DocIndex

    entries = (await db.execute(
        select(DocIndex).where(DocIndex.org_id == org_id).order_by(DocIndex.title)
    )).scalars().all()

    return {
        "total": len(entries),
        "ingested": sum(1 for e in entries if e.ingested),
        "pages": [
            {
                "id": e.id,
                "source_type": e.source_type,
                "source_ref": e.source_ref,
                "title": e.title,
                "source_url": e.source_url,
                "last_modified": e.last_modified,
                "ingested": e.ingested,
                "ingested_at": e.ingested_at.isoformat() if e.ingested_at else None,
            }
            for e in entries
        ],
    }


@router.post("/issues/index")
async def index_issues(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Index recent issues from the connected repo's issue tracker.

    Fetches issue titles, labels, state, and body preview. No LLM calls.
    Issues are matched by title in get_context for relevant context.
    """
    org_id = await _get_org_id(user_data, db)

    config = (await db.execute(
        select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
    )).scalar_one_or_none()

    if not config or not config.repo_url or not config.github_access_token:
        raise HTTPException(status_code=400, detail="No repo configured")

    import httpx
    from app.models.issue_index import IssueIndex

    # Detect provider
    repo_url = config.repo_url
    token = config.github_access_token
    provider = config.repo_provider or "github"

    issues_fetched = []

    if provider == "github":
        # Fetch recent issues (open + recently closed)
        repo_url_clean = repo_url.rstrip("/")
        if repo_url_clean.endswith(".git"):
            repo_url_clean = repo_url_clean[:-4]
        parts = repo_url_clean.split("/")
        owner, repo = parts[-2], parts[-1]

        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

        async with httpx.AsyncClient(timeout=30) as client:
            for state in ["open", "closed"]:
                page = 1
                while len(issues_fetched) < 500:
                    resp = await client.get(
                        f"https://api.github.com/repos/{owner}/{repo}/issues",
                        headers=headers,
                        params={
                            "state": state,
                            "per_page": 100,
                            "page": page,
                            "sort": "updated",
                            "direction": "desc",
                        },
                    )
                    if not resp.is_success:
                        break
                    items = resp.json()
                    if not items:
                        break
                    for item in items:
                        if "pull_request" in item:
                            continue  # skip PRs
                        issues_fetched.append({
                            "issue_ref": str(item["number"]),
                            "title": item.get("title", ""),
                            "state": item.get("state", ""),
                            "labels": [l["name"] for l in item.get("labels", [])],
                            "author": item.get("user", {}).get("login", ""),
                            "url": item.get("html_url", ""),
                            "body_preview": (item.get("body") or "")[:500],
                            "created_at_source": item.get("created_at", ""),
                        })
                    page += 1
                    if len(items) < 100:
                        break

    elif provider == "bitbucket":
        # Bitbucket issues
        workspace, repo_slug = repo_url.rstrip("/").split("/")[-2:]
        headers = {"Authorization": f"Bearer {token}"} if ":" not in token else {
            "Authorization": f"Basic {__import__('base64').b64encode(token.encode()).decode()}"
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}/issues",
                headers=headers,
                params={"pagelen": 50, "sort": "-updated_on"},
            )
            if resp.is_success:
                for item in resp.json().get("values", []):
                    issues_fetched.append({
                        "issue_ref": str(item.get("id", "")),
                        "title": item.get("title", ""),
                        "state": item.get("state", ""),
                        "labels": [],
                        "author": item.get("reporter", {}).get("display_name", ""),
                        "url": item.get("links", {}).get("html", {}).get("href", ""),
                        "body_preview": (item.get("content", {}).get("raw", "") or "")[:500],
                        "created_at_source": item.get("created_on", ""),
                    })

    if not issues_fetched:
        return {"ok": True, "indexed": 0, "message": "No issues found"}

    # Upsert into issue_index
    existing = (await db.execute(
        select(IssueIndex).where(IssueIndex.org_id == org_id, IssueIndex.source_type == f"{provider}_issues")
    )).scalars().all()
    existing_refs = {e.issue_ref for e in existing}

    new_count = 0
    for issue in issues_fetched:
        if issue["issue_ref"] not in existing_refs:
            db.add(IssueIndex(
                org_id=org_id,
                source_type=f"{provider}_issues",
                issue_ref=issue["issue_ref"],
                title=issue["title"],
                state=issue["state"],
                labels=issue["labels"],
                author=issue["author"],
                url=issue["url"],
                body_preview=issue["body_preview"],
                created_at_source=issue["created_at_source"],
            ))
            new_count += 1

    await db.commit()

    return {
        "ok": True,
        "indexed": len(issues_fetched),
        "new": new_count,
        "provider": provider,
    }


@router.get("/issues/index")
async def list_issue_index(
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List indexed issues for the org."""
    org_id = await _get_org_id(user_data, db)
    from app.models.issue_index import IssueIndex

    entries = (await db.execute(
        select(IssueIndex).where(IssueIndex.org_id == org_id).order_by(IssueIndex.id.desc()).limit(100)
    )).scalars().all()

    return {
        "total": len(entries),
        "issues": [
            {
                "issue_ref": e.issue_ref,
                "title": e.title,
                "state": e.state,
                "labels": e.labels,
                "url": e.url,
                "body_preview": e.body_preview[:100] if e.body_preview else "",
            }
            for e in entries
        ],
    }
