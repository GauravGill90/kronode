import asyncio
import json
import logging
import os
import re

from app.agents.base import AgentBase

logger = logging.getLogger(__name__)

MAX_TOTAL_BYTES = 30_000   # 30 KB total file content sent to Claude
MAX_FILE_BYTES = 4_000     # 4 KB per individual file
MAX_FILES_TO_SELECT = 12   # max files to select heuristically
MAX_FILES_TO_FETCH = 10    # never fetch more than this


class ContextBuilderAgent(AgentBase):
    display_name = "Context Builder"

    async def run(self, context: dict) -> dict:
        repo_url = context.get("repo_url", "")
        token = context.get("github_access_token")
        description = context.get("description", "")
        priority_exts = context.get("profile_priority_extensions", [])
        cached_conventions = context.get("cached_conventions")

        if not repo_url or not token:
            logger.info("[ContextBuilder] No repo URL or token — returning empty bundle")
            return {
                "summary": "No repo configured — context bundle is empty.",
                "relevant_files": [],
                "conventions": [],
                "repo_structure": "",
            }

        try:
            return await self._build(repo_url, token, description, priority_exts, cached_conventions, context)
        except Exception as exc:
            logger.warning(f"[ContextBuilder] Failed: {exc}")
            return {
                "summary": f"Context fetch failed ({exc}) — proceeding without repo context.",
                "relevant_files": [],
                "conventions": [],
                "repo_structure": "",
            }

    async def _build(
        self,
        repo_url: str,
        token: str,
        description: str,
        priority_exts: list[str],
        cached_conventions: list[str] | None,
        context: dict,
    ) -> dict:
        from app.services.github_service import get_repo_tree, get_file_content

        # 1. Get full repo file tree
        all_paths = await get_repo_tree(repo_url, token)
        if not all_paths:
            return {
                "summary": "Repo tree is empty.",
                "relevant_files": [],
                "conventions": [],
                "repo_structure": "",
            }

        repo_structure_summary = _summarise_tree(all_paths)

        # 2a. Load previously touched file paths for this org (boosts file selection)
        from app.core.database import AsyncSessionLocal
        from app.models.memory import MemoryRecord
        from sqlalchemy import select as sa_select

        org_id = context.get("org_id")
        previously_touched: set[str] = set()
        if org_id:
            try:
                async with AsyncSessionLocal() as db:
                    rows = (await db.execute(
                        sa_select(MemoryRecord.content)
                        .where(
                            MemoryRecord.org_id == org_id,
                            MemoryRecord.record_type == "file_touched",
                        )
                        .order_by(MemoryRecord.id.desc())
                        .limit(100)
                    )).scalars().all()
                    for c in rows:
                        if isinstance(c, dict) and c.get("path"):
                            previously_touched.add(c["path"])
                logger.info(f"[ContextBuilder] {len(previously_touched)} previously-touched paths loaded")
            except Exception as exc:
                logger.warning(f"[ContextBuilder] Could not load file_touched records: {exc}")

        # 2b. Deterministic file selection — no LLM call, profile + memory boost applied
        selected_paths = _heuristic_select(
            description, all_paths,
            priority_exts=priority_exts,
            previously_touched=previously_touched,
        )
        logger.info(f"[ContextBuilder] Heuristic selected {len(selected_paths)} files (priority_exts={priority_exts})")

        # 3. Fetch file contents concurrently (capped)
        fetch_tasks = [
            get_file_content(repo_url, p, token)
            for p in selected_paths[:MAX_FILES_TO_FETCH]
        ]
        raw_contents = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        relevant_files: list[dict] = []
        total_bytes = 0
        for path, content in zip(selected_paths, raw_contents):
            if isinstance(content, Exception) or content is None:
                continue
            # Truncate individual file
            if len(content) > MAX_FILE_BYTES:
                content = content[:MAX_FILE_BYTES] + "\n… [truncated]"
            if total_bytes + len(content) > MAX_TOTAL_BYTES:
                break
            relevant_files.append({"path": path, "content": content})
            total_bytes += len(content)

        # 4. Ask cheap LLM which convention categories matter for this task
        category_boost = await _get_category_relevance(description)

        # 5. Load conventions from DB (structured convention table)
        conventions = []
        pitfalls = []
        reviewer_patterns = []
        try:
            from app.models.convention import Convention
            # Detect org's stack for base convention filtering
            org_stack = None
            async with AsyncSessionLocal() as db:
                if org_id:
                    from app.models.org import OnboardingConfig as OC
                    oc = (await db.execute(sa_select(OC).where(OC.org_id == org_id))).scalar_one_or_none()
                    if oc:
                        org_stack = oc.docs_scope  # stores detected primary stack

            async with AsyncSessionLocal() as db:
                # Load all customer conventions + base conventions matching org's stack
                query = sa_select(Convention).where(
                    Convention.suppressed == False,  # noqa: E712
                )
                if org_stack:
                    # Customer conventions for this org + base conventions matching stack
                    query = query.where(
                        (Convention.org_id == org_id) |
                        ((Convention.org_id.is_(None)) & ((Convention.stack == org_stack) | (Convention.stack.is_(None))))
                    )
                else:
                    query = query.where(
                        (Convention.org_id == org_id) | (Convention.org_id.is_(None))
                    )
                conv_rows = (await db.execute(query)).scalars().all()

                # Score each convention for relevance to THIS task
                conventions = await _rank_conventions(
                    conv_rows,
                    description=description,
                    selected_paths=selected_paths,
                    category_boost=category_boost,
                    max_conventions=30,
                )
                logger.info(f"[ContextBuilder] {len(conv_rows)} total conventions → {len(conventions)} relevant selected")
        except Exception as exc:
            logger.warning(f"[ContextBuilder] Convention table query failed: {exc}")

        # Fall back to Haiku extraction if convention table is empty
        if not conventions:
            if cached_conventions:
                conventions = [{"rule": c, "category": "style", "confidence": 0.5, "layer": "unknown", "source_prs": []} for c in cached_conventions]
                logger.info(f"[ContextBuilder] Using {len(conventions)} cached conventions (fallback)")
            else:
                raw_conventions = await self._extract_conventions(relevant_files, repo_structure_summary)
                conventions = [{"rule": c, "category": "style", "confidence": 0.5, "layer": "extracted", "source_prs": []} for c in raw_conventions]
                context["new_conventions"] = raw_conventions

        # 5. Load pitfalls for selected files
        selected_path_set = set(selected_paths)
        if org_id:
            try:
                async with AsyncSessionLocal() as db:
                    pitfall_rows = (await db.execute(
                        sa_select(MemoryRecord)
                        .where(
                            MemoryRecord.org_id == org_id,
                            MemoryRecord.record_type == "pitfall",
                        )
                        .order_by(MemoryRecord.id.desc())
                        .limit(50)
                    )).scalars().all()
                    for r in pitfall_rows:
                        content = r.content or {}
                        pitfall_files = set(content.get("files_changed", []))
                        if pitfall_files & selected_path_set:
                            # Handle both old (str) and new ({body, reviewer}) comment formats
                            comments = content.get("review_comments", [])
                            desc_parts = []
                            reviewers = content.get("reviewers", [])
                            for c in comments:
                                if isinstance(c, dict):
                                    reviewer = c.get("reviewer", "")
                                    body = c.get("body", "")
                                    desc_parts.append(f"{reviewer}: {body}" if reviewer else body)
                                else:
                                    desc_parts.append(str(c))
                            pitfalls.append({
                                "description": "; ".join(desc_parts)[:200],
                                "reviewers": reviewers,
                                "files": list(pitfall_files & selected_path_set),
                                "pr_url": content.get("pr_url", ""),
                            })
                    logger.info(f"[ContextBuilder] Loaded {len(pitfalls)} relevant pitfalls")
            except Exception as exc:
                logger.warning(f"[ContextBuilder] Pitfall query failed: {exc}")

        # 6. Load reviewer patterns
        if org_id:
            try:
                async with AsyncSessionLocal() as db:
                    pattern_rows = (await db.execute(
                        sa_select(MemoryRecord)
                        .where(
                            MemoryRecord.org_id == org_id,
                            MemoryRecord.record_type == "pattern",
                        )
                        .order_by(MemoryRecord.id.desc())
                        .limit(20)
                    )).scalars().all()
                    for r in pattern_rows:
                        content = r.content or {}
                        reviewer = content.get("reviewer", "")
                        changes = content.get("changes_requested", [])
                        if changes:
                            reviewer_patterns.append({
                                "reviewer": reviewer,
                                "preference": changes[0][:200] if changes else "",
                                "source": content.get("description", "")[:100],
                            })

                # Also load per-reviewer conventions from the conventions table
                async with AsyncSessionLocal() as db:
                    enforced_convs = (await db.execute(
                        sa_select(Convention)
                        .where(
                            Convention.org_id == org_id,
                            Convention.enforced_by.isnot(None),
                            Convention.suppressed == False,  # noqa: E712
                        )
                        .order_by(Convention.confidence.desc())
                        .limit(10)
                    )).scalars().all()
                    for c in enforced_convs:
                        enforcers = c.enforced_by or []
                        if enforcers:
                            reviewer_patterns.append({
                                "reviewer": ", ".join(enforcers[:3]),
                                "preference": c.rule[:200],
                                "source": f"enforced across {c.frequency} PR(s)",
                            })
                    logger.info(f"[ContextBuilder] Loaded {len(reviewer_patterns)} reviewer patterns")
            except Exception as exc:
                logger.warning(f"[ContextBuilder] Pattern query failed: {exc}")

        return {
            "summary": (
                f"Fetched {len(relevant_files)} relevant file(s) from repo "
                f"({total_bytes // 1000}KB). "
                f"{len(conventions)} conventions, {len(pitfalls)} pitfalls, "
                f"{len(reviewer_patterns)} reviewer patterns loaded."
            ),
            "relevant_files": relevant_files,
            "conventions": conventions,
            "pitfalls": pitfalls,
            "reviewer_patterns": reviewer_patterns,
            "repo_structure": repo_structure_summary,
        }

    async def _extract_conventions(
        self, files: list[dict], repo_structure: str
    ) -> list[str]:
        """Ask Claude haiku to extract coding conventions from the fetched files."""
        if not files:
            return []

        files_text = "\n\n".join(
            f"=== {f['path']} ===\n{f['content']}" for f in files[:8]
        )
        prompt = f"""Analyse these source files and list the coding conventions used.

Repository structure: {repo_structure}

Files:
{files_text}

Return a JSON array of short strings, each describing one convention.
Examples: "Uses named exports", "TypeScript with strict mode", "Tests in __tests__/ directories",
"CSS modules for styling", "snake_case for Python variables", "Async/await throughout"

Return 5-12 conventions. JSON array only."""

        try:
            from app.core.llm import cheap
            raw = await cheap(system="Extract coding conventions. Return JSON array only.", user_message=prompt, max_tokens=512)
            raw = re.sub(r"\n?```$", "", raw)
            result = json.loads(raw)
            if isinstance(result, list):
                return [str(c) for c in result]
        except Exception as exc:
            logger.warning(f"[ContextBuilder] Convention extraction failed: {exc}")

        return []


