"""Kronode MCP Server — organizational memory for AI coding tools.

Exposes team conventions, pitfalls, reviewer patterns, and file companion
data as MCP tools that any AI coding agent can call mid-task.
"""
import logging
import os

from mcp.server import FastMCP

logger = logging.getLogger(__name__)

# Org ID is resolved at startup from the API token
_org_id: int | None = None
_repo_url: str | None = None
_github_token: str | None = None

mcp = FastMCP(
    name="kronode",
    instructions=(
        "Kronode provides organizational memory for your engineering team. "
        "Call get_context at the start of any task to get team conventions, "
        "known pitfalls, and reviewer preferences. Call check_completeness "
        "before committing to catch missed files."
    ),
)


def configure(org_id: int, repo_url: str = "", github_token: str = ""):
    """Set org context for this MCP server instance."""
    global _org_id, _repo_url, _github_token
    _org_id = org_id
    _repo_url = repo_url
    _github_token = github_token
    logger.info(f"[KronodeMCP] Configured for org {org_id}, repo {repo_url[:50]}")


@mcp.tool(
    name="get_context",
    description=(
        "Get organizational context for a coding task. Returns team conventions "
        "ranked by relevance, known pitfalls for the files being touched, "
        "reviewer preferences, past failure patterns, and relevant documentation. "
        "Call this at the START of any task before writing code."
    ),
)
async def get_context(task_description: str, files_touched: list[str] | None = None) -> dict:
    """Fetch ranked organizational context for a specific task."""
    from app.core.database import AsyncSessionLocal
    from app.models.convention import Convention
    from app.models.memory import MemoryRecord
    from sqlalchemy import select

    if not _org_id:
        return {"error": "MCP server not configured — missing org_id"}

    async with AsyncSessionLocal() as db:
        # 1. Load conventions
        conv_rows = (await db.execute(
            select(Convention).where(
                Convention.org_id == _org_id,
                Convention.suppressed == False,  # noqa: E712
            )
        )).scalars().all()

        # 2. Rank by relevance to this task
        from app.agents.context_builder import _rank_conventions, _get_category_relevance
        category_boost = await _get_category_relevance(task_description)
        conventions = await _rank_conventions(
            conv_rows,
            description=task_description,
            selected_paths=files_touched or [],
            category_boost=category_boost,
            max_conventions=20,
        )

        # 3. Load pitfalls (file-scoped)
        pitfalls = []
        if files_touched:
            pitfall_rows = (await db.execute(
                select(MemoryRecord).where(
                    MemoryRecord.org_id == _org_id,
                    MemoryRecord.record_type == "pitfall",
                ).order_by(MemoryRecord.id.desc()).limit(30)
            )).scalars().all()

            touched_set = set(files_touched)
            for r in pitfall_rows:
                content = r.content or {}
                pitfall_files = set(content.get("files_changed", []))
                # Include if any touched file overlaps or shares a directory
                touched_dirs = {f.rsplit("/", 1)[0] for f in touched_set if "/" in f}
                pitfall_dirs = {f.rsplit("/", 1)[0] for f in pitfall_files if "/" in f}
                if (pitfall_files & touched_set) or (pitfall_dirs & touched_dirs):
                    comments = content.get("review_comments", [])
                    desc_parts = []
                    for c in comments[:3]:
                        if isinstance(c, dict):
                            reviewer = c.get("reviewer", "")
                            body = c.get("body", "")
                            desc_parts.append(f"{reviewer}: {body}" if reviewer else body)
                        else:
                            desc_parts.append(str(c))
                    pitfalls.append({
                        "description": "; ".join(desc_parts)[:300],
                        "files": list(pitfall_files & touched_set)[:5],
                        "pr_url": content.get("pr_url", ""),
                    })

        # 4. Load reviewer patterns
        reviewer_patterns = []
        pattern_rows = (await db.execute(
            select(MemoryRecord).where(
                MemoryRecord.org_id == _org_id,
                MemoryRecord.record_type == "pattern",
            ).order_by(MemoryRecord.id.desc()).limit(15)
        )).scalars().all()
        for r in pattern_rows:
            content = r.content or {}
            changes = content.get("changes_requested", [])
            if changes:
                reviewer_patterns.append({
                    "reviewer": content.get("reviewer", ""),
                    "preference": changes[0][:200],
                })

        # Also load enforced_by conventions
        enforced = (await db.execute(
            select(Convention).where(
                Convention.org_id == _org_id,
                Convention.enforced_by.isnot(None),
                Convention.suppressed == False,  # noqa: E712
            ).order_by(Convention.confidence.desc()).limit(10)
        )).scalars().all()
        for c in enforced:
            enforcers = c.enforced_by or []
            if enforcers:
                reviewer_patterns.append({
                    "reviewer": ", ".join(enforcers[:3]),
                    "preference": c.rule[:200],
                })

        # 5. Load past failures
        past_failures = []
        failure_rows = (await db.execute(
            select(MemoryRecord).where(
                MemoryRecord.org_id == _org_id,
                MemoryRecord.record_type == "coder_failure",
            ).order_by(MemoryRecord.id.desc()).limit(10)
        )).scalars().all()
        for r in failure_rows:
            content = r.content or {}
            past_failures.append({
                "task": content.get("task_description", "")[:100],
                "error": content.get("error", content.get("review_summary", ""))[:200],
                "category": content.get("failure_category", ""),
            })

        # 6. Load doc chunks
        doc_chunks = []
        try:
            from app.services.doc_ingestion import query_relevant_chunks
            raw_chunks = await query_relevant_chunks(_org_id, task_description, max_chunks=5)
            doc_chunks = [
                {"heading": c.get("heading", ""), "content": c.get("content", "")[:500]}
                for c in raw_chunks
            ]
        except Exception:
            pass

    return {
        "conventions": conventions,
        "pitfalls": pitfalls,
        "reviewer_patterns": reviewer_patterns[:10],
        "past_failures": past_failures[:5],
        "doc_chunks": doc_chunks,
        "org_id": _org_id,
    }


