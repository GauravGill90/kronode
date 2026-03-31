"""Abstract base for context providers.

Each provider contributes a piece of organizational context (conventions,
pitfalls, docs, reviewer patterns, etc.) that gets merged into the unified
context response served by MCP, REST API, Slack bot, and Jira panel.
"""
from abc import ABC, abstractmethod


class ContextProvider(ABC):
    """Interface for context source providers."""

    name: str = ""
    weight: float = 1.0  # ranking weight for this provider's results

    @abstractmethod
    async def get_context(
        self,
        org_id: int,
        task_description: str,
        files_touched: list[str] | None = None,
    ) -> dict:
        """Return context relevant to the given task.

        Returns a dict with provider-specific keys. The registry merges
        all provider results into a single context response.
        """
        ...
