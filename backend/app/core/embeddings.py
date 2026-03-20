"""Lightweight embedding helper for semantic search.

Uses OpenAI text-embedding-3-small ($0.02/MTok) for convention matching.
Falls back to keyword matching if no OpenAI key is configured.

No pgvector needed — cosine similarity computed in Python.
Fast enough for <1000 conventions.
"""
import logging
import math

logger = logging.getLogger(__name__)

# In-memory cache: rule text -> embedding vector
_cache: dict[str, list[float]] = {}


async def get_embedding(text: str) -> list[float] | None:
    """Get embedding for a text string. Returns None if unavailable."""
    if text in _cache:
        return _cache[text]

    from app.core.config import settings
    if not settings.openai_api_key:
        return None

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=text,
        )
        embedding = response.data[0].embedding
        _cache[text] = embedding
        return embedding
    except Exception as exc:
        logger.warning(f"[Embeddings] Failed: {exc}")
        return None


async def get_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    """Get embeddings for multiple texts in one API call."""
    from app.core.config import settings
    if not settings.openai_api_key:
        return [None] * len(texts)

    # Check cache first
    uncached_indices = []
    uncached_texts = []
    results: list[list[float] | None] = [None] * len(texts)

    for i, text in enumerate(texts):
        if text in _cache:
            results[i] = _cache[text]
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if not uncached_texts:
        return results

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

        # Batch in chunks of 100
        for chunk_start in range(0, len(uncached_texts), 100):
            chunk = uncached_texts[chunk_start:chunk_start + 100]
            response = await client.embeddings.create(
                model="text-embedding-3-small",
                input=chunk,
            )
            for j, emb_data in enumerate(response.data):
                idx = uncached_indices[chunk_start + j]
                embedding = emb_data.embedding
                results[idx] = embedding
                _cache[uncached_texts[chunk_start + j]] = embedding

    except Exception as exc:
        logger.warning(f"[Embeddings] Batch failed: {exc}")

    return results


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