@mcp.tool(
    name="get_file_companions",
    description=(
        "Find files that typically change together with the given file, based on "
        "git history and past task records. Use this to discover translation files, "
        "test files, type definitions, or any companion files you might miss."
    ),
)
async def get_file_companions(file_path: str) -> dict:
    """Find files that historically co-change with the given file."""
    from app.services.companion_analysis import get_companions

    if not _org_id:
        return {"error": "MCP server not configured — missing org_id"}

    companions = await get_companions(_org_id, file_path)
    return {
        "file": file_path,
        "companions": companions,
    }


@mcp.tool(
    name="get_reviewer_guidance",
    description=(
        "Get specific guidance for the likely reviewers of files you're changing. "
        "Returns what each reviewer typically cares about so you can address their "
        "concerns proactively and avoid review rounds."
    ),
)
async def get_reviewer_guidance(files_changed: list[str]) -> dict:
    """Get reviewer-specific preferences for the given files."""
    from app.core.database import AsyncSessionLocal
    from app.models.convention import Convention
    from app.models.memory import MemoryRecord
    from sqlalchemy import select

    if not _org_id:
        return {"error": "MCP server not configured — missing org_id"}

    guidance = []
    async with AsyncSessionLocal() as db:
        # Conventions enforced by specific reviewers
        enforced = (await db.execute(
            select(Convention).where(
                Convention.org_id == _org_id,
                Convention.enforced_by.isnot(None),
                Convention.suppressed == False,  # noqa: E712
            ).order_by(Convention.confidence.desc()).limit(20)
        )).scalars().all()

        # Group by reviewer
        reviewer_map: dict[str, list[str]] = {}
        for c in enforced:
            for reviewer in (c.enforced_by or []):
                reviewer_map.setdefault(reviewer, []).append(c.rule[:150])

        for reviewer, prefs in reviewer_map.items():
            guidance.append({
                "reviewer": reviewer,
                "preferences": prefs[:5],
                "enforcement_count": len(prefs),
            })

    return {
        "files": files_changed,
        "guidance": guidance,
    }


@mcp.tool(
    name="check_completeness",
    description=(
        "Before committing, check if you missed any files that typically change "
        "together with the ones you modified. Catches missed translation files, "
        "test files, type definitions, schemas, etc."
    ),
)
async def check_completeness(task_description: str, files_changed: list[str]) -> dict:
    """Verify all companion files have been updated."""
    from app.services.companion_analysis import get_companions

    if not _org_id:
        return {"error": "MCP server not configured — missing org_id"}

    changed_set = set(files_changed)
    missing = []

    for file_path in files_changed:
        companions = await get_companions(_org_id, file_path)
        for comp in companions:
            comp_path = comp["path"]
            if comp_path not in changed_set:
                missing.append({
                    "file": comp_path,
                    "reason": f"Usually changes with {file_path} ({comp['co_change_pct']}% of the time)",
                })

    # Dedupe by file path
    seen = set()
    unique_missing = []
    for m in missing:
        if m["file"] not in seen:
            unique_missing.append(m)
            seen.add(m["file"])

    return {
        "complete": len(unique_missing) == 0,
        "files_checked": len(files_changed),
        "missing": unique_missing,
    }
