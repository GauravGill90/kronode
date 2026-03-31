from app.services.issue_providers.base import IssueProvider
from app.services.issue_providers.jira_provider import JiraProvider
from app.services.issue_providers.linear_provider import LinearProvider
from app.services.issue_providers.github_issues_provider import GitHubIssuesProvider

_PROVIDERS: dict[str, type[IssueProvider]] = {
    "jira": JiraProvider,
    "linear": LinearProvider,
    "github_issues": GitHubIssuesProvider,
}


def get_issue_provider(provider_type: str) -> IssueProvider:
    """Return an issue provider instance for the given provider type."""
    cls = _PROVIDERS.get(provider_type)
    if not cls:
        raise ValueError(f"Unknown issue provider: {provider_type!r}. Available: {list(_PROVIDERS)}")
    return cls()
