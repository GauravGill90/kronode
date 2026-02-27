import base64
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def _auth_headers(token: str) -> dict:
    return {**HEADERS, "Authorization": f"Bearer {token}"}


def _parse_repo(repo_url: str) -> tuple[str, str]:
    """Extract owner/repo from a GitHub URL."""
    repo_url = repo_url.rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[:-4]
    parts = repo_url.split("/")
    return parts[-2], parts[-1]


def _parse_pr_url(pr_url: str) -> tuple[str, str, int]:
    """Parse https://github.com/{owner}/{repo}/pull/{number} → (owner, repo, number)."""
    url = pr_url.rstrip("/")
    parts = url.split("/")
    # Expected: ['https:', '', 'github.com', owner, repo, 'pull', number]
    if len(parts) < 7 or parts[5] != "pull":
        raise ValueError(f"Cannot parse PR URL: {pr_url!r}")
    return parts[3], parts[4], int(parts[6])


# Extensions to skip — binaries, lock files, generated assets
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".wav", ".ogg",
    ".lock", ".sum",            # package-lock.json, go.sum, etc.
    ".min.js", ".min.css",      # minified
}
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", ".env", "coverage", ".turbo",
}


def _should_skip(path: str) -> bool:
    parts = path.split("/")
    if any(p in _SKIP_DIRS for p in parts[:-1]):
        return True
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _SKIP_EXTENSIONS)


async def get_repo_tree(repo_url: str, token: str) -> list[str]:
    """Return a list of all file paths in the default branch (excluding binaries/generated)."""
    owner, repo = _parse_repo(repo_url)
    headers = _auth_headers(token)

    async with httpx.AsyncClient(timeout=30) as client:
        # Get default branch
        resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
        resp.raise_for_status()
        default_branch = resp.json()["default_branch"]

        # Get full recursive tree
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1",
            headers=headers,
        )
        resp.raise_for_status()
        tree = resp.json().get("tree", [])

    paths = [
        item["path"]
        for item in tree
        if item["type"] == "blob" and not _should_skip(item["path"])
    ]
    return paths


async def get_file_content(repo_url: str, path: str, token: str) -> str | None:
    """Fetch and decode a single file from the repo. Returns None on error."""
    owner, repo = _parse_repo(repo_url)
    headers = _auth_headers(token)

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}",
            headers=headers,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("encoding") != "base64" or not data.get("content"):
            return None
        try:
            return base64.b64decode(data["content"]).decode("utf-8", errors="replace")
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
    """
    Create a branch, commit files, and open a PR.
    Returns the PR URL.
    """
    access_token = token or settings.github_client_id  # In production, fetch from Secrets Manager
    owner, repo = _parse_repo(repo_url)
    headers = _auth_headers(access_token)

    async with httpx.AsyncClient(timeout=30) as client:
        # Get default branch SHA
        resp = await client.get(f"{GITHUB_API}/repos/{owner}/{repo}", headers=headers)
        resp.raise_for_status()
        default_branch = resp.json()["default_branch"]

        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{default_branch}",
            headers=headers,
        )
        resp.raise_for_status()
        base_sha = resp.json()["object"]["sha"]

        # Create branch
        resp = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs",
            headers=headers,
            json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
        )
        if resp.status_code == 422:
            # Branch already exists — use it
            logger.warning(f"Branch {branch_name} already exists, reusing.")
        else:
            resp.raise_for_status()

        # Get current tree SHA
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/commits/{base_sha}",
            headers=headers,
        )
        resp.raise_for_status()
        tree_sha = resp.json()["tree"]["sha"]

        # Create blobs for each file
        tree_items = []
        for file in files:
            content = file["content"]
            encoded = base64.b64encode(content.encode()).decode() if isinstance(content, str) else base64.b64encode(content).decode()
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs",
                headers=headers,
                json={"content": encoded, "encoding": "base64"},
            )
            resp.raise_for_status()
            blob_sha = resp.json()["sha"]
            tree_items.append({
                "path": file["path"],
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        # Create tree
        resp = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/trees",
            headers=headers,
            json={"base_tree": tree_sha, "tree": tree_items},
        )
        resp.raise_for_status()
        new_tree_sha = resp.json()["sha"]

        # Create commit
        resp = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/commits",
            headers=headers,
            json={
                "message": commit_message,
                "tree": new_tree_sha,
                "parents": [base_sha],
            },
        )
        resp.raise_for_status()
        new_commit_sha = resp.json()["sha"]

        # Update branch ref
        resp = await client.patch(
            f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{branch_name}",
            headers=headers,
            json={"sha": new_commit_sha},
        )
        resp.raise_for_status()

        # Open PR
        resp = await client.post(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls",
            headers=headers,
            json={
                "title": pr_title,
                "body": pr_description,
                "head": branch_name,
                "base": default_branch,
            },
        )
        resp.raise_for_status()
        pr_url = resp.json()["html_url"]
        logger.info(f"PR created: {pr_url}")
        return pr_url


