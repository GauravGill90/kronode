import asyncio
import json
import logging
import os
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_TOTAL_BYTES = 30_000   # 30 KB total file content sent to Claude
MAX_FILE_BYTES = 4_000     # 4 KB per individual file
MAX_FILES_TO_SELECT = 12   # max files to select heuristically
MAX_FILES_TO_FETCH = 10    # never fetch more than this


class ContextBuilderAgent(AgentBase):
    display_name = "Context Builder"

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

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

        # 4. Use cached conventions if available, otherwise extract via Haiku
        if cached_conventions:
            conventions = cached_conventions
            logger.info(f"[ContextBuilder] Using {len(conventions)} cached conventions — skipping Haiku call")
        else:
            conventions = await self._extract_conventions(relevant_files, repo_structure_summary)
            # Signal to pipeline that we have fresh conventions to cache
            context["new_conventions"] = conventions

        return {
            "summary": (
                f"Fetched {len(relevant_files)} relevant file(s) from repo "
                f"({total_bytes // 1000}KB). "
                f"{len(conventions)} conventions extracted."
            ),
            "relevant_files": relevant_files,
            "conventions": conventions,
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
            message = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
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
