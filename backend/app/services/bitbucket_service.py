"""Bitbucket Cloud REST API service.

Mirrors github_service.py — implements the same interface (get_repo_tree,
get_file_content, create_pull_request, add_files_to_branch, get_pr_status,
fetch_merged_prs) but against the Bitbucket Cloud API v2.

Authentication: Bearer token (OAuth access token) passed as the `token`
argument.  For App Passwords, callers should supply the value in the form
``username:app_password``; the helper functions detect this and switch to
HTTP Basic auth automatically.
"""
import base64
import logging

import httpx

logger = logging.getLogger(__name__)

BITBUCKET_API = "https://api.bitbucket.org/2.0"


def _auth_headers(token: str) -> dict[str, str]:
    """Return auth headers for the Bitbucket API.

    If *token* contains a colon it is treated as ``username:app_password``
    (Basic auth); otherwise it is used as an OAuth Bearer token.
    """
    if ":" in token:
        encoded = base64.b64encode(token.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}
    return {"Authorization": f"Bearer {token}"}


def _parse_repo(repo_url: str) -> tuple[str, str]:
    """Extract (workspace, repo_slug) from a Bitbucket URL."""
    repo_url = repo_url.rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    parts = repo_url.split("/")
    return parts[-2], parts[-1]


def _parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Parse https://bitbucket.org/{workspace}/{repo}/pull-requests/{id}."""
    url = pr_url.rstrip("/")
    parts = url.split("/")
    # Expected: ['https:', '', 'bitbucket.org', workspace, repo, 'pull-requests', id]
    if len(parts) < 7 or parts[5] != "pull-requests":
        raise ValueError(f"Cannot parse Bitbucket PR URL: {pr_url!r}")
    return parts[3], parts[4], int(parts[6])


# ---------------------------------------------------------------------------
# File-tree helpers
# ---------------------------------------------------------------------------

_DOC_EXTENSIONS = {".md", ".mdx"}
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", "coverage", ".turbo", ".changeset",
}
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".wav", ".ogg",
    ".lock", ".sum",
    ".min.js", ".min.css",
}


def _should_skip(path: str) -> bool:
    parts = path.split("/")
    if any(p in _SKIP_DIRS for p in parts[:-1]):
        return True
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _SKIP_EXTENSIONS)


async def _list_all_files(
    client: httpx.AsyncClient,
    workspace: str,
    repo_slug: str,
    commit: str,
    token: str,
    path: str = "",
) -> list[dict]:
    """Recursively list all files under *path* in a Bitbucket repo."""
    base = f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src/{commit}"
    url = f"{base}/{path}" if path else base
    headers = _auth_headers(token)
    files: list[dict] = []

    while url:
        resp = await client.get(url, headers=headers, params={"pagelen": 100})
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("values", []):
            item_type = item.get("type")
            item_path = item.get("path", "")
            if item_type == "commit_file":
                files.append(item)
            elif item_type == "commit_directory":
                sub = await _list_all_files(
                    client, workspace, repo_slug, commit, token, path=item_path
                )
                files.extend(sub)
        url = data.get("next")  # type: ignore[assignment]

    return files


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_repo_tree(repo_url: str, token: str) -> list[str]:
    """Return a list of all file paths in the default branch."""
    workspace, repo_slug = _parse_repo(repo_url)
    headers = _auth_headers(token)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}",
            headers=headers,
        )
        resp.raise_for_status()
        default_branch = resp.json()["mainbranch"]["name"]

        # Resolve branch → commit hash
        resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/refs/branches/{default_branch}",
            headers=headers,
        )
        resp.raise_for_status()
        commit = resp.json()["target"]["hash"]

        all_files = await _list_all_files(client, workspace, repo_slug, commit, token)

    paths = [
        item["path"]
        for item in all_files
        if not _should_skip(item["path"])
    ]
    return paths


async def get_file_content(repo_url: str, path: str, token: str) -> str | None:
    """Fetch and return the raw content of a single file. Returns None on error."""
    workspace, repo_slug = _parse_repo(repo_url)
    headers = _auth_headers(token)

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src/HEAD/{path}",
            headers=headers,
        )
        if resp.status_code != 200:
            return None
        try:
            return resp.text
        except Exception:
            return None


