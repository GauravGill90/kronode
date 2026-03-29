from app.services.doc_providers.base import DocProvider, RawDoc, ChunkData
from app.services.doc_providers.git_provider import GitDocProvider

_PROVIDERS: dict[str, type[DocProvider]] = {
    "git": GitDocProvider,
}


def get_provider(source_type: str) -> DocProvider:
    """Return a doc provider instance for the given source type."""
    cls = _PROVIDERS.get(source_type)
    if not cls:
        raise ValueError(f"Unknown doc provider: {source_type!r}. Available: {list(_PROVIDERS)}")
    return cls()
