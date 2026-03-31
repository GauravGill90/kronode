"""Abstract base for git providers.

Each provider implements the same interface for interacting with a git hosting
platform (GitHub, Bitbucket, GitLab). This allows the rest of the codebase to
be provider-agnostic.
"""
from abc import ABC, abstractmethod


class GitProvider(ABC):
    """Interface for git hosting providers."""

    @abstractmethod
    async def get_repo_tree(self, repo_url: str, token: str) -> list[str]:
        """Return a flat list of file paths in the repository."""
        ...

    @abstractmethod
    async def get_file_content(self, repo_url: str, path: str, token: str) -> str | None:
        """Fetch the content of a single file. Returns None if not found."""
        ...

    @abstractmethod
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
        """Create a branch, commit files, and open a PR. Returns the PR URL."""
        ...

    @abstractmethod
    async def add_files_to_branch(
        self,
        repo_url: str,
        branch_name: str,
        files: list[dict],
        commit_message: str,
        token: str,
    ) -> bool:
        """Add files as a new commit on an existing branch. Returns True on success."""
        ...

    @abstractmethod
    async def get_pr_status(self, pr_url: str, token: str) -> dict:
        """Fetch the current status of a pull request.

        Returns a dict with at least:
            merged: bool
            state: str (open, closed, merged)
            reviews: list[dict] (reviewer, state, body)
            review_comments: list[dict]
        """
        ...

    @abstractmethod
    async def fetch_merged_prs(
        self,
        repo_url: str,
        token: str,
        count: int = 200,
    ) -> list[dict]:
        """Fetch recent merged PRs with diffs, descriptions, and review comments.

        Returns a list of dicts with at least:
            number, title, body, url, author, files_changed,
            diff, review_comments, reviewers
        """
        ...

    @abstractmethod
    async def open_pull_request(
        self,
        repo_url: str,
        branch_name: str,
        pr_title: str,
        pr_description: str,
        token: str,
    ) -> str:
        """Open a PR for an existing branch (branch already pushed via git).
        Returns the PR URL.
        """
        ...

    @abstractmethod
    async def validate_token(self, token: str, repo_url: str) -> dict:
        """Validate the token and return repo metadata.

        Returns a dict with at least:
            valid: bool
            repo_name: str
            default_branch: str
            error: str | None
        """
        ...
