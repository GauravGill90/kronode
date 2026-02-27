import asyncio
import json
import logging
import re

import anthropic

from app.agents.base import AgentBase
from app.core.config import settings

logger = logging.getLogger(__name__)

MAX_TOTAL_BYTES = 50_000   # 50 KB total file content sent to Claude
MAX_FILE_BYTES = 6_000     # 6 KB per individual file
MAX_FILES_TO_SELECT = 20   # ask Claude to pick at most this many
MAX_FILES_TO_FETCH = 15    # never fetch more than this (in case Claude over-selects)


class ContextBuilderAgent(AgentBase):
    display_name = "Context Builder"

    def __init__(self):
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self, context: dict) -> dict:
        repo_url = context.get("repo_url", "")
        token = context.get("github_access_token")
        description = context.get("description", "")

        if not repo_url or not token:
            logger.info("[ContextBuilder] No repo URL or token — returning empty bundle")
            return {
                "summary": "No repo configured — context bundle is empty.",
                "relevant_files": [],
                "conventions": [],
                "repo_structure": "",
            }

        try:
            return await self._build(repo_url, token, description)
        except Exception as exc:
            logger.warning(f"[ContextBuilder] Failed: {exc}")
            return {
                "summary": f"Context fetch failed ({exc}) — proceeding without repo context.",
                "relevant_files": [],
                "conventions": [],
                "repo_structure": "",
            }

    async def _build(self, repo_url: str, token: str, description: str) -> dict:
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

        tree_text = "\n".join(all_paths[:2000])  # cap path list for haiku prompt
        repo_structure_summary = _summarise_tree(all_paths)

        # 2. Ask haiku which files are relevant to this task
        selected_paths = await self._select_files(description, tree_text, all_paths)

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

        # 4. Extract conventions from the fetched files
        conventions = await self._extract_conventions(relevant_files, repo_structure_summary)

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

    async def _select_files(
        self, description: str, tree_text: str, all_paths: list[str]
    ) -> list[str]:
        """Ask Claude haiku to pick the most relevant files for this task."""
        prompt = f"""You are selecting files from a codebase that are most relevant to implementing this task:

Task: {description}

Repository file tree:
{tree_text}

Return a JSON array of up to {MAX_FILES_TO_SELECT} file paths that are most relevant.
Include: files the task will likely modify, files that show conventions or patterns to follow,
config files, and any tests related to the area being changed.
Exclude: documentation, changelogs, and unrelated parts of the codebase.

Respond with a JSON array only. No explanation."""

        try:
            message = await self.client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            # Strip markdown if present
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            selected = json.loads(raw)
            if isinstance(selected, list):
                # Validate paths exist in the tree
                path_set = set(all_paths)
                return [p for p in selected if p in path_set]
        except Exception as exc:
            logger.warning(f"[ContextBuilder] File selection failed: {exc}")

        # Fallback: return a simple heuristic selection
        return _heuristic_select(description, all_paths)

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


def _heuristic_select(description: str, paths: list[str]) -> list[str]:
    """Simple fallback: config files + source files scored by description match."""
    words = set(description.lower().split())
    scored: list[tuple[int, str]] = []
    for p in paths:
        name = p.split("/")[-1]
        ext = "." + name.rsplit(".", 1)[-1] if "." in name else ""
        score = 0
        if name in _CONFIG_NAMES:
            score += 3
        if ext in _SOURCE_EXTS:
            score += 1
        if any(w in p.lower() for w in words if len(w) > 3):
            score += 2
        if score > 0:
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:MAX_FILES_TO_SELECT]]
