"""Convention extraction from PR history.

Extracts coding conventions from merged PR diffs, descriptions, and review comments
using Gemini Flash (or Haiku fallback) for cheap batch analysis. Deduplicates and scores by frequency.
"""
import json
import logging
import re

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are a coding convention extractor. Analyse this PR diff, description, and review comments to extract coding conventions the team follows.

A convention is a recurring pattern or rule the team enforces — not a one-off decision. Look for:
- Naming patterns (variables, files, components)
- Error handling patterns
- Testing patterns
- Import/export style
- Architecture patterns (where things go, how they're structured)
- Code style preferences
- Logging conventions

For each convention found, provide:
- rule: a clear, actionable statement (e.g. "Use named exports for React components")
- category: one of naming, error_handling, testing, logging, architecture, style

Only extract conventions you're confident about. Skip trivial formatting (spacing, semicolons — those belong in linters).

IMPORTANT: Respond with ONLY a JSON object. No markdown, no code blocks, no explanation.
Do NOT include code snippets in the JSON — only the rule text and category string.

{"conventions": [{"rule": "Use named exports for React components", "category": "style"}]}

If no conventions are apparent, respond: {"conventions": []}
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
        from app.core.llm import cheap
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


def deduplicate_conventions(conventions: list[dict]) -> list[dict]:
    """Deduplicate conventions by rule similarity. Groups by exact match on lowercased rule text,
    keeps the version with the highest frequency, and merges examples.

    Each convention should have: rule, category, example, source_prs (list), frequency.
    """
    seen: dict[str, dict] = {}  # normalised_rule -> convention

    for c in conventions:
        # Normalise: lowercase, strip punctuation, collapse whitespace
        key = re.sub(r"[^\w\s]", "", c["rule"].lower())
        key = re.sub(r"\s+", " ", key).strip()

        if key in seen:
            existing = seen[key]
            existing["frequency"] += c.get("frequency", 1)
            # Merge examples (keep unique)
            if c.get("example") and c["example"] not in (existing.get("examples") or []):
                existing.setdefault("examples", []).append(c["example"])
            # Merge source PRs
            for pr_url in c.get("source_prs", []):
                if pr_url not in (existing.get("source_prs") or []):
                    existing.setdefault("source_prs", []).append(pr_url)
            # Merge source files
            current_files = set(existing.get("source_files") or [])
            current_files.update(c.get("source_files", []))
            existing["source_files"] = list(current_files)[:50]
        else:
            seen[key] = {
                "rule": c["rule"],
                "category": c["category"],
                "examples": [c["example"]] if c.get("example") else [],
                "source_prs": list(c.get("source_prs", [])),
                "source_files": list(c.get("source_files", [])),
                "frequency": c.get("frequency", 1),
            }

    return list(seen.values())


def score_conventions(conventions: list[dict]) -> list[dict]:
    """Score conventions by frequency. Higher frequency = higher confidence."""
    if not conventions:
        return []

    max_freq = max(c.get("frequency", 1) for c in conventions)

    for c in conventions:
        freq = c.get("frequency", 1)
        # Confidence: 0.3 base + up to 0.7 based on relative frequency
        c["confidence"] = round(0.3 + 0.7 * (freq / max_freq), 2)

    # Sort by confidence descending
    conventions.sort(key=lambda c: c["confidence"], reverse=True)
    return conventions
