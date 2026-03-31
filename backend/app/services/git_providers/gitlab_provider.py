"""GitLab git provider — GitLab REST API v4.

Supports gitlab.com and self-hosted instances. The repo_url is parsed to
determine the API base:
  - https://gitlab.com/group/project  → https://gitlab.com/api/v4
  - https://git.corp.com/group/project → https://git.corp.com/api/v4
"""
import base64
import logging
from urllib.parse import quote_plus, urlparse

import httpx

from app.services.git_providers.base import GitProvider

logger = logging.getLogger(__name__)

# Extensions to skip — same as github/bitbucket services
_SKIP_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp",
    ".pdf", ".zip", ".tar", ".gz", ".woff", ".woff2", ".ttf", ".eot",
    ".mp4", ".mp3", ".wav", ".ogg",
    ".lock", ".sum", ".min.js", ".min.css",
}
_SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "__pycache__",
    ".venv", "venv", ".env", "coverage", ".turbo",
}


def _parse_repo(repo_url: str) -> tuple[str, str]:
    """Extract (api_base, project_path_encoded) from a GitLab URL.

    Returns:
        api_base: e.g. "https://gitlab.com/api/v4"
        project_path: URL-encoded project path, e.g. "group%2Fproject"
    """
    url = repo_url.rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parsed = urlparse(url)
    # path is e.g. /group/subgroup/project
    path_parts = parsed.path.strip("/")
    api_base = f"{parsed.scheme}://{parsed.netloc}/api/v4"
    project_path = quote_plus(path_parts)
    return api_base, project_path


def _auth_headers(token: str) -> dict[str, str]:
    return {"PRIVATE-TOKEN": token}


def _should_skip(path: str) -> bool:
    lower = path.lower()
    if any(f"/{d}/" in f"/{lower}/" for d in _SKIP_DIRS):
        return True
    return any(lower.endswith(ext) for ext in _SKIP_EXTENSIONS)


