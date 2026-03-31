"""Embedding helper for semantic search.

Priority:
1. Local sentence-transformers (free, no data leaves the server)
2. OpenAI text-embedding-3-small (if OPENAI_API_KEY set and local unavailable)
3. None (falls back to keyword matching)

No pgvector needed — cosine similarity computed in Python.
"""
import logging
import math

logger = logging.getLogger(__name__)

# In-memory cache: text -> embedding vector
_cache: dict[str, list[float]] = {}

# Local model singleton (loaded once, reused)
_local_model = None
_local_model_failed = False


def _get_local_model():
    """Load the local sentence-transformers model (lazy, singleton)."""
    global _local_model, _local_model_failed
    if _local_model is not None:
        return _local_model
    if _local_model_failed:
        return None

    try:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: 384 dimensions, 80MB, very fast
        # Good enough for convention/doc matching. Free. Private.
        _local_model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("[Embeddings] Local model loaded: all-MiniLM-L6-v2")
        return _local_model
    except ImportError:
        logger.info("[Embeddings] sentence-transformers not installed, falling back to OpenAI")
        _local_model_failed = True
        return None
    except Exception as e:
        logger.warning(f"[Embeddings] Local model failed to load: {e}")
        _local_model_failed = True
        return None


def _local_embed(texts: list[str]) -> list[list[float]]:
    """Embed texts using the local model. Synchronous."""
    model = _get_local_model()
    if model is None:
        return []
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return [emb.tolist() for emb in embeddings]


async def get_embedding(text: str) -> list[float] | None:
    """Get embedding for a text string. Returns None if unavailable."""
    if text in _cache:
        return _cache[text]

    # Try local first
    model = _get_local_model()
    if model is not None:
        try:
            result = _local_embed([text])
            if result:
                _cache[text] = result[0]
                return result[0]
        except Exception as e:
            logger.warning(f"[Embeddings] Local embed failed: {e}")

    # Fallback to OpenAI
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
        logger.warning(f"[Embeddings] OpenAI failed: {exc}")
        return None


async def get_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    """Get embeddings for multiple texts. Uses local model if available."""
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

    # Try local model first (batch is fast)
    model = _get_local_model()
    if model is not None:
        try:
            embeddings = _local_embed(uncached_texts)
            for j, emb in enumerate(embeddings):
                idx = uncached_indices[j]
                results[idx] = emb
                _cache[uncached_texts[j]] = emb
            return results
        except Exception as e:
            logger.warning(f"[Embeddings] Local batch failed: {e}")

    # Fallback to OpenAI
    from app.core.config import settings
    if not settings.openai_api_key:
        return results

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=settings.openai_api_key)

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
        logger.warning(f"[Embeddings] OpenAI batch failed: {exc}")

    return results


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    if len(a) != len(b):
        # Dimension mismatch (e.g., local 384 vs OpenAI 1536) — can't compare
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
