"""Self-onboarding pipeline.

Triggered when a repo is connected. Automatically analyses PR history,
detects stack, extracts conventions, and builds initial org context.
"""
import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.org import OnboardingConfig
from app.models.memory import MemoryRecord
# Provider-specific imports resolved at runtime based on config.repo_provider

logger = logging.getLogger(__name__)

# Known config files that indicate stack
STACK_INDICATORS = {
    "package.json": "Node.js / JavaScript",
    "tsconfig.json": "TypeScript",
    "pyproject.toml": "Python",
    "requirements.txt": "Python",
    "Cargo.toml": "Rust",
    "go.mod": "Go",
    "Gemfile": "Ruby",
    "pom.xml": "Java (Maven)",
    "build.gradle": "Java/Kotlin (Gradle)",
    "Podfile": "iOS (CocoaPods)",
    "Makefile": "Makefile present",
    "Dockerfile": "Docker",
    "docker-compose.yml": "Docker Compose",
    ".github/workflows": "GitHub Actions CI",
}

FRAMEWORK_INDICATORS = {
    "next.config": "Next.js",
    "nuxt.config": "Nuxt",
    "vite.config": "Vite",
    "tailwind.config": "Tailwind CSS",
    "prisma/schema.prisma": "Prisma ORM",
    "alembic/": "Alembic migrations",
    "app/main.py": "FastAPI",
    "manage.py": "Django",
}

# Map detected stack indicators to a primary stack tag for convention filtering
_STACK_MAP = {
    "TypeScript": "typescript",
    "Node.js / JavaScript": "typescript",  # close enough for convention purposes
    "Python": "python",
    "Go": "go",
    "Rust": "rust",
    "Ruby": "ruby",
    "Java (Maven)": "java",
    "Java/Kotlin (Gradle)": "java",
}


def _detect_primary_stack(detected_stack: list[str]) -> str:
    """Determine the primary stack tag from detected indicators."""
    for indicator in detected_stack:
        if indicator in _STACK_MAP:
            return _STACK_MAP[indicator]
    return "unknown"


