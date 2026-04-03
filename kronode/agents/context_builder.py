"""Convention ranking — scores and ranks conventions by relevance to a task.

Standalone functions used by the MCP server. No agent class needed.
"""
import logging
import os
import re

logger = logging.getLogger(__name__)

_CATEGORY_FILE_HINTS = {
    "testing": {"test", "spec", "__tests__", "tests", "vitest", "jest"},
    "error_handling": {"error", "exception", "catch", "try", "handler", "middleware"},
    "logging": {"log", "logger", "logging", "sentry", "monitor"},
    "naming": set(),
    "style": set(),
    "architecture": set(),
}


async def _get_category_relevance(description: str) -> dict[str, float]:
    """Keyword-based category relevance. No LLM, instant."""
    desc_lower = description.lower()

    _KEYWORDS: dict[str, list[str]] = {
        "architecture": ["architect", "refactor", "migrate", "restructure", "module", "service", "api", "endpoint", "route", "middleware", "pattern", "design"],
        "style": ["style", "css", "tailwind", "styled", "theme", "ui", "component", "layout", "tamagui", "stylesheet", "color", "font"],
        "naming": ["rename", "name", "naming", "convention", "prefix", "suffix", "case", "camel", "snake"],
        "error_handling": ["error", "exception", "catch", "try", "throw", "handle", "fallback", "retry", "timeout", "crash", "fail"],
        "testing": ["test", "spec", "jest", "vitest", "pytest", "coverage", "mock", "stub", "assert", "expect", "unit test", "integration"],
        "logging": ["log", "logger", "debug", "trace", "console", "print", "monitor", "metric", "telemetry", "sentry"],
    }

    weights: dict[str, float] = {}
    for cat, keywords in _KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in desc_lower)
        if hits >= 3:
            weights[cat] = 2.0
        elif hits >= 1:
            weights[cat] = 1.0
        else:
            weights[cat] = 0.5
    return weights


async def _rank_conventions(
    conv_rows: list,
    description: str,
    selected_paths: list[str],
    category_boost: dict[str, float] | None = None,
    max_conventions: int = 30,
) -> list[dict]:
    """Score and rank conventions by relevance to a task."""
    if category_boost is None:
        category_boost = {}

    semantic_scores: dict[int, float] = {}
    try:
        from kronode.core.embeddings import get_embedding, get_embeddings_batch, cosine_similarity
        task_emb = await get_embedding(description)
        if task_emb:
            rule_texts = [c.rule for c in conv_rows]
            rule_embs = await get_embeddings_batch(rule_texts)
            for idx, emb in enumerate(rule_embs):
                if emb:
                    semantic_scores[idx] = cosine_similarity(task_emb, emb)
            if semantic_scores:
                logger.info(f"[Ranking] Semantic matching: {len(semantic_scores)} conventions scored")
    except Exception as exc:
        logger.warning(f"[Ranking] Semantic matching failed: {exc}")

    desc_lower = description.lower()
    desc_words = {w for w in re.split(r'\W+', desc_lower) if len(w) > 3}

    path_words = set()
    for p in selected_paths:
        parts = p.lower().replace("\\", "/").split("/")
        path_words.update(parts)
        name = os.path.splitext(parts[-1])[0]
        path_words.update(w for w in re.split(r'[\W_]+', name) if len(w) > 2)

    scored: list[tuple[float, dict]] = []

    for c in conv_rows:
        score = 0.0
        rule_lower = c.rule.lower()
        rule_words = {w for w in re.split(r'\W+', rule_lower) if len(w) > 3}

        # Layer boost
        score += 2.0 if getattr(c, 'layer', '') in ('customer', 'manual', 'local') else 0.5

        # Keyword overlap
        overlap = desc_words & rule_words
        score += len(overlap) * 1.5

        # Category relevance
        cat_mult = category_boost.get(getattr(c, 'category', ''), 1.0)
        cat_hints = _CATEGORY_FILE_HINTS.get(getattr(c, 'category', ''), set())
        if cat_hints and (cat_hints & path_words):
            score += 2.0 * cat_mult
        elif not cat_hints:
            score += 0.5 * cat_mult
        else:
            score += 0.3 * cat_mult

        # Path overlap
        path_overlap = path_words & rule_words
        score += len(path_overlap) * 1.0

        # Source file match
        conv_files = set(getattr(c, 'source_files', None) or [])
        if conv_files:
            if conv_files & set(selected_paths):
                score += 5.0
            else:
                conv_dirs = {f.rsplit("/", 1)[0] for f in conv_files if "/" in f}
                selected_dirs = {p.rsplit("/", 1)[0] for p in selected_paths if "/" in p}
                if conv_dirs & selected_dirs:
                    score += 3.0

        # Semantic similarity
        conv_idx = conv_rows.index(c)
        sem_score = semantic_scores.get(conv_idx, 0.0)
        if sem_score > 0.3:
            score += sem_score * 4.0

        # Confidence tiebreaker
        score += getattr(c, 'confidence', 0.5) * 0.5
        score += min(getattr(c, 'frequency', 1) * 0.1, 1.0)

        # File match detection
        has_file_signal = bool(conv_files & set(selected_paths)) if conv_files and selected_paths else False
        if not has_file_signal and conv_files and selected_paths:
            conv_dirs = {f.rsplit("/", 1)[0] for f in conv_files if "/" in f}
            selected_dirs = {p.rsplit("/", 1)[0] for p in selected_paths if "/" in p}
            has_file_signal = bool(conv_dirs & selected_dirs)

        if selected_paths and conv_files and not has_file_signal:
            score *= 0.3

        # Match reason
        match_reason = ""
        if has_file_signal:
            match_reason = "File/directory match"
        elif sem_score > 0.4:
            match_reason = f"Semantic similarity ({sem_score:.2f})"
        elif overlap:
            match_reason = f"Keyword: {', '.join(list(overlap)[:3])}"
        else:
            match_reason = f"Category: {getattr(c, 'category', '')}"

        scored.append((score, {
            "rule": c.rule,
            "category": getattr(c, 'category', ''),
            "confidence": getattr(c, 'confidence', 0.5),
            "layer": getattr(c, 'layer', ''),
            "enforced_by": getattr(c, 'enforced_by', None) or [],
            "source_files": list(conv_files)[:5],
            "source_prs": (getattr(c, 'source_prs', None) or [])[:3],
            "frequency": getattr(c, 'frequency', 1),
            "relevance_score": round(score, 2),
            "file_match": has_file_signal,
            "match_reason": match_reason,
        }))

    scored.sort(key=lambda x: (-int(x[1].get("file_match", False)), -x[0]))
    return [d for _, d in scored[:max_conventions]]
