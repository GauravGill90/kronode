"""Jira issue provider — wraps existing jira_service.py."""
from app.services.issue_providers.base import IssueProvider
from app.services import jira_service


class JiraProvider(IssueProvider):

    async def fetch_open_issues(self, config: dict, max_results: int = 20) -> list[dict]:
        tickets = await jira_service.fetch_project_tickets(
            workspace_url=config["workspace_url"],
            email=config["email"],
            api_token=config["api_token"],
            project_key=config["project_key"],
            epic_key=config.get("epic_key"),
        )
        return tickets[:max_results]

    async def fetch_issue_detail(self, config: dict, issue_id: str) -> dict | None:
        return await jira_service.fetch_ticket_detail(
            workspace_url=config["workspace_url"],
            email=config["email"],
            api_token=config["api_token"],
            ticket_id=issue_id,
        )

    async def update_issue_status(self, config: dict, issue_id: str, status: str, pr_url: str | None = None) -> bool:
        return await jira_service.update_ticket_status(
            workspace_url=config["workspace_url"],
            email=config["email"],
            api_token=config["api_token"],
            ticket_id=issue_id,
            status=status,
            pr_url=pr_url or "",
        )

    async def post_comment(self, config: dict, issue_id: str, comment: str) -> bool:
        return await jira_service.post_plan_comment(
            workspace_url=config["workspace_url"],
            email=config["email"],
            api_token=config["api_token"],
            ticket_id=issue_id,
            plan=comment,
        )

    async def validate_credentials(self, config: dict) -> dict:
        try:
            tickets = await jira_service.fetch_project_tickets(
                workspace_url=config["workspace_url"],
                email=config["email"],
                api_token=config["api_token"],
                project_key=config["project_key"],
            )
            return {"valid": True, "error": None, "project_name": config["project_key"]}
        except Exception as e:
            return {"valid": False, "error": str(e), "project_name": ""}