# ── Helpers ────────────────────────────────────────────────────────────────────

def _summarise_tree(paths: list[str]) -> str:
    """Build a concise top-level directory summary."""
    dirs: dict[str, int] = {}
    for path in paths:
        top = path.split("/")[0] if "/" in path else "."
        dirs[top] = dirs.get(top, 0) + 1
    top_dirs = sorted(dirs.items(), key=lambda x: -x[1])[:12]
    return ", ".join(f"{d}/ ({n} files)" for d, n in top_dirs)


_SOURCE_EXTS = {".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rb", ".rs", ".java"}
_CONFIG_NAMES = {
    "package.json", "tsconfig.json", "pyproject.toml", "setup.py",
    "Makefile", "Dockerfile", "requirements.txt",
}


def _heuristic_select(
    description: str,
    paths: list[str],
    priority_exts: list[str] = [],
    previously_touched: set[str] = set(),
) -> list[str]:
    """Deterministic file selection: config files + source files scored by description match.
    priority_exts are given a +2 score boost (from the agent profile CONTEXT_PRIORITIES).
    previously_touched paths get a +2 score boost (from memory_records)."""
    desc_words = {w.lower() for w in re.split(r'\W+', description) if len(w) > 3}
    scored: list[tuple[int, str]] = []
    for p in paths:
        name = os.path.basename(p)
        ext = os.path.splitext(p)[1]
        score = 0
        if name in _CONFIG_NAMES:
            score += 3
        elif ext in _SOURCE_EXTS:
            score += 1
        if priority_exts and ext in priority_exts:
            score += 2  # profile extension boost
        if previously_touched and p in previously_touched:
            score += 2  # memory boost — touched in a previous task
        if any(w in p.lower() for w in desc_words):
            score += 2
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:MAX_FILES_TO_SELECT]]