class GitLabProvider(GitProvider):

    async def get_repo_tree(self, repo_url: str, token: str) -> list[str]:
        api_base, project = _parse_repo(repo_url)
        headers = _auth_headers(token)
        files: list[str] = []

        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            while True:
                resp = await client.get(
                    f"{api_base}/projects/{project}/repository/tree",
                    headers=headers,
                    params={"recursive": "true", "per_page": 100, "page": page},
                )
                if resp.status_code != 200:
                    logger.error(f"[GitLab] tree fetch failed: {resp.status_code}")
                    break

                items = resp.json()
                if not items:
                    break

                for item in items:
                    if item.get("type") == "blob" and not _should_skip(item["path"]):
                        files.append(item["path"])
                page += 1

        logger.info(f"[GitLab] repo tree: {len(files)} files")
        return files

    async def get_file_content(self, repo_url: str, path: str, token: str) -> str | None:
        api_base, project = _parse_repo(repo_url)
        headers = _auth_headers(token)
        encoded_path = quote_plus(path)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{api_base}/projects/{project}/repository/files/{encoded_path}",
                headers=headers,
                params={"ref": "HEAD"},
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            content = data.get("content", "")
            encoding = data.get("encoding", "base64")
            if encoding == "base64":
                try:
                    return base64.b64decode(content).decode("utf-8", errors="replace")
                except Exception:
                    return None
            return content

    async def create_pull_request(
        self,
        repo_url: str,
        branch_name: str,
        files: list[dict],
        commit_message: str,
        pr_title: str,
        pr_description: str,
        token: str,
    ) -> str:
        api_base, project = _parse_repo(repo_url)
        headers = _auth_headers(token)

        async with httpx.AsyncClient(timeout=30) as client:
            # Get default branch
            repo_resp = await client.get(
                f"{api_base}/projects/{project}", headers=headers,
            )
            repo_data = repo_resp.json()
            default_branch = repo_data.get("default_branch", "main")

            # Create branch
            await client.post(
                f"{api_base}/projects/{project}/repository/branches",
                headers=headers,
                json={"branch": branch_name, "ref": default_branch},
            )

            # Commit files using the commits API
            actions = []
            for f in files:
                actions.append({
                    "action": "create",
                    "file_path": f["path"],
                    "content": f["content"],
                })

            await client.post(
                f"{api_base}/projects/{project}/repository/commits",
                headers=headers,
                json={
                    "branch": branch_name,
                    "commit_message": commit_message,
                    "actions": actions,
                },
            )

            # Create merge request
            mr_resp = await client.post(
                f"{api_base}/projects/{project}/merge_requests",
                headers=headers,
                json={
                    "source_branch": branch_name,
                    "target_branch": default_branch,
                    "title": pr_title,
                    "description": pr_description,
                },
            )
            mr_data = mr_resp.json()
            return mr_data.get("web_url", "")

    async def open_pull_request(
        self,
        repo_url: str,
        branch_name: str,
        pr_title: str,
        pr_description: str,
        token: str,
    ) -> str:
        api_base, project = _parse_repo(repo_url)
        headers = _auth_headers(token)
        async with httpx.AsyncClient(timeout=30) as client:
            repo_resp = await client.get(
                f"{api_base}/projects/{project}", headers=headers,
            )
            repo_data = repo_resp.json()
            default_branch = repo_data.get("default_branch", "main")
            mr_resp = await client.post(
                f"{api_base}/projects/{project}/merge_requests",
                headers=headers,
                json={
                    "source_branch": branch_name,
                    "target_branch": default_branch,
                    "title": pr_title,
                    "description": pr_description,
                },
            )
            mr_data = mr_resp.json()
            return mr_data.get("web_url", "")

    async def add_files_to_branch(
        self,
        repo_url: str,
        branch_name: str,
        files: list[dict],
        commit_message: str,
        token: str,
    ) -> bool:
        if not files:
            return False

        api_base, project = _parse_repo(repo_url)
        headers = _auth_headers(token)

        actions = []
        for f in files:
            actions.append({
                "action": "update",
                "file_path": f["path"],
                "content": f["content"],
            })

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{api_base}/projects/{project}/repository/commits",
                headers=headers,
                json={
                    "branch": branch_name,
                    "commit_message": commit_message,
                    "actions": actions,
                },
            )
            return resp.status_code in (200, 201)

    async def get_pr_status(self, pr_url: str, token: str) -> dict:
        """Fetch merge request status.

        GitLab MR URLs: https://gitlab.com/group/project/-/merge_requests/123
        """
        url = pr_url.rstrip("/")
        parsed = urlparse(url)
        # path: /group/project/-/merge_requests/123
        parts = parsed.path.strip("/").split("/")

        # Find merge_requests in path and extract MR IID
        mr_idx = None
        for i, p in enumerate(parts):
            if p == "merge_requests" and i + 1 < len(parts):
                mr_idx = i
                break

        if mr_idx is None:
            return {"merged": False, "state": "unknown", "reviews": [], "review_comments": []}

        mr_iid = parts[mr_idx + 1]
        # Project path is everything before "/-/"
        project_parts = parts[:mr_idx - 1]  # skip the "-" before merge_requests
        project_path = "/".join(project_parts)
        api_base = f"{parsed.scheme}://{parsed.netloc}/api/v4"
        project_encoded = quote_plus(project_path)
        headers = _auth_headers(token)

        async with httpx.AsyncClient(timeout=15) as client:
            # Get MR details
            resp = await client.get(
                f"{api_base}/projects/{project_encoded}/merge_requests/{mr_iid}",
                headers=headers,
            )
            if resp.status_code != 200:
                return {"merged": False, "state": "unknown", "reviews": [], "review_comments": []}

            mr = resp.json()
            state = mr.get("state", "opened")  # opened, closed, merged
            merged = state == "merged"

            # Get MR notes (comments)
            notes_resp = await client.get(
                f"{api_base}/projects/{project_encoded}/merge_requests/{mr_iid}/notes",
                headers=headers,
                params={"per_page": 50},
            )
            review_comments = []
            if notes_resp.status_code == 200:
                for note in notes_resp.json():
                    if note.get("system"):
                        continue
                    review_comments.append({
                        "reviewer": note.get("author", {}).get("username", ""),
                        "body": note.get("body", ""),
                    })

            # Get approvals
            approvals_resp = await client.get(
                f"{api_base}/projects/{project_encoded}/merge_requests/{mr_iid}/approvals",
                headers=headers,
            )
            reviews = []
            if approvals_resp.status_code == 200:
                approvals_data = approvals_resp.json()
                for approver in approvals_data.get("approved_by", []):
                    user = approver.get("user", {})
                    reviews.append({
                        "reviewer": user.get("username", ""),
                        "state": "approved",
                        "body": "",
                    })

            return {
                "merged": merged,
                "state": state,
                "reviews": reviews,
                "review_comments": review_comments,
                "changes_requested": not merged and state == "opened" and len(review_comments) > 0,
            }

    async def fetch_merged_prs(
        self, repo_url: str, token: str, count: int = 200,
    ) -> list[dict]:
        api_base, project = _parse_repo(repo_url)
        headers = _auth_headers(token)
        prs: list[dict] = []

        async with httpx.AsyncClient(timeout=30) as client:
            page = 1
            per_page = min(count, 100)

            while len(prs) < count:
                resp = await client.get(
                    f"{api_base}/projects/{project}/merge_requests",
                    headers=headers,
                    params={
                        "state": "merged",
                        "order_by": "updated_at",
                        "sort": "desc",
                        "per_page": per_page,
                        "page": page,
                    },
                )
                if resp.status_code != 200:
                    break

                mrs = resp.json()
                if not mrs:
                    break

                for mr in mrs:
                    mr_iid = mr["iid"]

                    # Fetch diff
                    diff_resp = await client.get(
                        f"{api_base}/projects/{project}/merge_requests/{mr_iid}/changes",
                        headers=headers,
                    )
                    diff_text = ""
                    files_changed = []
                    if diff_resp.status_code == 200:
                        changes = diff_resp.json().get("changes", [])
                        diff_parts = []
                        for change in changes:
                            files_changed.append(change.get("new_path", change.get("old_path", "")))
                            diff_parts.append(change.get("diff", ""))
                        diff_text = "\n".join(diff_parts)

                    # Fetch notes (review comments)
                    notes_resp = await client.get(
                        f"{api_base}/projects/{project}/merge_requests/{mr_iid}/notes",
                        headers=headers,
                        params={"per_page": 50},
                    )
                    review_comments = []
                    reviewers = set()
                    if notes_resp.status_code == 200:
                        for note in notes_resp.json():
                            if note.get("system"):
                                continue
                            author = note.get("author", {}).get("username", "")
                            if author and author != mr.get("author", {}).get("username", ""):
                                reviewers.add(author)
                            review_comments.append({
                                "reviewer": author,
                                "body": note.get("body", ""),
                            })

                    prs.append({
                        "number": mr_iid,
                        "title": mr.get("title", ""),
                        "body": mr.get("description", "") or "",
                        "url": mr.get("web_url", ""),
                        "author": mr.get("author", {}).get("username", ""),
                        "files_changed": files_changed,
                        "diff": diff_text[:50000],  # cap to avoid memory issues
                        "review_comments": review_comments,
                        "reviewers": list(reviewers),
                    })

                    if len(prs) >= count:
                        break

                page += 1

        logger.info(f"[GitLab] fetched {len(prs)} merged MRs")
        return prs

    async def list_org_repos(self, org_or_workspace: str, token: str) -> list[dict]:
        # org_or_workspace is the group name/path. We need to URL-encode it.
        from urllib.parse import quote_plus
        headers = _auth_headers(token)
        repos: list[dict] = []
        group_encoded = quote_plus(org_or_workspace)
        page = 1
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    f"https://gitlab.com/api/v4/groups/{group_encoded}/projects",
                    headers=headers,
                    params={"per_page": 100, "page": page, "archived": "false"},
                )
                if resp.status_code != 200:
                    break
                items = resp.json()
                if not items:
                    break
                for r in items:
                    repos.append({
                        "repo_url": r.get("web_url", ""),
                        "repo_name": r.get("path_with_namespace", ""),
                        "default_branch": r.get("default_branch", "main"),
                        "description": r.get("description") or "",
                    })
                page += 1
        return repos

    async def validate_token(self, token: str, repo_url: str) -> dict:
        api_base, project = _parse_repo(repo_url)
        headers = _auth_headers(token)

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{api_base}/projects/{project}", headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "valid": True,
                        "repo_name": data.get("path_with_namespace", ""),
                        "default_branch": data.get("default_branch", "main"),
                        "error": None,
                    }
                return {
                    "valid": False,
                    "repo_name": "",
                    "default_branch": "",
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                }
        except Exception as e:
            return {
                "valid": False,
                "repo_name": "",
                "default_branch": "",
                "error": str(e),
            }
