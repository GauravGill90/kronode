"""Kronode MCP Server — organizational memory for AI coding tools.

Two tools:
  get_context — everything an AI needs before coding (conventions, companions,
                reviewer guidance, completeness check, docs, pitfalls, checklist)
  get_doc     — drill into a full documentation page when get_context returns
                a truncated snippet
"""
import logging
import os

from mcp.server import FastMCP

logger = logging.getLogger(__name__)

_org_id: int | None = None
_repo_url: str | None = None
_github_token: str | None = None

mcp = FastMCP(
    name="kronode",
    instructions=(
        "Kronode provides organizational memory for your engineering team. "
        "ALWAYS call get_context at the START of any coding task. Pass the task description "
        "and the files you plan to touch. It returns everything in one call: file-specific "
        "conventions, reviewer preferences, file companions, completeness check, past failures, "
        "documentation, and a PR-ready checklist. Conventions with file_match=true are the most "
        "important — they were extracted from PRs that modified the exact files you're editing. "
        "Use get_doc only when you need the full text of a documentation page that was truncated."
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
        "Get everything you need before writing code — call this at the START of any task. "
        "Pass the task description AND files_touched (file paths you'll modify). "
        "Returns in one call: "
        "(1) conventions ranked by file-level relevance (file_match=true = from exact files), "
        "(2) file companions (files that usually change together — tests, i18n, types), "
        "(3) reviewer guidance (what each likely reviewer will check), "
        "(4) completeness check (did you miss any companion files), "
        "(5) pitfalls (past issues on these files), "
        "(6) past failures (mistakes to avoid), "
        "(7) relevant documentation with source URLs, "
        "(8) PR-ready checklist summarizing what to watch for. "
        "Each convention includes source_files, enforced_by, source_prs, and last_updated."
    ),
)
async def get_context(task_description: str, files_touched: list[str] | None = None) -> dict:
    """Full organizational context for a coding task — one call, everything returned."""
    from app.core.database import AsyncSessionLocal
    from app.models.convention import Convention
    from app.models.memory import MemoryRecord
    from app.services.companion_analysis import get_companions
    from sqlalchemy import select

    if not _org_id:
        return {"error": "MCP server not configured — missing org_id"}

    files_touched = files_touched or []

    async with AsyncSessionLocal() as db:
        # ── 1. Conventions (ranked by file relevance) ────────────────────────
        conv_rows = (await db.execute(
            select(Convention).where(
                Convention.org_id == _org_id,
                Convention.suppressed == False,  # noqa: E712
            )
        )).scalars().all()

        from app.agents.context_builder import _rank_conventions, _get_category_relevance
        category_boost = await _get_category_relevance(task_description)
        conventions = await _rank_conventions(
            conv_rows,
            description=task_description,
            selected_paths=files_touched,
            category_boost=category_boost,
            max_conventions=20,
        )

        # ── 2. Pitfalls (file-scoped) ────────────────────────────────────────
        pitfalls = []
        if files_touched:
            pitfall_rows = (await db.execute(
                select(MemoryRecord).where(
                    MemoryRecord.org_id == _org_id,
                    MemoryRecord.record_type == "pitfall",
                ).order_by(MemoryRecord.id.desc()).limit(30)
            )).scalars().all()

            touched_set = set(files_touched)
            touched_dirs = {f.rsplit("/", 1)[0] for f in touched_set if "/" in f}
            for r in pitfall_rows:
                content = r.content or {}
                pitfall_files = set(content.get("files_changed", []))
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

        # ── 3. Reviewer guidance ─────────────────────────────────────────────
        reviewer_guidance = []

        # From enforced_by conventions (grouped by reviewer)
        enforced = (await db.execute(
            select(Convention).where(
                Convention.org_id == _org_id,
                Convention.enforced_by.isnot(None),
                Convention.suppressed == False,  # noqa: E712
            ).order_by(Convention.confidence.desc()).limit(20)
        )).scalars().all()

        reviewer_map: dict[str, list[str]] = {}
        for c in enforced:
            for reviewer in (c.enforced_by or []):
                reviewer_map.setdefault(reviewer, []).append(c.rule[:150])

        for reviewer, prefs in reviewer_map.items():
            reviewer_guidance.append({
                "reviewer": reviewer,
                "preferences": prefs[:5],
                "enforcement_count": len(prefs),
            })

        # From memory records (direct reviewer feedback)
        pattern_rows = (await db.execute(
            select(MemoryRecord).where(
                MemoryRecord.org_id == _org_id,
                MemoryRecord.record_type == "pattern",
            ).order_by(MemoryRecord.id.desc()).limit(15)
        )).scalars().all()
        for r in pattern_rows:
            content = r.content or {}
            changes = content.get("changes_requested", [])
            reviewer = content.get("reviewer", "")
            if changes and reviewer:
                # Merge into existing reviewer entry if exists
                existing = next((g for g in reviewer_guidance if g["reviewer"] == reviewer), None)
                if existing:
                    existing["preferences"].extend(changes[:2])
                else:
                    reviewer_guidance.append({
                        "reviewer": reviewer,
                        "preferences": changes[:3],
                        "enforcement_count": 0,
                    })

        # ── 4. Past failures ─────────────────────────────────────────────────
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

        # ── 5. Documentation ─────────────────────────────────────────────────
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

    # ── 6. File companions ───────────────────────────────────────────────
    file_companions: list[dict] = []
    seen_paths: set[str] = set()
    for file_path in files_touched[:5]:
        try:
            companions = await get_companions(_org_id, file_path)
            for comp in companions:
                if comp.get("path") not in seen_paths:
                    seen_paths.add(comp["path"])
                    file_companions.append({**comp, "companion_of": file_path})
        except Exception:
            pass

    # ── 7. Completeness check ────────────────────────────────────────────
    changed_set = set(files_touched)
    missing_files = []
    for comp in file_companions:
        if comp.get("path") not in changed_set:
            missing_files.append({
                "file": comp["path"],
                "reason": f"Usually changes with {comp.get('companion_of', '?')} ({comp.get('co_change_pct', '?')}% of the time)",
            })

    # ── 8. PR-ready checklist ────────────────────────────────────────────
    checklist: list[str] = []

    file_matched = [c for c in conventions if c.get("file_match")]
    if file_matched:
        checklist.append(f"Follow {len(file_matched)} file-specific conventions (file_match=true)")

    for g in reviewer_guidance[:3]:
        prefs = g.get("preferences", [])
        if prefs:
            checklist.append(f"{g['reviewer']} will check: {prefs[0][:100]}")

    if missing_files:
        checklist.append(f"Don't forget: {', '.join(m['file'] for m in missing_files[:5])}")

    if past_failures:
        checklist.append(f"Avoid past mistake: {past_failures[0].get('error', '')[:100]}")

    return {
        "conventions": conventions,
        "pitfalls": pitfalls,
        "reviewer_guidance": reviewer_guidance[:10],
        "past_failures": past_failures[:5],
        "doc_chunks": doc_chunks,
        "file_companions": file_companions[:15],
        "completeness": {
            "complete": len(missing_files) == 0,
            "missing": missing_files[:10],
        },
        "pr_ready_checklist": checklist,
        "org_id": _org_id,
    }