async def create_pull_request(
    repo_url: str,
    branch_name: str,
    files: list[dict],
    commit_message: str,
    pr_title: str,
    pr_description: str,
    token: str | None = None,
) -> str:
    """Create a branch, commit files via the Bitbucket src API, and open a PR.

    Returns the PR URL (HTML).
    """
    if not token:
        raise ValueError("Bitbucket token is required")

    workspace, repo_slug = _parse_repo(repo_url)
    headers = _auth_headers(token)

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # 1. Get default branch and its HEAD commit hash
        resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}",
            headers=headers,
        )
        resp.raise_for_status()
        default_branch = resp.json()["mainbranch"]["name"]

        resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/refs/branches/{default_branch}",
            headers=headers,
        )
        resp.raise_for_status()
        base_hash = resp.json()["target"]["hash"]

        # 2. Create branch pointing at base commit
        resp = await client.post(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/refs/branches",
            headers=headers,
            json={"name": branch_name, "target": {"hash": base_hash}},
        )
        if resp.status_code == 400 and "already exists" in resp.text.lower():
            logger.warning(f"[Bitbucket] Branch {branch_name!r} already exists, reusing.")
        elif resp.status_code not in (200, 201):
            resp.raise_for_status()

        # 3. Commit files to the new branch via src endpoint (multipart/form-data)
        form_data: dict[str, str] = {
            "message": commit_message,
            "branch": branch_name,
        }
        upload_files: list[tuple[str, bytes]] = []
        for file in files:
            content = file["content"]
            raw = content.encode() if isinstance(content, str) else content
            upload_files.append((file["path"], raw))

        resp = await client.post(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src",
            headers=headers,
            data=form_data,
            files=[(name, (name, content)) for name, content in upload_files],
        )
        resp.raise_for_status()

        # 4. Open the pull request
        resp = await client.post(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests",
            headers=headers,
            json={
                "title": pr_title,
                "description": pr_description,
                "source": {"branch": {"name": branch_name}},
                "destination": {"branch": {"name": default_branch}},
            },
        )
        resp.raise_for_status()
        pr_url: str = resp.json()["links"]["html"]["href"]
        logger.info(f"[Bitbucket] PR created: {pr_url}")
        return pr_url


async def add_files_to_branch(
    repo_url: str,
    branch_name: str,
    files: list[dict],
    commit_message: str,
    token: str,
) -> bool:
    """Add files as a new commit on an existing branch.

    Used by TesterAgent to commit test files after CoderAgent has already
    opened the PR.  Returns True on success, False on any failure (never
    raises — callers treat this as non-fatal).
    """
    if not files:
        return False

    workspace, repo_slug = _parse_repo(repo_url)
    headers = _auth_headers(token)

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            form_data: dict[str, str] = {
                "message": commit_message,
                "branch": branch_name,
            }
            upload_files: list[tuple[str, bytes]] = []
            for file in files:
                content = file["content"]
                raw = content.encode() if isinstance(content, str) else content
                upload_files.append((file["path"], raw))

            resp = await client.post(
                f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/src",
                headers=headers,
                data=form_data,
                files=[(name, (name, content)) for name, content in upload_files],
            )
            resp.raise_for_status()

        logger.info(
            f"[Bitbucket] add_files_to_branch: {len(files)} file(s) committed to {branch_name!r}"
        )
        return True

    except Exception as exc:
        logger.warning(f"[Bitbucket] add_files_to_branch failed: {exc}")
        return False


async def get_pr_status(pr_url: str, token: str) -> dict:
    """Check the current state of a Bitbucket pull request.

    Returns the same shape as the GitHub equivalent:
        merged, closed, changes_requested, review_comments, inline_comments,
        reviewers.
    """
    try:
        workspace, repo_slug, pr_id = _parse_pr_url(pr_url)
    except ValueError as exc:
        logger.warning(f"[Bitbucket] get_pr_status: {exc}")
        return {
            "merged": False,
            "closed": False,
            "changes_requested": False,
            "review_comments": [],
            "inline_comments": [],
            "reviewers": [],
        }

    headers = _auth_headers(token)
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}",
            headers=headers,
        )
        if resp.status_code == 404:
            logger.warning(f"[Bitbucket] PR not found: {pr_url}")
            return {
                "merged": False,
                "closed": False,
                "changes_requested": False,
                "review_comments": [],
                "inline_comments": [],
                "reviewers": [],
            }
        resp.raise_for_status()
        pr = resp.json()

        state = pr.get("state", "")  # OPEN | MERGED | DECLINED | SUPERSEDED
        merged = state == "MERGED"
        closed = state in {"DECLINED", "SUPERSEDED"} and not merged

        # Participants carry approval state
        participants = pr.get("participants", [])
        changes_requested = any(
            p.get("state") == "changes_requested" for p in participants
        )
        reviewers = [
            p.get("user", {}).get("nickname", "")
            for p in participants
            if p.get("user", {}).get("nickname")
        ]

        # Fetch actual comments from the PR comment thread
        comments_resp = await client.get(
            f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments",
            headers=headers,
            params={"pagelen": 50},
        )
        review_comments: list[dict] = []
        inline_comments: list[dict] = []
        if comments_resp.is_success:
            for c in comments_resp.json().get("values", []):
                body = (c.get("content") or {}).get("raw", "").strip()
                if not body:
                    continue
                reviewer = (c.get("user") or {}).get("nickname", "unknown")
                inline_path = (c.get("inline") or {}).get("path", "")
                if inline_path:
                    inline_comments.append({"path": inline_path, "body": body, "reviewer": reviewer})
                else:
                    review_comments.append({"body": body, "reviewer": reviewer, "state": "COMMENTED"})

    return {
        "merged": merged,
        "closed": closed,
        "changes_requested": changes_requested,
        "review_comments": review_comments,
        "inline_comments": inline_comments,
        "reviewers": reviewers,
    }


