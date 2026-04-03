"""Embedding helper — local-first with fastembed (ONNX, ~50MB).

Priority:
1. Local fastembed (free, no data leaves the machine)
2. OpenAI text-embedding-3-small (if OPENAI_API_KEY set)
3. None (falls back to keyword matching)
"""
import logging
import math

logger = logging.getLogger(__name__)

_cache: dict[str, list[float]] = {}
_model = None
_model_failed = False


def _get_model():
    """Load fastembed model (lazy singleton)."""
    global _model, _model_failed
    if _model is not None:
        return _model
    if _model_failed:
        return None

    try:
        from fastembed import TextEmbedding
        _model = TextEmbedding("BAAI/bge-small-en-v1.5")  # 384 dims, ~50MB
        logger.info("[Embeddings] Loaded fastembed model: bge-small-en-v1.5")
        return _model
    except ImportError:
        logger.info("[Embeddings] fastembed not installed — falling back to OpenAI or keywords")
        _model_failed = True
        return None
    except Exception as e:
        logger.warning(f"[Embeddings] Failed to load model: {e}")
        _model_failed = True
        return None


def _local_embed(texts: list[str]) -> list[list[float]]:
    """Embed texts using fastembed."""
    model = _get_model()
    if model is None:
        return []
    embeddings = list(model.embed(texts))
    return [emb.tolist() for emb in embeddings]


async def get_embedding(text: str) -> list[float] | None:
    if text in _cache:
        return _cache[text]

    model = _get_model()
    if model is not None:
        try:
            result = _local_embed([text])
            if result:
                _cache[text] = result[0]
                return result[0]
        except Exception as e:
            logger.warning(f"[Embeddings] Local embed failed: {e}")

    from kronode.core.config import get_settings
    if not get_settings().openai_api_key:
        return None

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        response = await client.embeddings.create(model="text-embedding-3-small", input=text)
        embedding = response.data[0].embedding
        _cache[text] = embedding
        return embedding
    except Exception as exc:
        logger.warning(f"[Embeddings] OpenAI failed: {exc}")
        return None


async def get_embeddings_batch(texts: list[str]) -> list[list[float] | None]:
    uncached_indices, uncached_texts = [], []
    results: list[list[float] | None] = [None] * len(texts)

    for i, text in enumerate(texts):
        if text in _cache:
            results[i] = _cache[text]
        else:
            uncached_indices.append(i)
            uncached_texts.append(text)

    if not uncached_texts:
        return results

    model = _get_model()
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

    from kronode.core.config import get_settings
    if not get_settings().openai_api_key:
        return results

    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=get_settings().openai_api_key)
        for chunk_start in range(0, len(uncached_texts), 100):
            chunk = uncached_texts[chunk_start:chunk_start + 100]
            response = await client.embeddings.create(model="text-embedding-3-small", input=chunk)
            for j, emb_data in enumerate(response.data):
                idx = uncached_indices[chunk_start + j]
                results[idx] = emb_data.embedding
                _cache[uncached_texts[chunk_start + j]] = emb_data.embedding
    except Exception as exc:
        logger.warning(f"[Embeddings] OpenAI batch failed: {exc}")

    return results


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
