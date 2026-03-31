"""Abstract base for issue/ticket providers (Jira, Linear, GitHub Issues)."""
from abc import ABC, abstractmethod


class IssueProvider(ABC):
    """Interface for issue tracking providers."""

    @abstractmethod
    async def fetch_open_issues(self, config: dict, max_results: int = 20) -> list[dict]:
        """Fetch open issues/tickets. Returns list of dicts with: id, key, title, description, status, assignee, url."""
        ...

    @abstractmethod
    async def fetch_issue_detail(self, config: dict, issue_id: str) -> dict | None:
        """Fetch full detail for a single issue."""
        ...

    @abstractmethod
    async def update_issue_status(self, config: dict, issue_id: str, status: str, pr_url: str | None = None) -> bool:
        """Transition an issue to a new status. Optionally attach PR URL."""
        ...

    @abstractmethod
    async def post_comment(self, config: dict, issue_id: str, comment: str) -> bool:
        """Post a comment on an issue."""
        ...

    @abstractmethod
    async def validate_credentials(self, config: dict) -> dict:
        """Validate credentials. Returns dict with: valid (bool), error (str|None), project_name (str)."""
        ...