# Keywords that indicate a convention's category is relevant to certain file patterns
_CATEGORY_FILE_HINTS = {
    "testing": {"test", "spec", "__tests__", "tests", "vitest", "jest"},
    "error_handling": {"error", "exception", "catch", "try", "handler", "middleware"},
    "logging": {"log", "logger", "logging", "sentry", "monitor"},
    "naming": set(),  # always relevant
    "style": set(),   # always relevant
    "architecture": set(),  # always relevant
}


async def _get_category_relevance(description: str) -> dict[str, float]:
    """Ask cheap LLM which convention categories are most relevant for this task.

    Returns a dict of category -> boost multiplier (1.0 = neutral, 2.0 = very relevant).
    Falls back to uniform weights if LLM fails.
    """
    try:
        from app.core.llm import cheap
        raw = await cheap(
            system=(
                'Given a task description, rate how relevant each convention category is on a scale of 1-3. '
                'Categories: architecture, style, naming, error_handling, testing, logging. '
                'Respond with JSON only: {"architecture": 2, "style": 1, ...}'
            ),
            user_message=f"Task: {description}",
            max_tokens=64,
        )
        raw = re.sub(r"^```[a-z]*\n?", "", raw.strip())
        raw = re.sub(r"\n?```$", "", raw)
        # Try direct parse, then extract first JSON object
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{[^}]+\}", raw)
            parsed = json.loads(match.group()) if match else {}
        # Normalise to multipliers: 1->0.5, 2->1.0, 3->2.0
        weights = {
            "architecture": 1.0, "style": 1.0, "naming": 1.0,
            "error_handling": 1.0, "testing": 1.0, "logging": 1.0,
        }
        for cat, val in parsed.items():
            if cat in weights and isinstance(val, (int, float)):
                weights[cat] = {1: 0.5, 2: 1.0, 3: 2.0}.get(int(val), 1.0)
        logger.info(f"[ContextBuilder] Category relevance: {weights}")
        return weights
    except Exception as exc:
        logger.warning(f"[ContextBuilder] Category relevance LLM failed: {exc} — using uniform weights")
        return {}