async def run_onboarding(org_id: int) -> None:
    """Run self-onboarding for an org. Analyses repo and triggers convention extraction."""

    # Load config
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
        )
        config = result.scalar_one_or_none()

    if not config or not config.repo_url or not config.github_access_token:
        logger.warning(f"[SelfOnboarding] Org {org_id}: no repo or token — skipping")
        return

    logger.info(f"[SelfOnboarding] Starting for org {org_id}, repo={config.repo_url}")

    # Step 1: Analyse repo structure and detect stack
    try:
        from app.services.git_providers import get_git_provider
        git = get_git_provider(config.repo_provider or "github")
        all_paths = await git.get_repo_tree(config.repo_url, config.github_access_token)
    except Exception as exc:
        logger.warning(f"[SelfOnboarding] Failed to fetch repo tree: {exc}")
        return

    detected_stack = []
    detected_frameworks = []

    for path in all_paths:
        basename = path.split("/")[-1]
        if basename in STACK_INDICATORS:
            detected_stack.append(STACK_INDICATORS[basename])
        for pattern, framework in FRAMEWORK_INDICATORS.items():
            if pattern in path:
                if framework not in detected_frameworks:
                    detected_frameworks.append(framework)

    stack_summary = ", ".join(sorted(set(detected_stack))) if detected_stack else "Unknown"
    framework_summary = ", ".join(detected_frameworks) if detected_frameworks else "None detected"
    primary_stack = _detect_primary_stack(detected_stack)

    logger.info(f"[SelfOnboarding] Org {org_id}: stack={stack_summary}, primary={primary_stack}, frameworks={framework_summary}")

    # Step 2: Analyse PR review patterns (who reviews what, common feedback)
    try:
        from app.services.git_providers import get_git_provider
        git = get_git_provider(config.repo_provider or "github")
        prs = await git.fetch_merged_prs(
            repo_url=config.repo_url,
            token=config.github_access_token,
            count=50,
        )
    except Exception as exc:
        logger.warning(f"[SelfOnboarding] Failed to fetch PRs: {exc}")
        prs = []

    reviewer_stats: dict[str, int] = {}
    common_feedback: list[str] = []
    for pr in prs:
        for reviewer in pr.get("reviewers", []):
            reviewer_stats[reviewer] = reviewer_stats.get(reviewer, 0) + 1
        for comment in pr.get("review_comments", []):
            if len(comment) > 20:  # skip trivial comments
                common_feedback.append(comment[:200])

    # Store reviewer patterns as memory records
    if reviewer_stats:
        async with AsyncSessionLocal() as db:
            for reviewer, count in sorted(reviewer_stats.items(), key=lambda x: -x[1])[:10]:
                record = MemoryRecord(
                    org_id=org_id,
                    record_type="pattern",
                    content={
                        "reviewer": reviewer,
                        "review_count": count,
                        "description": f"Reviewer {reviewer} has reviewed {count} PRs",
                        "changes_requested": [],
                    },
                    source="self_onboarding",
                )
                db.add(record)
            await db.commit()
        logger.info(f"[SelfOnboarding] Stored {min(len(reviewer_stats), 10)} reviewer patterns")

    # Step 3: Enrich project context with auto-detected info
    auto_context = f"Auto-detected stack: {stack_summary}\nFrameworks: {framework_summary}\nFiles: {len(all_paths)}"
    if reviewer_stats:
        top_reviewers = sorted(reviewer_stats.items(), key=lambda x: -x[1])[:5]
        auto_context += "\nTop reviewers: " + ", ".join(f"{r} ({c} PRs)" for r, c in top_reviewers)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(OnboardingConfig).where(OnboardingConfig.org_id == org_id)
        )
        config = result.scalar_one_or_none()
        if config:
            existing = config.project_context or ""
            if "Auto-detected" not in existing:
                config.project_context = f"{existing}\n\n{auto_context}".strip()
            # Store detected stack for convention filtering
            config.docs_scope = primary_stack  # reuse docs_scope field for detected stack
            await db.commit()
            logger.info(f"[SelfOnboarding] Enriched project_context for org {org_id}, stack={primary_stack}")

    # Step 4: Analyse current codebase structure (read key files, extract conventions)
    try:
        await _analyse_codebase_structure(config.repo_url, config.github_access_token, org_id, all_paths, repo_provider=config.repo_provider or "github")
    except Exception as exc:
        logger.warning(f"[SelfOnboarding] Codebase analysis failed: {exc}")

    # Step 5: Ingest documentation from repo (markdown files)
    try:
        from app.services.doc_ingestion import ingest_docs
        doc_source = config.repo_provider if config.repo_provider in ("bitbucket", "gitlab") else "git"
        chunk_count = await ingest_docs(org_id, source_type=doc_source)
        logger.info(f"[SelfOnboarding] Ingested {chunk_count} doc chunks for org {org_id}")
    except Exception as exc:
        logger.warning(f"[SelfOnboarding] Doc ingestion failed (non-blocking): {exc}")

    # Step 6: Trigger PR-based convention extraction (runs as separate Celery task)
    from app.pipeline.task_queue import run_convention_extraction
    run_convention_extraction.delay(org_id, 200)
    logger.info(f"[SelfOnboarding] Queued convention extraction for org {org_id}")

    # Step 7: Post conventions to Slack for team review
    if config.slack_bot_token and config.slack_channel_id:
        try:
            from app.models.convention import Convention
            from sqlalchemy import select as sa_sel
            async with AsyncSessionLocal() as db:
                conv_rows = (await db.execute(
                    sa_sel(Convention)
                    .where(Convention.org_id == org_id, Convention.suppressed == False)  # noqa: E712
                    .order_by(Convention.confidence.desc())
                    .limit(20)
                )).scalars().all()

            if conv_rows:
                from app.services.slack_service import post_conventions_review
                conventions = [{"rule": c.rule, "category": c.category} for c in conv_rows]
                total = len(conv_rows)
                agent_name = config.agent_name or "Kronode"
                await post_conventions_review(
                    channel_id=config.slack_channel_id,
                    conventions=conventions,
                    agent_name=agent_name,
                    bot_token=config.slack_bot_token,
                    total_count=total,
                )
                logger.info(f"[SelfOnboarding] Posted {total} conventions to Slack for review")
        except Exception as exc:
            logger.warning(f"[SelfOnboarding] Slack conventions review post failed: {exc}")

    logger.info(f"[SelfOnboarding] Complete for org {org_id}")


