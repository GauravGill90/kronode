"""File companion analysis — find files that typically change together.

Uses two data sources:
1. MemoryRecord `file_touched` records (from past Kronode tasks)
2. Convention `source_files` (files conventions were extracted from)

Returns companion files with co-change frequency.
"""
import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def get_companions(org_id: int, file_path: str, min_co_change_pct: int = 30) -> list[dict]:
    """Find files that historically change together with the given file.

    Returns list of {path, co_change_pct, co_change_count, total_tasks}.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.memory import MemoryRecord

    # 1. Find all tasks that touched this file
    async with AsyncSessionLocal() as db:
        touched_rows = (await db.execute(
            select(MemoryRecord.task_id, MemoryRecord.content).where(
                MemoryRecord.org_id == org_id,
                MemoryRecord.record_type == "file_touched",
            ).order_by(MemoryRecord.id.desc()).limit(500)
        )).all()

    # Build task_id → [file_paths] mapping
    task_files: dict[str, list[str]] = defaultdict(list)
    for task_id, content in touched_rows:
        if isinstance(content, dict) and content.get("path"):
            tid = str(task_id) if task_id else "unknown"
            task_files[tid].append(content["path"])

    # Find tasks that include our target file
    target_dir = file_path.rsplit("/", 1)[0] if "/" in file_path else ""
    my_tasks = []
    for tid, paths in task_files.items():
        if file_path in paths:
            my_tasks.append(tid)
        elif target_dir:
            # Also match if any file in the same directory was touched
            for p in paths:
                if p.startswith(target_dir + "/"):
                    my_tasks.append(tid)
                    break

    if not my_tasks:
        # No history — fall back to directory-based companion detection
        return await _directory_companions(org_id, file_path)

    # Count co-occurrences
    co_change: dict[str, int] = defaultdict(int)
    for tid in my_tasks:
        for other_path in task_files.get(tid, []):
            if other_path != file_path:
                co_change[other_path] += 1

    total_tasks = len(my_tasks)
    companions = []
    for path, count in sorted(co_change.items(), key=lambda x: -x[1]):
        pct = int(100 * count / total_tasks)
        if pct >= min_co_change_pct:
            companions.append({
                "path": path,
                "co_change_pct": pct,
                "co_change_count": count,
                "total_tasks": total_tasks,
            })

    return companions[:20]


async def _directory_companions(org_id: int, file_path: str) -> list[dict]:
    """Fallback: if no task history, find files in the same directory family.

    Looks for common companion patterns:
    - Same directory siblings (e.g., all locale files)
    - Test file for source file
    - Type definition file
    """
    from app.core.database import AsyncSessionLocal
    from app.models.memory import MemoryRecord

    if "/" not in file_path:
        return []

    file_dir = file_path.rsplit("/", 1)[0]

    # Check if the directory has known sibling patterns from conventions
    # For now, return empty — this will be enriched with git log mining later
    return []