async def fetch_merged_prs(
    repo_url: str,
    token: str,
    count: int = 200,
) -> list[dict]:
    """Fetch the last *count* merged PRs with diffs and review context.

    Returns a list of dicts matching the shape produced by
    ``github_service.fetch_merged_prs``.
    """
    workspace, repo_slug = _parse_repo(repo_url)
    headers = _auth_headers(token)
    prs: list[dict] = []
    url: str | None = (
        f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests"
        f"?state=MERGED&pagelen=50&sort=-updated_on"
    )

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        while url and len(prs) < count:
            resp = await client.get(url, headers=headers)
            if not resp.is_success:
                logger.warning(f"[Bitbucket] fetch_merged_prs failed: {resp.status_code}")
                break
            data = resp.json()
            for pr in data.get("values", []):
                prs.append({
                    "number": pr["id"],
                    "title": pr["title"],
                    "body": (pr.get("description") or "")[:2000],
                    "url": pr["links"]["html"]["href"],
                    "author": (pr.get("author") or {}).get("nickname", ""),
                    "merged_at": pr.get("updated_on", ""),
                })
                if len(prs) >= count:
                    break
            url = data.get("next")

        # Enrich each PR with diff, files changed, reviewer info
        for pr_record in prs:
            pr_id = pr_record["number"]
            try:
                # Files changed (diffstat)
                diffstat_resp = await client.get(
                    f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diffstat",
                    headers=headers,
                )
                if diffstat_resp.is_success:
                    pr_record["files_changed"] = [
                        (f.get("new") or f.get("old") or {}).get("path", "")
                        for f in diffstat_resp.json().get("values", [])
                    ]
                else:
                    pr_record["files_changed"] = []

                # Raw diff (truncated)
                diff_resp = await client.get(
                    f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/diff",
                    headers=headers,
                )
                pr_record["diff"] = diff_resp.text[:4000] if diff_resp.is_success else ""

                # Participants → reviewers
                pr_detail_resp = await client.get(
                    f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}",
                    headers=headers,
                )
                if pr_detail_resp.is_success:
                    participants = pr_detail_resp.json().get("participants", [])
                    pr_record["reviewers"] = list({
                        p.get("user", {}).get("nickname", "")
                        for p in participants
                        if p.get("user", {}).get("nickname")
                    })
                else:
                    pr_record["reviewers"] = []

                # Actual review comments from comment thread
                comments_resp = await client.get(
                    f"{BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests/{pr_id}/comments",
                    headers=headers,
                    params={"pagelen": 30},
                )
                if comments_resp.is_success:
                    pr_record["review_comments"] = [
                        (c.get("content") or {}).get("raw", "").strip()
                        for c in comments_resp.json().get("values", [])
                        if (c.get("content") or {}).get("raw", "").strip()
                    ]
                    pr_record["attributed_comments"] = [
                        {
                            "body": (c.get("content") or {}).get("raw", "").strip(),
                            "reviewer": (c.get("user") or {}).get("nickname", ""),
                        }
                        for c in comments_resp.json().get("values", [])
                        if (c.get("content") or {}).get("raw", "").strip() and (c.get("user") or {}).get("nickname")
                    ]
                else:
                    pr_record["review_comments"] = []
                    pr_record["attributed_comments"] = []

            except Exception as exc:
                logger.warning(f"[Bitbucket] Failed to enrich PR #{pr_id}: {exc}")
                pr_record.setdefault("files_changed", [])
                pr_record.setdefault("diff", "")
                pr_record.setdefault("reviewers", [])
                pr_record.setdefault("review_comments", [])

    logger.info(f"[Bitbucket] Fetched {len(prs)} merged PRs from {workspace}/{repo_slug}")
    return prs
