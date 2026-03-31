"""Pitfalls context provider — past issues on touched files."""
from app.services.context_providers.base import ContextProvider


class PitfallsProvider(ContextProvider):
    name = "pitfalls"
    weight = 1.5

    async def get_context(self, org_id: int, task_description: str, files_touched: list[str] | None = None) -> dict:
        if not files_touched:
            return {"pitfalls": []}

        from app.core.database import AsyncSessionLocal
        from app.models.memory import MemoryRecord
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            pitfall_rows = (await db.execute(
                select(MemoryRecord).where(
                    MemoryRecord.org_id == org_id,
                    MemoryRecord.record_type == "pitfall",
                ).order_by(MemoryRecord.id.desc()).limit(30)
            )).scalars().all()

        touched_set = set(files_touched)
        touched_dirs = {f.rsplit("/", 1)[0] for f in touched_set if "/" in f}
        pitfalls = []

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

        return {"pitfalls": pitfalls}