@mcp.tool(
    name="get_doc",
    description=(
        "Get the full content of a documentation page when get_context returned a "
        "truncated snippet (full_available=true). Search by title or keyword. "
        "Returns the complete page text with source URL."
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
        rows = (await db.execute(
            select(DocChunk).where(DocChunk.org_id == _org_id)
        )).scalars().all()

        if not rows:
            return {"results": [], "message": "No documentation ingested for this org."}

        query_emb = await get_embedding(query)
        matches = []

        for chunk in rows:
            score = 0.0
            if query_emb and chunk.embedding:
                score = cosine_similarity(query_emb, chunk.embedding)

            heading_lower = (chunk.heading or "").lower()
            query_lower = query.lower()
            if query_lower in heading_lower:
                score += 0.3

            if score >= 0.25:
                matches.append((score, chunk))

        matches.sort(key=lambda x: -x[0])

        if not matches:
            return {"results": [], "message": f"No docs matched '{query}'."}

        top_source_ref = matches[0][1].source_ref
        page_chunks = sorted(
            [c for c in rows if c.source_ref == top_source_ref],
            key=lambda c: c.id,
        )

        full_content = "\n\n".join(c.content for c in page_chunks)
        page_title = page_chunks[0].heading.split(" > ")[0] if page_chunks else query
        source_url = page_chunks[0].source_url or ""

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
