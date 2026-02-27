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
