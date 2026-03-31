"""Bitbucket git provider — delegates to bitbucket_service.py."""
from app.services.git_providers.base import GitProvider
from app.services import bitbucket_service


class BitbucketProvider(GitProvider):

    async def get_repo_tree(self, repo_url: str, token: str) -> list[str]:
        return await bitbucket_service.get_repo_tree(repo_url, token)

    async def get_file_content(self, repo_url: str, path: str, token: str) -> str | None:
        return await bitbucket_service.get_file_content(repo_url, path, token)

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
        return await bitbucket_service.create_pull_request(
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
        return await bitbucket_service.add_files_to_branch(
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
        workspace, repo_slug = bitbucket_service._parse_repo(repo_url)
        headers = bitbucket_service._auth_headers(token)
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(
                f"{bitbucket_service.BITBUCKET_API}/repositories/{workspace}/{repo_slug}",
                headers=headers,
            )
            resp.raise_for_status()
            default_branch = resp.json()["mainbranch"]["name"]
            resp = await client.post(
                f"{bitbucket_service.BITBUCKET_API}/repositories/{workspace}/{repo_slug}/pullrequests",
                headers=headers,
                json={
                    "title": pr_title,
                    "description": pr_description,
                    "source": {"branch": {"name": branch_name}},
                    "destination": {"branch": {"name": default_branch}},
                },
            )
            resp.raise_for_status()
            return resp.json()["links"]["html"]["href"]

    async def get_pr_status(self, pr_url: str, token: str) -> dict:
        return await bitbucket_service.get_pr_status(pr_url, token)

    async def fetch_merged_prs(
        self, repo_url: str, token: str, count: int = 200,
    ) -> list[dict]:
        return await bitbucket_service.fetch_merged_prs(repo_url, token, count)

    async def list_org_repos(self, org_or_workspace: str, token: str) -> list[dict]:
        import httpx
        headers = bitbucket_service._auth_headers(token)
        repos: list[dict] = []
        url = f"{bitbucket_service.BITBUCKET_API}/repositories/{org_or_workspace}"
        async with httpx.AsyncClient(timeout=30) as client:
            while url:
                resp = await client.get(url, headers=headers, params={"pagelen": 100})
                if resp.status_code != 200:
                    break
                data = resp.json()
                for r in data.get("values", []):
                    repos.append({
                        "repo_url": f"https://bitbucket.org/{r.get('full_name', '')}",
                        "repo_name": r.get("full_name", ""),
                        "default_branch": r.get("mainbranch", {}).get("name", "main"),
                        "description": r.get("description") or "",
                        "language": r.get("language") or "",
                        "pushed_at": r.get("updated_on") or "",
                        "size_kb": r.get("size", 0),
                    })
                url = data.get("next")  # pagination
        return repos

    async def validate_token(self, token: str, repo_url: str) -> dict:
        """Validate Bitbucket token by fetching repo metadata."""
        import httpx

        try:
            workspace, repo_slug = bitbucket_service._parse_repo(repo_url)
            headers = bitbucket_service._auth_headers(token)
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{bitbucket_service.BITBUCKET_API}/repositories/{workspace}/{repo_slug}",
                    headers=headers,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    default_branch = data.get("mainbranch", {}).get("name", "main")
                    return {
                        "valid": True,
                        "repo_name": data.get("full_name", f"{workspace}/{repo_slug}"),
                        "default_branch": default_branch,
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
