"""Convention extraction pipeline.

Orchestrates: fetch merged PRs → extract conventions per PR → deduplicate → score → store.
Runs as a Celery background task, not part of the per-task agent pipeline.
"""
import asyncio
import json
import logging
import re

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.convention import Convention
from app.models.org import OnboardingConfig
from app.services.convention_extractor import (
    extract_conventions_from_pr,
    deduplicate_conventions,
    score_conventions,
)

logger = logging.getLogger(__name__)


MIN_FREQUENCY = 2  # Convention must be seen in 2+ PRs to be stored


async def run_extraction(org_id: int, pr_count: int = 200) -> int:
    """Run convention extraction for an org. Returns number of conventions stored."""

    # Load org config
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
        )
        config = result.scalar_one_or_none()

    if not config or not config.repo_url or not config.github_access_token:
        logger.warning(f"[ConventionPipeline] Org {org_id}: no repo or token configured — skipping")
        return 0

    # Step 1: Fetch merged PRs (route to correct provider)
    logger.info(f"[ConventionPipeline] Org {org_id}: fetching up to {pr_count} merged PRs (provider={config.repo_provider})")
    if config.repo_provider == "bitbucket":
        from app.services.bitbucket_service import fetch_merged_prs
    else:
        from app.services.github_service import fetch_merged_prs
    prs = await fetch_merged_prs(
        repo_url=config.repo_url,
        token=config.github_access_token,
        count=pr_count,
    )

    if not prs:
        logger.info(f"[ConventionPipeline] Org {org_id}: no merged PRs found")
        return 0

    logger.info(f"[ConventionPipeline] Org {org_id}: fetched {len(prs)} PRs, extracting conventions...")

    # Step 2: Extract conventions from each PR (with rate limiting)
    all_conventions: list[dict] = []
    for i, pr in enumerate(prs):
        conventions = await extract_conventions_from_pr(pr)
        for c in conventions:
            c["source_prs"] = [pr.get("url", "")]
            c["frequency"] = 1
        all_conventions.extend(conventions)

        # Log progress every 20 PRs
        if (i + 1) % 20 == 0:
            # Check dedup rate — stop early if we're seeing diminishing returns
            current_deduped = await deduplicate_conventions(all_conventions)
            dedup_rate = 1 - (len(current_deduped) / len(all_conventions)) if all_conventions else 0
            logger.info(
                f"[ConventionPipeline] Org {org_id}: processed {i + 1}/{len(prs)} PRs, "
                f"{len(all_conventions)} raw, {len(current_deduped)} unique, dedup_rate={dedup_rate:.0%}"
            )
            if dedup_rate > 0.8 and len(current_deduped) >= 20:
                logger.info(f"[ConventionPipeline] Org {org_id}: dedup rate {dedup_rate:.0%} > 80% — stopping early (diminishing returns)")
                break

        # Rate limiting: short pause every 10 PRs to avoid API throttling
        if (i + 1) % 10 == 0:
            await asyncio.sleep(1)

    if not all_conventions:
        logger.info(f"[ConventionPipeline] Org {org_id}: no conventions extracted from {len(prs)} PRs")
        return 0

    # Step 3: Deduplicate
    deduped = await deduplicate_conventions(all_conventions)
    logger.info(f"[ConventionPipeline] Org {org_id}: {len(all_conventions)} raw → {len(deduped)} deduplicated")

    # Step 4: Score and filter
    scored = score_conventions(deduped)
    pre_filter = len(scored)
    scored = [c for c in scored if c.get("frequency", 1) >= MIN_FREQUENCY]
    logger.info(f"[ConventionPipeline] Org {org_id}: {pre_filter} scored → {len(scored)} above frequency threshold ({MIN_FREQUENCY}+)")

    # Step 5: Store — semantic upsert into conventions table
    stored = 0
    updated = 0
    async with AsyncSessionLocal() as db:
        # Load existing conventions for semantic matching
        existing_rows = (await db.execute(
            select(Convention).where(
                Convention.org_id == org_id,
                Convention.suppressed == False,  # noqa: E712
            )
        )).scalars().all()

        # Build embeddings for semantic matching
        existing_rules = [r.rule for r in existing_rows]
        new_rules = [c["rule"] for c in scored]

        try:
            from app.core.embeddings import get_embeddings_batch, cosine_similarity
            all_embeddings = await get_embeddings_batch(existing_rules + new_rules)
            existing_embs = all_embeddings[:len(existing_rules)]
            new_embs = all_embeddings[len(existing_rules):]
            use_semantic = any(e is not None for e in existing_embs + new_embs)
        except Exception:
            use_semantic = False
            existing_embs = []
            new_embs = []

        for i, c in enumerate(scored):
            # Find best matching existing convention
            best_match = None
            best_sim = 0.0

            if use_semantic and new_embs[i] is not None:
                for j, existing_conv in enumerate(existing_rows):
                    if existing_embs[j] is None:
                        continue
                    sim = cosine_similarity(new_embs[i], existing_embs[j])
                    if sim > best_sim:
                        best_sim = sim
                        best_match = existing_conv

            # Also check exact text match as fallback
            if best_sim < 0.85:
                for existing_conv in existing_rows:
                    if existing_conv.rule == c["rule"]:
                        best_match = existing_conv
                        best_sim = 1.0
                        break

            if best_match and best_sim >= 0.85:
                # Update existing convention
                best_match.frequency = best_match.frequency + c.get("frequency", 1)
                best_match.confidence = max(best_match.confidence, c.get("confidence", 0.5))
                # Keep higher-frequency rule text
                if c.get("frequency", 1) > best_match.frequency - c.get("frequency", 1):
                    best_match.rule = c["rule"]
                if c.get("examples"):
                    current_examples = best_match.examples or []
                    merged = list(set(current_examples + c["examples"]))[:5]
                    best_match.examples = merged
                if c.get("source_prs"):
                    current_prs = best_match.source_prs or []
                    merged = list(set(current_prs + c["source_prs"]))[:20]
                    best_match.source_prs = merged
                if c.get("source_files"):
                    current_files = set(best_match.source_files or [])
                    current_files.update(c["source_files"])
                    best_match.source_files = list(current_files)[:50]
                updated += 1
            else:
                conv = Convention(
                    org_id=org_id,
                    rule=c["rule"],
                    category=c.get("category", "style"),
                    examples=c.get("examples", []),
                    frequency=c.get("frequency", 1),
                    confidence=c.get("confidence", 0.5),
                    layer="customer",
                    source_prs=c.get("source_prs", []),
                    source_files=c.get("source_files", []),
                )
                db.add(conv)
                stored += 1

        await db.commit()

    logger.info(f"[ConventionPipeline] Org {org_id}: {stored} new, {updated} updated (semantic match)")

    # Step 6: Extract reviewer-specific patterns from attributed comments
    await _extract_reviewer_patterns(org_id, prs, db_session=None)

    return stored


