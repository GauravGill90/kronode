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
        "For the best results, call kronode_workflow at the START of any coding task — it runs "
        "all tools in one call and returns conventions, pitfalls, reviewer guidance, file companions, "
        "completeness check, and a PR-ready checklist. Alternatively, call individual tools: "
        "get_context for conventions/docs, get_file_companions for co-changing files, "
        "get_reviewer_guidance for reviewer preferences, check_completeness before committing, "
        "and get_doc for full documentation pages. "
        "Conventions with file_match=true are the most important — they come from PRs that "
        "modified the exact files you're editing."
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
        "Get organizational context for a coding task. ALWAYS call this before writing code. "
        "Pass the task description AND files_touched (list of file paths you'll modify). "
        "Returns: (1) conventions ranked by file-level relevance — those with file_match=true "
        "were extracted from PRs that modified the exact files you're touching, (2) pitfalls — "
        "past issues on these files, (3) reviewer preferences for likely reviewers, "
        "(4) past failures on similar tasks, (5) relevant documentation with source URLs. "
        "Each convention includes source_files, enforced_by (reviewers), source_prs, and "
        "last_updated date so you can judge recency and reliability."
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
                {
                    "heading": c.get("heading", ""),
                    "content": c.get("content", "")[:1000],
                    "full_available": len(c.get("content", "")) > 1000,
                    "similarity": round(c.get("similarity", 0), 2),
                    "source_url": c.get("source_url", ""),
                }
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


@mcp.tool(
    name="get_doc",
    description=(
        "Get the full content of a documentation page by searching for it by title or heading. "
        "Use this when get_context returns a truncated doc chunk and you need the complete content. "
        "Returns the full page text, not just a snippet."
    ),
)
async def get_doc(query: str) -> dict:
    """Search for and return full documentation content matching the query."""
    from app.core.database import AsyncSessionLocal
    from app.models.doc_chunk import DocChunk
    from app.core.embeddings import get_embedding, cosine_similarity
    from sqlalchemy import select

    if not _org_id:
        return {"error": "MCP server not configured — missing org_id"}

    async with AsyncSessionLocal() as db:
        # Load all doc chunks for this org
        rows = (await db.execute(
            select(DocChunk).where(DocChunk.org_id == _org_id)
        )).scalars().all()

        if not rows:
            return {"results": [], "message": "No documentation ingested for this org."}

        # Try semantic search first
        query_emb = await get_embedding(query)
        matches = []

        for chunk in rows:
            score = 0.0
            # Semantic match
            if query_emb and chunk.embedding:
                score = cosine_similarity(query_emb, chunk.embedding)

            # Also boost exact keyword matches in heading
            heading_lower = (chunk.heading or "").lower()
            query_lower = query.lower()
            if query_lower in heading_lower:
                score += 0.3  # strong heading match

            if score >= 0.25:
                matches.append((score, chunk))

        # Sort by score, group by source_ref (page) to return full pages
        matches.sort(key=lambda x: -x[0])

        if not matches:
            return {"results": [], "message": f"No docs matched '{query}'."}

        # Get the top matching page's source_ref, then return ALL chunks from that page
        top_source_ref = matches[0][1].source_ref
        page_chunks = [
            chunk for chunk in rows
            if chunk.source_ref == top_source_ref
        ]
        # Sort page chunks by ID (insertion order ≈ document order)
        page_chunks.sort(key=lambda c: c.id)

        full_content = "\n\n".join(c.content for c in page_chunks)
        page_title = page_chunks[0].heading.split(" > ")[0] if page_chunks else query
        source_url = page_chunks[0].source_url or ""

        # Also return other matching pages as suggestions
        seen_refs = {top_source_ref}
        other_pages = []
        for score, chunk in matches:
            if chunk.source_ref not in seen_refs:
                seen_refs.add(chunk.source_ref)
                other_pages.append({
                    "title": chunk.heading.split(" > ")[0],
                    "source_ref": chunk.source_ref,
                    "similarity": round(score, 2),
                })
            if len(other_pages) >= 4:
                break

        return {
            "title": page_title,
            "source_url": source_url,
            "content": full_content,
            "chunks_in_page": len(page_chunks),
            "similarity": round(matches[0][0], 2),
            "other_matches": other_pages,
        }


@mcp.tool(
    name="kronode_workflow",
    description=(
        "Run the full Kronode workflow in a single call. Returns everything you need: "
        "conventions, pitfalls, reviewer guidance, file companions, completeness check, "
        "and relevant documentation — all at once. Use this instead of calling individual "
        "tools separately. Pass the task description, the files you plan to touch, and "
        "optionally the files you've already changed (for completeness check)."
    ),
)
async def kronode_workflow(
    task_description: str,
    files_touched: list[str],
    files_changed: list[str] | None = None,
) -> dict:
    """Run all Kronode tools in one call — full context for a coding task."""
    if not _org_id:
        return {"error": "MCP server not configured — missing org_id"}

    # 1. Get full context (conventions, pitfalls, past failures, docs)
    context = await get_context(task_description, files_touched)

    # 2. File companions for each touched file (top 3 files to keep it fast)
    all_companions: list[dict] = []
    seen_companion_paths: set[str] = set()
    for file_path in files_touched[:5]:
        try:
            result = await get_file_companions(file_path)
            for comp in result.get("companions", []):
                if comp.get("path") not in seen_companion_paths:
                    seen_companion_paths.add(comp["path"])
                    all_companions.append({**comp, "companion_of": file_path})
        except Exception:
            pass

    # 3. Reviewer guidance
    reviewer = await get_reviewer_guidance(files_touched)

    # 4. Completeness check
    check_files = files_changed or files_touched
    completeness = await check_completeness(task_description, check_files)

    # 5. Build PR-ready checklist
    checklist: list[str] = []

    # File-matched conventions
    file_matched = [c for c in context.get("conventions", []) if c.get("file_match")]
    if file_matched:
        checklist.append(f"Follow {len(file_matched)} file-specific conventions (see conventions with file_match=true)")

    # Reviewer preferences
    guidance = reviewer.get("guidance", [])
    for g in guidance[:3]:
        reviewer_name = g.get("reviewer", "")
        prefs = g.get("preferences", [])
        if prefs:
            checklist.append(f"{reviewer_name} will check: {prefs[0][:100]}")

    # Missing companions
    missing = completeness.get("missing", [])
    if missing:
        checklist.append(f"Don't forget: {', '.join(m['file'] for m in missing[:5])}")

    # Past failures
    failures = context.get("past_failures", [])
    if failures:
        checklist.append(f"Avoid past mistake: {failures[0].get('error', '')[:100]}")

    return {
        "conventions": context.get("conventions", []),
        "pitfalls": context.get("pitfalls", []),
        "past_failures": context.get("past_failures", []),
        "doc_chunks": context.get("doc_chunks", []),
        "reviewer_patterns": context.get("reviewer_patterns", []),
        "file_companions": all_companions[:15],
        "reviewer_guidance": guidance,
        "completeness": completeness,
        "pr_ready_checklist": checklist,
        "org_id": _org_id,
    }