async def add_files_to_branch(
    repo_url: str,
    branch_name: str,
    files: list[dict],
    commit_message: str,
    token: str,
) -> bool:
    """Add files as a new commit on an existing branch.

    Used by TesterAgent to commit test files after CoderAgent has already opened the PR.
    Returns True on success, False on any failure (never raises — callers treat this as non-fatal).
    """
    if not files:
        return False

    owner, repo = _parse_repo(repo_url)
    headers = _auth_headers(token)

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Get current HEAD SHA for the branch
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{branch_name}",
                headers=headers,
            )
            resp.raise_for_status()
            head_sha = resp.json()["object"]["sha"]

            # 2. Get tree SHA of the HEAD commit
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/commits/{head_sha}",
                headers=headers,
            )
            resp.raise_for_status()
            tree_sha = resp.json()["tree"]["sha"]

            # 3. Create blobs for each file
            tree_items = []
            for file in files:
                content = file["content"]
                encoded = base64.b64encode(
                    content.encode() if isinstance(content, str) else content
                ).decode()
                resp = await client.post(
                    f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs",
                    headers=headers,
                    json={"content": encoded, "encoding": "base64"},
                )
                resp.raise_for_status()
                tree_items.append({
                    "path": file["path"],
                    "mode": "100644",
                    "type": "blob",
                    "sha": resp.json()["sha"],
                })

            # 4. Create new tree on top of existing tree
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/trees",
                headers=headers,
                json={"base_tree": tree_sha, "tree": tree_items},
            )
            resp.raise_for_status()
            new_tree_sha = resp.json()["sha"]

            # 5. Create commit on top of HEAD
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/commits",
                headers=headers,
                json={"message": commit_message, "tree": new_tree_sha, "parents": [head_sha]},
            )
            resp.raise_for_status()
            new_commit_sha = resp.json()["sha"]

            # 6. Fast-forward branch ref
            resp = await client.patch(
                f"{GITHUB_API}/repos/{owner}/{repo}/git/refs/heads/{branch_name}",
                headers=headers,
                json={"sha": new_commit_sha},
            )
            resp.raise_for_status()

        logger.info(f"[GitHub] add_files_to_branch: {len(files)} file(s) committed to {branch_name}")
        return True

    except Exception as exc:
        logger.warning(f"[GitHub] add_files_to_branch failed: {exc}")
        return False


async def get_pr_status(pr_url: str, token: str) -> dict:
    """Check the current state of a GitHub pull request.

    Returns:
        merged: bool — PR was merged
        closed: bool — PR was closed without merging
        changes_requested: bool — at least one reviewer requested changes
        review_comments: list[str] — bodies from CHANGES_REQUESTED reviews
    """
    try:
        owner, repo, number = _parse_pr_url(pr_url)
    except ValueError as exc:
        logger.warning(f"[GitHub] get_pr_status: {exc}")
        return {"merged": False, "closed": False, "changes_requested": False, "review_comments": []}

    headers = _auth_headers(token)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}", headers=headers
        )
        if resp.status_code == 404:
            logger.warning(f"[GitHub] PR not found: {pr_url}")
            return {"merged": False, "closed": False, "changes_requested": False, "review_comments": [], "inline_comments": []}
        resp.raise_for_status()
        pr = resp.json()
        merged = pr.get("merged_at") is not None
        closed = pr.get("state") == "closed" and not merged

        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/reviews", headers=headers
        )
        resp.raise_for_status()
        reviews = resp.json()

        # Inline line-level review comments
        resp = await client.get(
            f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{number}/comments", headers=headers
        )
        resp.raise_for_status()
        inline = resp.json()

    changes_requested = any(r.get("state") == "CHANGES_REQUESTED" for r in reviews)
    review_comments = [
        r.get("body", "").strip()
        for r in reviews
        if r.get("state") == "CHANGES_REQUESTED" and r.get("body", "").strip()
    ]
    # Inline comments: body + file path for context
    inline_comments = [
        {"path": c.get("path", ""), "body": c.get("body", "").strip()}
        for c in inline
        if c.get("body", "").strip()
    ]
    return {
        "merged": merged,
        "closed": closed,
        "changes_requested": changes_requested,
        "review_comments": review_comments,
        "inline_comments": inline_comments,
    }