# Key files to read for codebase structure analysis
_STRUCTURE_FILES = [
    "package.json", "tsconfig.json", "pyproject.toml",
    ".eslintrc", ".eslintrc.js", ".eslintrc.json", "eslint.config.js",
    ".prettierrc", ".prettierrc.json",
    "jest.config.ts", "jest.config.js", "vitest.config.ts",
    "Dockerfile", "docker-compose.yml",
    "README.md",
]

_SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rb", ".rs"}


async def _analyse_codebase_structure(
    repo_url: str, token: str, org_id: int, all_paths: list[str], repo_provider: str = "github"
) -> None:
    """Read key config files + sample source files to extract conventions from the current codebase."""
    import os
    from app.services.git_providers import get_git_provider
    git = get_git_provider(repo_provider)
    get_file_content = git.get_file_content
    from app.services.convention_extractor import extract_conventions_from_pr, deduplicate_conventions, score_conventions

    logger.info(f"[SelfOnboarding] Analysing codebase structure for org {org_id}")

    # Collect config files
    files_to_read = []
    for path in all_paths:
        basename = path.split("/")[-1]
        if basename in _STRUCTURE_FILES:
            files_to_read.append(path)

    # Sample a few source files from different directories (max 10)
    dirs_sampled = set()
    for path in all_paths:
        ext = os.path.splitext(path)[1]
        if ext not in _SOURCE_EXTS:
            continue
        parent = path.rsplit("/", 1)[0] if "/" in path else "."
        if parent not in dirs_sampled and len(dirs_sampled) < 10:
            dirs_sampled.add(parent)
            files_to_read.append(path)

    # Fetch contents
    file_contents = []
    for path in files_to_read[:20]:  # cap at 20
        try:
            content = await get_file_content(repo_url, path, token)
            if content and len(content) < 5000:
                file_contents.append(f"--- {path} ---\n{content[:3000]}")
        except Exception:
            continue

    if not file_contents:
        logger.info("[SelfOnboarding] No readable files found for codebase analysis")
        return

    # Create a synthetic "PR" from the codebase snapshot and extract conventions
    synthetic_pr = {
        "title": "Codebase structure analysis",
        "body": "Conventions extracted from current codebase files (not a real PR)",
        "diff": "\n\n".join(file_contents),
        "review_comments": [],
        "files_changed": [p for p in files_to_read[:20]],
    }

    conventions = await extract_conventions_from_pr(synthetic_pr)
    if not conventions:
        logger.info("[SelfOnboarding] No conventions extracted from codebase structure")
        return

    for c in conventions:
        c["source_prs"] = []
        c["frequency"] = 1

    deduped = await deduplicate_conventions(conventions)
    scored = score_conventions(deduped)

    # Store as customer conventions
    stored = 0
    async with AsyncSessionLocal() as db:
        for c in scored:
            from app.models.convention import Convention
            from sqlalchemy import select as sa_sel
            existing = (await db.execute(
                sa_sel(Convention).where(
                    Convention.org_id == org_id,
                    Convention.rule == c["rule"],
                )
            )).scalar_one_or_none()
            if not existing:
                conv = Convention(
                    org_id=org_id,
                    rule=c["rule"],
                    category=c.get("category", "style"),
                    examples=c.get("examples", []),
                    frequency=c.get("frequency", 1),
                    confidence=c.get("confidence", 0.5),
                    layer="customer",
                    source_files=c.get("source_files", []),
                )
                db.add(conv)
                stored += 1
        await db.commit()

    logger.info(f"[SelfOnboarding] Codebase analysis: {stored} conventions extracted from {len(file_contents)} files")
