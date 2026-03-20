"""Convention extraction pipeline.

Orchestrates: fetch merged PRs → extract conventions per PR → deduplicate → score → store.
Runs as a Celery background task, not part of the per-task agent pipeline.
"""
import asyncio
import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.convention import Convention
from app.models.org import OnboardingConfig
from app.services.github_service import fetch_merged_prs
from app.services.convention_extractor import (
    extract_conventions_from_pr,
    deduplicate_conventions,
    score_conventions,
)

logger = logging.getLogger(__name__)


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

    # Step 1: Fetch merged PRs
    logger.info(f"[ConventionPipeline] Org {org_id}: fetching up to {pr_count} merged PRs")
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
            current_deduped = deduplicate_conventions(all_conventions)
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
    deduped = deduplicate_conventions(all_conventions)
    logger.info(f"[ConventionPipeline] Org {org_id}: {len(all_conventions)} raw → {len(deduped)} deduplicated")

    # Step 4: Score
    scored = score_conventions(deduped)

    # Step 5: Store — upsert into conventions table
    stored = 0
    async with AsyncSessionLocal() as db:
        for c in scored:
            # Check if a similar convention already exists for this org
            existing = await db.execute(
                select(Convention).where(
                    Convention.org_id == org_id,
                    Convention.rule == c["rule"],
                    Convention.suppressed == False,  # noqa: E712
                )
            )
            existing_conv = existing.scalar_one_or_none()

            if existing_conv:
                # Update frequency and confidence
                existing_conv.frequency = max(existing_conv.frequency, c["frequency"])
                existing_conv.confidence = max(existing_conv.confidence, c["confidence"])
                if c.get("examples"):
                    current_examples = existing_conv.examples or []
                    merged = list(set(current_examples + c["examples"]))[:5]  # cap at 5 examples
                    existing_conv.examples = merged
                if c.get("source_prs"):
                    current_prs = existing_conv.source_prs or []
                    merged = list(set(current_prs + c["source_prs"]))[:20]
                    existing_conv.source_prs = merged
                if c.get("source_files"):
                    current_files = set(existing_conv.source_files or [])
                    current_files.update(c["source_files"])
                    existing_conv.source_files = list(current_files)[:50]  # cap at 50 unique files
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

    logger.info(f"[ConventionPipeline] Org {org_id}: stored {stored} new conventions, updated existing")
    return stored


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
            current_deduped = deduplicate_conventions(all_conventions)
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

    deduped = deduplicate_conventions(all_conventions)
    scored = score_conventions(deduped)

    logger.info(f"[BaseConventions] {len(all_conventions)} raw → {len(deduped)} deduped → storing")

    stored = 0
    async with AsyncSessionLocal() as db:
        for c in scored:
            existing = await db.execute(
                select(Convention).where(
                    Convention.org_id.is_(None),
                    Convention.rule == c["rule"],
                    Convention.layer == "base",
                )
            )
            existing_conv = existing.scalar_one_or_none()

            if existing_conv:
                existing_conv.frequency = max(existing_conv.frequency, c["frequency"])
                existing_conv.confidence = max(existing_conv.confidence, c["confidence"])
            else:
                conv = Convention(
                    org_id=None,  # base convention — no org
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

    logger.info(f"[BaseConventions] Stored {stored} base conventions from {repo_url}")
    return stored
