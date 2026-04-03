"""Convention extraction from PR history.

Extracts coding conventions from merged PR diffs, descriptions, and review comments
using Gemini Flash (or Haiku fallback) for cheap batch analysis. Deduplicates and scores by frequency.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are extracting TEAM-SPECIFIC coding conventions from a PR — patterns unique to THIS project, not universal best practices.

DO NOT extract:
- Universal language features everyone uses (optional chaining, async/await, destructuring, arrow functions)
- Generic advice any developer knows ("use clear naming", "handle errors", "separate concerns", "write tests")
- Linter-enforceable rules (semicolons, indentation, quotes, trailing commas)
- One-off decisions specific to this single PR that won't recur

DO extract:
- Project-specific naming patterns (e.g. "Handler suffix for API route files in packages/api/")
- Team architecture decisions (e.g. "All DB queries go through repository classes in lib/repos/")
- Non-obvious conventions a new team member would NOT guess (e.g. "Prisma schema changes require a migration script in packages/prisma/")
- Testing patterns specific to this project (e.g. "Use TestContext factory from tests/fixtures/ for integration tests")
- Import/export conventions beyond the obvious (e.g. "Barrel exports only in packages/*, not in apps/*")
- Tool/library-specific usage patterns (e.g. "Use tRPC routers in packages/trpc/server/routers/, never REST endpoints")

IMPORTANT: Every "rule" MUST reference a concrete project-specific detail — a file path pattern, directory, library name, component name, or tool. If the rule could apply to ANY project in this language without modification, it is too generic — DO NOT include it.

For each convention, provide:
- rule: a clear, actionable statement with project-specific detail
- category: one of naming, error_handling, testing, logging, architecture, style

Respond with ONLY a JSON object. No markdown, no code blocks, no explanation.

{"conventions": [{"rule": "Use tRPC routers in packages/trpc/server/routers/ instead of REST endpoints in pages/api/", "category": "architecture"}]}

If no project-specific conventions are apparent, respond: {"conventions": []}
"""


async def extract_conventions_from_pr(pr: dict) -> list[dict]:
    """Extract conventions from a single PR using Haiku.

    Args:
        pr: Dict with keys: title, body, diff, review_comments, files_changed

    Returns:
        List of convention dicts: [{rule, category, example}]
    """
    diff = pr.get("diff", "")
    if not diff:
        return []

    # Build context for the LLM
    parts = [f"PR: {pr.get('title', '')}"]
    if pr.get("body"):
        parts.append(f"Description:\n{pr['body'][:500]}")
    parts.append(f"Diff:\n{diff[:3000]}")
    if pr.get("review_comments"):
        comments = "\n".join(f"- {c[:200]}" for c in pr["review_comments"][:5])
        parts.append(f"Review comments:\n{comments}")

    user_message = "\n\n".join(parts)

    try:
        from kronode.core.llm import cheap
        raw = await cheap(system=EXTRACTION_PROMPT, user_message=user_message, max_tokens=1024)
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        # Try direct parse, then extract first JSON object if that fails
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", raw)
            if match:
                parsed = json.loads(match.group())
            else:
                return []
        conventions = parsed.get("conventions", [])

        # Validate structure + attach files from the PR
        files_changed = pr.get("files_changed", [])
        valid = []
        for c in conventions:
            if c.get("rule") and c.get("category"):
                valid.append({
                    "rule": c["rule"],
                    "category": c["category"],
                    "source_files": files_changed,
                })
        return valid

    except Exception as exc:
        logger.warning(f"[ConventionExtractor] LLM extraction failed for PR '{pr.get('title', '?')}': {exc}")
        return []


