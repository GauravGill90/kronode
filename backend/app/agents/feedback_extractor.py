"""Feedback extractor — learns from PR review comments.

Called from poll_pr_outcomes when a PR receives changes_requested or is merged.
Extracts conventions from reviewer feedback and updates the conventions table.
Not a pipeline agent — runs as a standalone function.
"""
import json
import logging
import re

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.convention import Convention

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """You are analysing reviewer feedback on a pull request to extract coding conventions the team enforces.

Given the review comments (both summary-level and inline), identify any conventions being enforced or corrections being made.

A convention is a recurring rule or preference — "always use named exports", "add error handling for async calls", "tests must cover edge cases", etc.

For each convention found:
- rule: clear, actionable statement
- category: one of naming, error_handling, testing, logging, architecture, style
- is_rejection: true if the reviewer is rejecting a pattern (i.e. "don't do X"), false if reinforcing a pattern

Respond with valid JSON only:
{"conventions": [{"rule": "...", "category": "...", "is_rejection": false}]}

If no conventions can be extracted, respond: {"conventions": []}
"""


async def extract_from_review(
    org_id: int,
    review_comments: list[str],
    inline_comments: list[dict],
    pr_url: str,
    is_merged: bool = False,
) -> int:
    """Extract conventions from PR review feedback and update the conventions table.

    Args:
        org_id: Organization ID
        review_comments: Summary-level review comments (list of strings)
        inline_comments: Inline comments [{path, body}]
        pr_url: URL of the PR for source attribution
        is_merged: If True, this is positive signal (merged = conventions were followed)

    Returns:
        Number of conventions created or updated
    """
    # Normalise comments — handle both old format (str) and new format ({body, reviewer})
    all_comments: list[str] = []
    reviewer_map: dict[str, list[str]] = {}  # reviewer -> [comments]
    for c in review_comments:
        if isinstance(c, dict):
            body = c.get("body", "")
            reviewer = c.get("reviewer", "unknown")
        else:
            body = str(c)
            reviewer = "unknown"
        if body:
            all_comments.append(f"[{reviewer}] {body}")
            reviewer_map.setdefault(reviewer, []).append(body)

    for ic in inline_comments:
        if ic.get("body"):
            reviewer = ic.get("reviewer", "unknown")
            all_comments.append(f"[{reviewer} on {ic.get('path', '?')}] {ic['body']}")
            reviewer_map.setdefault(reviewer, []).append(ic["body"])

    if not all_comments:
        return 0

    # Build user message
    comments_text = "\n".join(f"- {c[:300]}" for c in all_comments[:15])
    context_label = "merged PR (positive signal — conventions were followed)" if is_merged else "PR with changes requested"
    user_message = f"This is a {context_label}.\n\nReview comments:\n{comments_text}"

    try:
        from app.core.llm import cheap
        raw = await cheap(system=EXTRACTION_PROMPT, user_message=user_message, max_tokens=512)
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        parsed = json.loads(raw)
        extracted = parsed.get("conventions", [])
    except Exception as exc:
        logger.warning(f"[FeedbackExtractor] LLM extraction failed: {exc}")
        return 0

    if not extracted:
        return 0

    updated = 0
    async with AsyncSessionLocal() as db:
        for c in extracted:
            rule = c.get("rule", "").strip()
            if not rule:
                continue

            category = c.get("category", "style")
            is_rejection = c.get("is_rejection", False)

            # Check if this convention matches an existing one
            existing = await db.execute(
                select(Convention).where(
                    Convention.org_id == org_id,
                    Convention.rule == rule,
                )
            )
            existing_conv = existing.scalar_one_or_none()

            # Collect reviewers who enforced this convention
            enforcers = list(reviewer_map.keys())

            if existing_conv:
                if is_rejection and existing_conv.layer == "base":
                    existing_conv.suppressed = True
                    existing_conv.suppressed_by = f"PR review: {pr_url}"
                    logger.info(f"[FeedbackExtractor] Suppressed base convention: {rule[:60]}")
                elif not is_rejection:
                    existing_conv.frequency += 1
                    existing_conv.confidence = min(1.0, existing_conv.confidence * 1.1)
                    if pr_url not in (existing_conv.source_prs or []):
                        prs = list(existing_conv.source_prs or [])
                        prs.append(pr_url)
                        existing_conv.source_prs = prs[-20:]
                    # Track who enforces this convention
                    current_enforcers = set(existing_conv.enforced_by or [])
                    current_enforcers.update(enforcers)
                    existing_conv.enforced_by = list(current_enforcers)[:20]
                updated += 1
            else:
                if not is_rejection:
                    new_conv = Convention(
                        org_id=org_id,
                        rule=rule,
                        category=category,
                        examples=[],
                        frequency=1,
                        confidence=0.4,
                        layer="customer",
                        source_prs=[pr_url],
                        enforced_by=enforcers,
                    )
                    db.add(new_conv)
                    updated += 1
                    logger.info(f"[FeedbackExtractor] New convention from {enforcers}: {rule[:60]}")

        await db.commit()

    logger.info(f"[FeedbackExtractor] Processed {len(extracted)} conventions, {updated} updated/created")
    return updated