REVIEWER_PATTERN_PROMPT = """You are extracting a specific reviewer's enforcement patterns from their PR review comments.

Given all review comments from one reviewer across multiple PRs, identify recurring themes they enforce.

For each pattern, provide:
- rule: what this reviewer consistently asks for (be specific, reference file paths or tools if mentioned)
- category: one of naming, error_handling, testing, logging, architecture, style

Only include patterns that appear in 2+ comments. Skip one-off feedback.

Respond with ONLY a JSON object. No markdown.

{"conventions": [{"rule": "Reviewer requires error boundaries around async components in apps/web/", "category": "error_handling"}]}

If no recurring patterns found: {"conventions": []}
"""


async def _extract_reviewer_patterns(org_id: int, prs: list[dict], db_session=None) -> int:
    """Extract reviewer-specific conventions from attributed PR comments."""
    # Group comments by reviewer
    reviewer_comments: dict[str, list[str]] = {}
    for pr in prs:
        for comment in pr.get("attributed_comments", []):
            reviewer = comment.get("reviewer", "")
            body = comment.get("body", "").strip()
            if reviewer and body and not reviewer.endswith("[bot]"):
                reviewer_comments.setdefault(reviewer, []).append(body)

    if not reviewer_comments:
        logger.info(f"[ConventionPipeline] Org {org_id}: no attributed comments for reviewer patterns")
        return 0

    MIN_COMMENTS = 5
    extracted = 0

    for reviewer, comments in reviewer_comments.items():
        if len(comments) < MIN_COMMENTS:
            continue

        # Send aggregated comments to LLM
        comment_text = "\n".join(f"- {c[:300]}" for c in comments[:20])
        user_message = f"Reviewer: {reviewer}\nReview comments ({len(comments)} total, showing up to 20):\n{comment_text}"

        try:
            from app.core.llm import cheap
            raw = await cheap(system=REVIEWER_PATTERN_PROMPT, user_message=user_message, max_tokens=512)
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            parsed = json.loads(raw)
            conventions = parsed.get("conventions", [])

            async with AsyncSessionLocal() as db:
                for c in conventions:
                    if not c.get("rule"):
                        continue
                    # Check if this reviewer pattern already exists
                    existing = await db.execute(
                        select(Convention).where(
                            Convention.org_id == org_id,
                            Convention.rule == c["rule"],
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue

                    conv = Convention(
                        org_id=org_id,
                        rule=c["rule"],
                        category=c.get("category", "style"),
                        frequency=len(comments),
                        confidence=min(0.5 + len(comments) * 0.05, 0.95),
                        layer="customer",
                        enforced_by=[reviewer],
                    )
                    db.add(conv)
                    extracted += 1
                await db.commit()

            logger.info(f"[ConventionPipeline] Org {org_id}: extracted {len(conventions)} patterns from reviewer {reviewer}")

        except Exception as exc:
            logger.warning(f"[ConventionPipeline] Reviewer pattern extraction failed for {reviewer}: {exc}")

    logger.info(f"[ConventionPipeline] Org {org_id}: {extracted} total reviewer patterns stored")
    return extracted


async def run_base_extraction(
    repo_url: str = "https://github.com/calcom/cal.com",
    github_token: str = "",
    pr_count: int = 200,
    stack: str = "typescript",
) -> int:
    """Extract base conventions from an open-source repo (e.g. Cal.com).

    Base conventions have org_id=NULL, layer="base". They apply to all orgs
    on the same stack as a starting point. Customer conventions override them.
    """
    if not github_token:
        from app.core.config import settings
        # Try to use any org's GitHub token (works for public repos)
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(OnboardingConfig.github_access_token)
                .where(OnboardingConfig.github_access_token.isnot(None))
                .limit(1)
            )
            token = result.scalar_one_or_none()
            if token:
                github_token = token

    if not github_token:
        logger.warning("[BaseConventions] No GitHub token available — cannot fetch PRs")
        return 0

    logger.info(f"[BaseConventions] Extracting from {repo_url}, {pr_count} PRs")

    prs = await fetch_merged_prs(repo_url=repo_url, token=github_token, count=pr_count)
    if not prs:
        logger.info("[BaseConventions] No merged PRs found")
        return 0

    all_conventions: list[dict] = []
    for i, pr in enumerate(prs):
        conventions = await extract_conventions_from_pr(pr)
        for c in conventions:
            c["source_prs"] = [pr.get("url", "")]
            c["frequency"] = 1
        all_conventions.extend(conventions)

        if (i + 1) % 20 == 0:
            current_deduped = await deduplicate_conventions(all_conventions)
            dedup_rate = 1 - (len(current_deduped) / len(all_conventions)) if all_conventions else 0
            logger.info(
                f"[BaseConventions] Processed {i + 1}/{len(prs)} PRs, "
                f"{len(all_conventions)} raw, {len(current_deduped)} unique, dedup_rate={dedup_rate:.0%}"
            )
            if dedup_rate > 0.8 and len(current_deduped) >= 30:
                logger.info(f"[BaseConventions] dedup rate {dedup_rate:.0%} > 80% — stopping early")
                break
        if (i + 1) % 10 == 0:
            await asyncio.sleep(1)

    if not all_conventions:
        return 0

    deduped = await deduplicate_conventions(all_conventions)
    scored = score_conventions(deduped)
    pre_filter = len(scored)
    scored = [c for c in scored if c.get("frequency", 1) >= MIN_FREQUENCY]

    logger.info(f"[BaseConventions] {len(all_conventions)} raw → {len(deduped)} deduped → {len(scored)} above threshold (from {pre_filter}) → storing")

    stored = 0
    updated = 0
    async with AsyncSessionLocal() as db:
        # Load existing base conventions for semantic matching
        existing_rows = (await db.execute(
            select(Convention).where(
                Convention.org_id.is_(None),
                Convention.layer == "base",
            )
        )).scalars().all()

        existing_rules = [r.rule for r in existing_rows]
        new_rules = [c["rule"] for c in scored]

        try:
            from app.core.embeddings import get_embeddings_batch, cosine_similarity
            all_embeddings = await get_embeddings_batch(existing_rules + new_rules)
            existing_embs = all_embeddings[:len(existing_rules)]
            new_embs = all_embeddings[len(existing_rules):]
            use_semantic = any(e is not None for e in existing_embs + new_embs)
        except Exception:
            use_semantic = False
            existing_embs = []
            new_embs = []

        for i, c in enumerate(scored):
            best_match = None
            best_sim = 0.0

            if use_semantic and new_embs[i] is not None:
                for j, existing_conv in enumerate(existing_rows):
                    if existing_embs[j] is None:
                        continue
                    sim = cosine_similarity(new_embs[i], existing_embs[j])
                    if sim > best_sim:
                        best_sim = sim
                        best_match = existing_conv

            if best_sim < 0.85:
                for existing_conv in existing_rows:
                    if existing_conv.rule == c["rule"]:
                        best_match = existing_conv
                        best_sim = 1.0
                        break

            if best_match and best_sim >= 0.85:
                best_match.frequency = best_match.frequency + c.get("frequency", 1)
                best_match.confidence = max(best_match.confidence, c.get("confidence", 0.5))
                updated += 1
            else:
                conv = Convention(
                    org_id=None,
                    rule=c["rule"],
                    category=c.get("category", "style"),
                    examples=c.get("examples", []),
                    frequency=c.get("frequency", 1),
                    confidence=c.get("confidence", 0.5),
                    layer="base",
                    stack=stack,
                    source_prs=c.get("source_prs", []),
                    source_files=c.get("source_files", []),
                )
                db.add(conv)
                stored += 1

        await db.commit()

    logger.info(f"[BaseConventions] {stored} new, {updated} updated (semantic match) from {repo_url}")
    return stored


async def reset_and_reextract(org_id: int, pr_count: int = 200) -> int:
    """Delete all non-suppressed customer conventions for an org and re-extract from scratch."""
    from sqlalchemy import delete

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(Convention).where(
                Convention.org_id == org_id,
                Convention.layer == "customer",
                Convention.suppressed == False,  # noqa: E712 — preserve suppressed (explicit team decisions)
            )
        )
        deleted = result.rowcount
        await db.commit()

    logger.info(f"[ConventionReset] Org {org_id}: deleted {deleted} customer conventions, re-extracting...")
    stored = await run_extraction(org_id, pr_count)
    logger.info(f"[ConventionReset] Org {org_id}: re-extraction complete — {stored} new conventions")
    return stored


async def reset_base_conventions(repo_url: str = "https://github.com/calcom/cal.com", pr_count: int = 200, stack: str = "typescript") -> int:
    """Delete all base conventions and re-extract from a reference repo."""
    from sqlalchemy import delete

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            delete(Convention).where(Convention.layer == "base")
        )
        deleted = result.rowcount
        await db.commit()

    logger.info(f"[BaseConventionReset] Deleted {deleted} base conventions, re-extracting from {repo_url}...")
    stored = await run_base_extraction(repo_url=repo_url, pr_count=pr_count, stack=stack)
    logger.info(f"[BaseConventionReset] Re-extraction complete — {stored} new base conventions")
    return stored
