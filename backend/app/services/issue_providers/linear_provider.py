"""Linear issue provider — GraphQL API."""
import logging

import httpx

from app.services.issue_providers.base import IssueProvider

logger = logging.getLogger(__name__)

LINEAR_API = "https://api.linear.app/graphql"


class LinearProvider(IssueProvider):

    def _headers(self, config: dict) -> dict:
        return {
            "Authorization": config["api_key"],
            "Content-Type": "application/json",
        }

    async def _graphql(self, config: dict, query: str, variables: dict | None = None) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                LINEAR_API,
                headers=self._headers(config),
                json={"query": query, "variables": variables or {}},
            )
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                raise ValueError(f"Linear API error: {data['errors']}")
            return data.get("data", {})

    async def fetch_open_issues(self, config: dict, max_results: int = 20) -> list[dict]:
        team_key = config.get("team_key", "")
        query = """
        query($teamKey: String, $first: Int) {
            issues(
                filter: {
                    team: { key: { eq: $teamKey } }
                    state: { type: { in: ["backlog", "unstarted", "started"] } }
                }
                first: $first
                orderBy: updatedAt
            ) {
                nodes {
                    id identifier title description
                    state { name }
                    assignee { name }
                    url
                }
            }
        }
        """
        data = await self._graphql(config, query, {"teamKey": team_key, "first": max_results})
        nodes = data.get("issues", {}).get("nodes", [])
        return [
            {
                "id": n["id"],
                "key": n.get("identifier", ""),
                "title": n.get("title", ""),
                "description": (n.get("description") or "")[:500],
                "status": n.get("state", {}).get("name", ""),
                "assignee": n.get("assignee", {}).get("name", "") if n.get("assignee") else "",
                "url": n.get("url", ""),
            }
            for n in nodes
        ]

    async def fetch_issue_detail(self, config: dict, issue_id: str) -> dict | None:
        query = """
        query($id: String!) {
            issue(id: $id) {
                id identifier title description
                state { name }
                assignee { name }
                labels { nodes { name } }
                comments { nodes { body user { name } } }
                url
            }
        }
        """
        data = await self._graphql(config, query, {"id": issue_id})
        issue = data.get("issue")
        if not issue:
            return None
        return {
            "id": issue["id"],
            "key": issue.get("identifier", ""),
            "title": issue.get("title", ""),
            "description": issue.get("description", ""),
            "status": issue.get("state", {}).get("name", ""),
            "assignee": issue.get("assignee", {}).get("name", "") if issue.get("assignee") else "",
            "labels": [l["name"] for l in issue.get("labels", {}).get("nodes", [])],
            "comments": [
                {"author": c.get("user", {}).get("name", ""), "body": c.get("body", "")}
                for c in issue.get("comments", {}).get("nodes", [])
            ],
            "url": issue.get("url", ""),
        }

    async def update_issue_status(self, config: dict, issue_id: str, status: str, pr_url: str | None = None) -> bool:
        # First find the state ID matching the status name
        query = """
        query($teamKey: String) {
            workflowStates(filter: { team: { key: { eq: $teamKey } } }) {
                nodes { id name }
            }
        }
        """
        data = await self._graphql(config, query, {"teamKey": config.get("team_key", "")})
        states = data.get("workflowStates", {}).get("nodes", [])
        target_state = next((s for s in states if s["name"].lower() == status.lower()), None)
        if not target_state:
            logger.warning(f"[Linear] State '{status}' not found")
            return False

        mutation = """
        mutation($id: String!, $stateId: String!) {
            issueUpdate(id: $id, input: { stateId: $stateId }) {
                success
            }
        }
        """
        data = await self._graphql(config, mutation, {"id": issue_id, "stateId": target_state["id"]})
        return data.get("issueUpdate", {}).get("success", False)

    async def post_comment(self, config: dict, issue_id: str, comment: str) -> bool:
        mutation = """
        mutation($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
            }
        }
        """
        data = await self._graphql(config, mutation, {"issueId": issue_id, "body": comment})
        return data.get("commentCreate", {}).get("success", False)

    async def validate_credentials(self, config: dict) -> dict:
        try:
            query = "query { viewer { id name } }"
            data = await self._graphql(config, query)
            viewer = data.get("viewer", {})
            return {"valid": True, "error": None, "project_name": viewer.get("name", "Linear")}
        except Exception as e:
            return {"valid": False, "error": str(e), "project_name": ""}
