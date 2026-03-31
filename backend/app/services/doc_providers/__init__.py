from app.services.doc_providers.base import DocProvider, RawDoc, ChunkData
from app.services.doc_providers.git_provider import GitDocProvider
from app.services.doc_providers.bitbucket_provider import BitbucketDocProvider
from app.services.doc_providers.confluence_provider import ConfluenceDocProvider

_PROVIDERS: dict[str, type[DocProvider]] = {
    "git": GitDocProvider,
    "bitbucket": BitbucketDocProvider,
    "confluence": ConfluenceDocProvider,
}


def get_provider(source_type: str) -> DocProvider:
    """Return a doc provider instance for the given source type."""
    cls = _PROVIDERS.get(source_type)
    if not cls:
        raise ValueError(f"Unknown doc provider: {source_type!r}. Available: {list(_PROVIDERS)}")
    return cls()