async def deduplicate_conventions(conventions: list[dict]) -> list[dict]:
    """Deduplicate conventions in two passes:
    1. Exact text match (fast, cheap — catches identical rephrasing)
    2. Semantic similarity via embeddings (catches "Use named exports" ≈ "Prefer named exports over default exports")

    Each convention should have: rule, category, example, source_prs (list), frequency.
    """
    # Pass 1: Exact text dedup (same as before)
    seen: dict[str, dict] = {}

    for c in conventions:
        key = re.sub(r"[^\w\s]", "", c["rule"].lower())
        key = re.sub(r"\s+", " ", key).strip()

        if key in seen:
            _merge_convention(seen[key], c)
        else:
            seen[key] = {
                "rule": c["rule"],
                "category": c["category"],
                "examples": [c["example"]] if c.get("example") else [],
                "source_prs": list(c.get("source_prs", [])),
                "source_files": list(c.get("source_files", [])),
                "frequency": c.get("frequency", 1),
            }

    unique = list(seen.values())

    # Pass 2: Semantic dedup via embeddings
    if len(unique) < 2:
        return unique

    try:
        from kronode.core.embeddings import get_embeddings_batch, cosine_similarity

        rules = [c["rule"] for c in unique]
        embeddings = await get_embeddings_batch(rules)

        # Check if we got valid embeddings
        if not any(e is not None for e in embeddings):
            logger.info("[Dedup] No embeddings available — using text-only dedup")
            return unique

        # Greedy clustering: sort by frequency desc, absorb similar conventions
        indexed = sorted(enumerate(unique), key=lambda x: x[1].get("frequency", 1), reverse=True)
        absorbed = set()
        SIMILARITY_THRESHOLD = 0.85

        for i, (idx_a, conv_a) in enumerate(indexed):
            if idx_a in absorbed:
                continue
            emb_a = embeddings[idx_a]
            if emb_a is None:
                continue

            for idx_b, conv_b in indexed[i + 1:]:
                if idx_b in absorbed:
                    continue
                emb_b = embeddings[idx_b]
                if emb_b is None:
                    continue

                sim = cosine_similarity(emb_a, emb_b)
                if sim >= SIMILARITY_THRESHOLD:
                    _merge_convention(conv_a, conv_b)
                    absorbed.add(idx_b)

        result = [c for i, c in enumerate(unique) if i not in absorbed]
        logger.info(f"[Dedup] Semantic pass: {len(unique)} → {len(result)} (absorbed {len(absorbed)})")
        return result

    except Exception as exc:
        logger.warning(f"[Dedup] Semantic dedup failed: {exc} — using text-only results")
        return unique


def _merge_convention(target: dict, source: dict) -> None:
    """Merge source convention into target, accumulating frequency and sources."""
    target["frequency"] = target.get("frequency", 1) + source.get("frequency", 1)
    if source.get("example") and source["example"] not in (target.get("examples") or []):
        target.setdefault("examples", []).append(source["example"])
    for pr_url in source.get("source_prs", []):
        if pr_url not in (target.get("source_prs") or []):
            target.setdefault("source_prs", []).append(pr_url)
    current_files = set(target.get("source_files") or [])
    current_files.update(source.get("source_files", []))
    target["source_files"] = list(current_files)[:50]


def extract_reviewer_knowledge(pr: dict) -> list[dict]:
    """Extract knowledge directly from reviewer comments — no LLM needed.

    Reviewer comments that are substantive (>50 chars, not just "LGTM")
    often contain real architectural guidance, gotchas, and team norms.
    These get stored as high-confidence conventions because a human
    explicitly taught this pattern.
    """
    comments = pr.get("review_comments", [])
    if not comments:
        return []

    files_changed = pr.get("files_changed", [])
    pr_url = pr.get("url", "")
    reviewers = pr.get("reviewers", [])
    knowledge: list[dict] = []

    # Noise patterns to skip
    _SKIP = {
        "lgtm", "looks good", "nit", "minor", "typo", "nitpick",
        "approved", "ship it", "+1", "nice", "great", "thanks",
    }

    for comment in comments:
        # Handle both string and dict comments
        if isinstance(comment, dict):
            body = comment.get("body", "")
            reviewer = comment.get("reviewer", "")
        else:
            body = str(comment)
            reviewer = reviewers[0] if reviewers else ""

        body = body.strip()

        # Skip short or noise comments
        if len(body) < 60:
            continue
        if any(body.lower().startswith(skip) for skip in _SKIP):
            continue

        # Skip pure questions (usually asking, not teaching)
        if body.count("?") > body.count(".") and len(body) < 200:
            continue

        # This is a substantive review comment — treat it as knowledge
        knowledge.append({
            "rule": f"[Reviewer: {reviewer}] {body[:300]}",
            "category": "architecture",  # reviewer comments are usually about how things should work
            "source_files": files_changed,
            "source_prs": [pr_url] if pr_url else [],
            "enforced_by": [reviewer] if reviewer else [],
            "frequency": 1,
            "confidence": 0.7,  # higher than LLM-extracted (0.3) — human explicitly said this
        })

    return knowledge


def score_conventions(conventions: list[dict]) -> list[dict]:
    """Score conventions by frequency using log scale. Higher frequency = higher confidence."""
    if not conventions:
        return []

    import math
    max_freq = max(c.get("frequency", 1) for c in conventions)

    for c in conventions:
        # Preserve manually set confidence (e.g., reviewer knowledge = 0.7)
        if c.get("confidence", 0) >= 0.5:
            continue

        freq = c.get("frequency", 1)
        if max_freq <= 1:
            c["confidence"] = 0.3
        else:
            c["confidence"] = round(0.3 + 0.7 * (math.log(freq) / math.log(max_freq)), 2)

    conventions.sort(key=lambda c: c["confidence"], reverse=True)
    return conventions