async def _rank_conventions(
    conv_rows: list,
    description: str,
    selected_paths: list[str],
    category_boost: dict[str, float] | None = None,
    max_conventions: int = 30,
) -> list[dict]:
    """Score and rank conventions by relevance to this specific task.

    Scoring (5 signals):
    1. Customer > base (team-specific conventions always prioritised)
    2. Keyword match between convention rule and task description
    3. Category relevance from LLM (which categories matter for this task)
    4. File path match: convention extracted from files we're touching
    5. Semantic similarity: embedding cosine distance between task and convention rule

    Returns top max_conventions as dicts.
    """
    if category_boost is None:
        category_boost = {}

    # Compute semantic embeddings (task description + all convention rules)
    semantic_scores: dict[int, float] = {}  # conv index -> similarity score
    try:
        from app.core.embeddings import get_embedding, get_embeddings_batch, cosine_similarity
        task_emb = await get_embedding(description)
        if task_emb:
            rule_texts = [c.rule for c in conv_rows]
            rule_embs = await get_embeddings_batch(rule_texts)
            for idx, emb in enumerate(rule_embs):
                if emb:
                    semantic_scores[idx] = cosine_similarity(task_emb, emb)
        if semantic_scores:
            logger.info(f"[ContextBuilder] Semantic matching: {len(semantic_scores)} conventions scored")
    except Exception as exc:
        logger.warning(f"[ContextBuilder] Semantic matching failed: {exc} — using keyword only")
    desc_lower = description.lower()
    desc_words = {w for w in re.split(r'\W+', desc_lower) if len(w) > 3}

    # Build a set of directory/file signals from selected paths
    path_words = set()
    path_dirs = set()
    for p in selected_paths:
        parts = p.lower().replace("\\", "/").split("/")
        path_words.update(parts)
        path_dirs.update(parts[:-1])  # directories only
        # Add filename without extension
        name = os.path.splitext(parts[-1])[0]
        path_words.update(w for w in re.split(r'[\W_]+', name) if len(w) > 2)

    scored: list[tuple[float, dict]] = []

    for c in conv_rows:
        score = 0.0
        rule_lower = c.rule.lower()
        rule_words = {w for w in re.split(r'\W+', rule_lower) if len(w) > 3}

        # 1. Layer boost: customer conventions are more specific
        if c.layer == "customer":
            score += 2.0
        else:
            score += 0.5

        # 2. Keyword overlap between convention rule and task description
        overlap = desc_words & rule_words
        score += len(overlap) * 1.5

        # 3. Category relevance (LLM-ranked + file hint matching)
        cat_mult = category_boost.get(c.category, 1.0)
        cat_hints = _CATEGORY_FILE_HINTS.get(c.category, set())
        if cat_hints and (cat_hints & path_words):
            score += 2.0 * cat_mult  # e.g., testing convention + test file + LLM says testing matters
        elif not cat_hints:
            score += 0.5 * cat_mult  # style/naming/architecture weighted by LLM relevance
        else:
            score += 0.3 * cat_mult

        # 4. Rule text matches file paths or directories
        path_overlap = path_words & rule_words
        score += len(path_overlap) * 1.0

        # 5. Source files match (strongest signal — this convention came from these exact files/dirs)
        conv_files = set(c.source_files or [])
        if conv_files:
            # Direct file match: convention extracted from a file we're touching
            direct_match = conv_files & set(selected_paths)
            if direct_match:
                score += 5.0  # very strong — same file

            # Directory match: convention from files in the same directory
            conv_dirs = {f.rsplit("/", 1)[0] for f in conv_files if "/" in f}
            selected_dirs = {p.rsplit("/", 1)[0] for p in selected_paths if "/" in p}
            dir_match = conv_dirs & selected_dirs
            if dir_match and not direct_match:
                score += 3.0  # strong — same directory

        # 6. Semantic similarity (embedding cosine distance)
        conv_idx = conv_rows.index(c)
        sem_score = semantic_scores.get(conv_idx, 0.0)
        if sem_score > 0.3:  # only boost if meaningfully similar
            score += sem_score * 4.0  # max ~4.0 for perfect semantic match

        # 7. Frequency + confidence as tiebreaker
        score += c.confidence * 0.5
        score += min(c.frequency * 0.1, 1.0)  # cap at 1.0

        scored.append((score, {
            "rule": c.rule,
            "category": c.category,
            "confidence": c.confidence,
            "layer": c.layer,
            "source_prs": c.source_prs or [],
            "relevance_score": round(score, 2),
        }))

    # Sort by relevance score descending
    scored.sort(key=lambda x: -x[0])

    # Always include ALL customer conventions (they're team-specific, never skip)
    customer = [(s, d) for s, d in scored if d["layer"] == "customer"]
    base = [(s, d) for s, d in scored if d["layer"] == "base"]

    # Take all customer + fill remaining slots with top-scoring base
    result = [d for _, d in customer]
    remaining = max_conventions - len(result)
    result.extend(d for _, d in base[:remaining])

    return result
