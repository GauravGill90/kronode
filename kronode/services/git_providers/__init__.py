from kronode.services.git_providers.base import GitProvider
from kronode.services.git_providers.github_provider import GitHubProvider
from kronode.services.git_providers.bitbucket_provider import BitbucketProvider

_PROVIDERS: dict[str, type[GitProvider]] = {
    "github": GitHubProvider,
    "bitbucket": BitbucketProvider,
}

# GitLab registered lazily to avoid import errors if python-gitlab isn't installed
try:
    from kronode.services.git_providers.gitlab_provider import GitLabProvider
    _PROVIDERS["gitlab"] = GitLabProvider
except ImportError:
    pass


def get_git_provider(provider_type: str) -> GitProvider:
    """Return a git provider instance for the given provider type."""
    cls = _PROVIDERS.get(provider_type)
    if not cls:
        raise ValueError(
            f"Unknown git provider: {provider_type!r}. Available: {list(_PROVIDERS)}"
        )
    return cls()
