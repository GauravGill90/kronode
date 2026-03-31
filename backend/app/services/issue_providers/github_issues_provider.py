"""GitHub Issues provider — REST API. Reuses the same token as git provider."""
import logging

import httpx

from app.services.issue_providers.base import IssueProvider

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


def _parse_repo(repo_url: str) -> tuple[str, str]:
    url = repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = url.split("/")
    return parts[-2], parts[-1]


class GitHubIssuesProvider(IssueProvider):

    def _headers(self, config: dict) -> dict:
        return {
            "Authorization": f"Bearer {config['token']}",
            "Accept": "application/vnd.github+json",
        }

    async def fetch_open_issues(self, config: dict, max_results: int = 20) -> list[dict]:
        owner, repo = _parse_repo(config["repo_url"])
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues",
                headers=self._headers(config),
                params={"state": "open", "per_page": max_results, "sort": "updated"},
            )
            if not resp.is_success:
                return []
            issues = resp.json()
            return [
                {
                    "id": str(i["number"]),
                    "key": f"#{i['number']}",
                    "title": i.get("title", ""),
                    "description": (i.get("body") or "")[:500],
                    "status": "open",
                    "assignee": i.get("assignee", {}).get("login", "") if i.get("assignee") else "",
                    "url": i.get("html_url", ""),
                    "labels": [l["name"] for l in i.get("labels", [])],
                }
                for i in issues
                if "pull_request" not in i  # exclude PRs
            ]

    async def fetch_issue_detail(self, config: dict, issue_id: str) -> dict | None:
        owner, repo = _parse_repo(config["repo_url"])
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_id}",
                headers=self._headers(config),
            )
            if not resp.is_success:
                return None
            i = resp.json()

            # Fetch comments
            comments_resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_id}/comments",
                headers=self._headers(config),
                params={"per_page": 20},
            )
            comments = []
            if comments_resp.is_success:
                comments = [
                    {"author": c.get("user", {}).get("login", ""), "body": c.get("body", "")}
                    for c in comments_resp.json()
                ]

            return {
                "id": str(i["number"]),
                "key": f"#{i['number']}",
                "title": i.get("title", ""),
                "description": i.get("body", "") or "",
                "status": i.get("state", "open"),
                "assignee": i.get("assignee", {}).get("login", "") if i.get("assignee") else "",
                "labels": [l["name"] for l in i.get("labels", [])],
                "comments": comments,
                "url": i.get("html_url", ""),
            }

    async def update_issue_status(self, config: dict, issue_id: str, status: str, pr_url: str | None = None) -> bool:
        owner, repo = _parse_repo(config["repo_url"])
        state = "closed" if status.lower() in ("done", "closed", "resolved") else "open"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_id}",
                headers=self._headers(config),
                json={"state": state},
            )
            return resp.is_success

    async def post_comment(self, config: dict, issue_id: str, comment: str) -> bool:
        owner, repo = _parse_repo(config["repo_url"])
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{GITHUB_API}/repos/{owner}/{repo}/issues/{issue_id}/comments",
                headers=self._headers(config),
                json={"body": comment},
            )
            return resp.is_success

    async def validate_credentials(self, config: dict) -> dict:
        owner, repo = _parse_repo(config["repo_url"])
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{GITHUB_API}/repos/{owner}/{repo}",
                headers=self._headers(config),
            )
            if resp.is_success:
                return {"valid": True, "error": None, "project_name": f"{owner}/{repo}"}
            return {"valid": False, "error": f"HTTP {resp.status_code}", "project_name": ""}
