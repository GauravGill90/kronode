"""Context provider registry — composable context sources.

Adding a new context source = one provider file + register here.
All outflow connectors (MCP, REST, Slack, Jira) call get_all_context().
"""
from app.services.context_providers.base import ContextProvider
from app.services.context_providers.conventions_provider import ConventionsProvider
from app.services.context_providers.pitfalls_provider import PitfallsProvider
from app.services.context_providers.reviewer_patterns_provider import ReviewerPatternsProvider
from app.services.context_providers.past_failures_provider import PastFailuresProvider
from app.services.context_providers.doc_chunks_provider import DocChunksProvider

_PROVIDERS: list[ContextProvider] = [
    ConventionsProvider(),
    PitfallsProvider(),
    ReviewerPatternsProvider(),
    PastFailuresProvider(),
    DocChunksProvider(),
]


def register_provider(provider: ContextProvider):
    """Register a new context provider at runtime."""
    _PROVIDERS.append(provider)


async def get_all_context(
    org_id: int,
    task_description: str,
    files_touched: list[str] | None = None,
) -> dict:
    """Gather context from all registered providers and merge results."""
    merged: dict = {"org_id": org_id}

    for provider in _PROVIDERS:
        try:
            result = await provider.get_context(org_id, task_description, files_touched)
            merged.update(result)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                f"[ContextProvider] {provider.name} failed: {e}"
            )

    return merged
