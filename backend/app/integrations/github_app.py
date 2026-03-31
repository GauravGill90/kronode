"""Kronode GitHub App — PR context comments + reviewer pattern learning.

When a PR is opened, Kronode posts a comment with:
- Relevant conventions for the changed files
- Missed companion files
- Reviewer guidance

Also subscribes to pull_request_review events to learn reviewer patterns.
"""
import hashlib
import hmac
import logging
import time

import httpx
import jwt

from app.core.config import settings

logger = logging.getLogger(__name__)


def _generate_jwt() -> str:
    """Generate a GitHub App JWT from the private key."""
    now = int(time.time())
    payload = {
        "iat": now - 60,
        "exp": now + (10 * 60),
        "iss": settings.github_app_id,
    }
    private_key = settings.github_app_private_key
    if not private_key:
        raise ValueError("GITHUB_APP_PRIVATE_KEY not set")
    return jwt.encode(payload, private_key, algorithm="RS256")


async def _get_installation_token(installation_id: int) -> str:
    """Exchange JWT for an installation access token (1-hour TTL)."""
    app_jwt = _generate_jwt()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.github.com/app/installations/{installation_id}/access_tokens",
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
            },
        )
        resp.raise_for_status()
        return resp.json()["token"]


def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature."""
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


async def handle_pull_request(payload: dict):
    """Handle pull_request.opened and pull_request.synchronize events."""
    action = payload.get("action")
    if action not in ("opened", "synchronize"):
        return

    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    installation = payload.get("installation", {})

    pr_number = pr.get("number")
    repo_full_name = repo.get("full_name", "")
    repo_url = f"https://github.com/{repo_full_name}"
    installation_id = installation.get("id")

    if not installation_id or not pr_number:
        return

    logger.info(f"[GitHubApp] PR #{pr_number} {action} on {repo_full_name}")

    # Get installation token
    try:
        token = await _get_installation_token(installation_id)
    except Exception as e:
        logger.error(f"[GitHubApp] Failed to get installation token: {e}")
        return

    # Get changed files
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            params={"per_page": 100},
        )
        if not resp.is_success:
            logger.warning(f"[GitHubApp] Failed to fetch PR files: {resp.status_code}")
            return
        files_changed = [f["filename"] for f in resp.json()]

    # Resolve org from repo URL
    org_id = await _resolve_org_from_repo(repo_url)
    if not org_id:
        logger.info(f"[GitHubApp] No org found for repo {repo_url} — skipping")
        return

    # Get context
    from app.mcp.server import configure, get_context, check_completeness

    configure(org_id=org_id)

    pr_title = pr.get("title", "")
    pr_body = pr.get("body", "") or ""
    task_description = f"{pr_title}\n{pr_body}"

    context = await get_context(task_description, files_touched=files_changed)
    completeness = await check_completeness(task_description, files_changed)

    # Build comment
    comment_parts = ["## 🧠 Kronode Context\n"]

    # Conventions
    conventions = context.get("conventions", [])
    if conventions:
        comment_parts.append("### Relevant Conventions\n")
        for c in conventions[:8]:
            rule = c.get("rule", c) if isinstance(c, dict) else str(c)
            comment_parts.append(f"- {rule[:200]}")
        comment_parts.append("")

    # Reviewer guidance
    reviewer_patterns = context.get("reviewer_patterns", [])
    if reviewer_patterns:
        comment_parts.append("### Reviewer Preferences\n")
        for rp in reviewer_patterns[:5]:
            reviewer = rp.get("reviewer", "")
            pref = rp.get("preference", "")
            comment_parts.append(f"- **{reviewer}**: {pref[:150]}")
        comment_parts.append("")

    # Missing files
    missing = completeness.get("missing", [])
    if missing:
        comment_parts.append("### ⚠️ Possibly Missing Files\n")
        for m in missing[:5]:
            comment_parts.append(f"- `{m['file']}` — {m['reason']}")
        comment_parts.append("")

    # Doc chunks
    doc_chunks = context.get("doc_chunks", [])
    if doc_chunks:
        comment_parts.append("### Related Documentation\n")
        for d in doc_chunks[:3]:
            heading = d.get("heading", "")
            truncated = "..." if d.get("full_available") else ""
            comment_parts.append(f"- **{heading}**{truncated}")
        comment_parts.append("")

    if len(comment_parts) <= 1:
        return  # Nothing useful to post

    comment_parts.append("\n---\n*Posted by [Kronode](https://kronode.dev) — organizational memory for AI coding tools*")
    comment_body = "\n".join(comment_parts)

    # Post comment
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
            json={"body": comment_body},
        )
        if resp.is_success:
            logger.info(f"[GitHubApp] Posted context comment on PR #{pr_number}")
        else:
            logger.warning(f"[GitHubApp] Failed to post comment: {resp.status_code}")


async def handle_pull_request_review(payload: dict):
    """Handle pull_request_review events to learn reviewer patterns."""
    review = payload.get("review", {})
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    reviewer = review.get("user", {}).get("login", "")
    state = review.get("state", "")  # approved, changes_requested, commented
    body = review.get("body", "") or ""
    repo_url = f"https://github.com/{repo.get('full_name', '')}"

    if state not in ("approved", "changes_requested"):
        return

    org_id = await _resolve_org_from_repo(repo_url)
    if not org_id:
        return

    # Store as memory record for reviewer pattern learning
    from app.core.database import AsyncSessionLocal
    from app.models.memory import MemoryRecord

    async with AsyncSessionLocal() as db:
        record = MemoryRecord(
            org_id=org_id,
            record_type="pattern",
            content={
                "reviewer": reviewer,
                "state": state,
                "changes_requested": [body] if state == "changes_requested" and body else [],
                "pr_url": pr.get("html_url", ""),
                "files_changed": [f.get("filename", "") for f in pr.get("files", [])[:20]],
            },
            source="github_app_webhook",
        )
        db.add(record)
        await db.commit()
        logger.info(f"[GitHubApp] Recorded {state} from {reviewer}")


async def _resolve_org_from_repo(repo_url: str) -> int | None:
    """Find org_id from repo URL."""
    from app.core.database import AsyncSessionLocal
    from app.models.org import OnboardingConfig
    from sqlalchemy import select

    repo_url_lower = repo_url.lower().rstrip("/")

    async with AsyncSessionLocal() as db:
        configs = (await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.repo_url.isnot(None))
        )).scalars().all()

        for cfg in configs:
            if cfg.repo_url and cfg.repo_url.lower().rstrip("/") == repo_url_lower:
                return cfg.org_id

    return None
