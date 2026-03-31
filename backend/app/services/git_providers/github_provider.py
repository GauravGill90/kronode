"""GitHub git provider — delegates to github_service.py."""
from app.services.git_providers.base import GitProvider
from app.services import github_service


class GitHubProvider(GitProvider):

    async def get_repo_tree(self, repo_url: str, token: str) -> list[str]:
        return await github_service.get_repo_tree(repo_url, token)

    async def get_file_content(self, repo_url: str, path: str, token: str) -> str | None:
        return await github_service.get_file_content(repo_url, path, token)

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
        return await github_service.create_pull_request(
            repo_url, branch_name, files, commit_message, pr_title, pr_description, token,
        )

    async def add_files_to_branch(
        self,
        repo_url: str,
        branch_name: str,
        files: list[dict],
        commit_message: str,
        token: str,
    ) -> bool:
        return await github_service.add_files_to_branch(
            repo_url, branch_name, files, commit_message, token,
        )

    async def open_pull_request(
        self,
        repo_url: str,
        branch_name: str,
        pr_title: str,
        pr_description: str,
        token: str,
    ) -> str:
        import httpx
        owner, repo = github_service._parse_repo(repo_url)
        headers = github_service._auth_headers(token)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{github_service.GITHUB_API}/repos/{owner}/{repo}", headers=headers,
            )
            resp.raise_for_status()
            default_branch = resp.json()["default_branch"]
            resp = await client.post(
                f"{github_service.GITHUB_API}/repos/{owner}/{repo}/pulls",
                headers=headers,
                json={
                    "title": pr_title,
                    "body": pr_description,
                    "head": branch_name,
                    "base": default_branch,
                },
            )
            resp.raise_for_status()
            return resp.json()["html_url"]

    async def get_pr_status(self, pr_url: str, token: str) -> dict:
        return await github_service.get_pr_status(pr_url, token)

    async def fetch_merged_prs(
        self, repo_url: str, token: str, count: int = 200,
    ) -> list[dict]:
        return await github_service.fetch_merged_prs(repo_url, token, count)

    async def validate_token(self, token: str, repo_url: str) -> dict:
        """Validate GitHub token by fetching repo metadata."""
        import httpx

        try:
            owner, repo = github_service._parse_repo(repo_url)
            headers = github_service._auth_headers(token)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{github_service.GITHUB_API}/repos/{owner}/{repo}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "valid": True,
                        "repo_name": data.get("full_name", f"{owner}/{repo}"),
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
