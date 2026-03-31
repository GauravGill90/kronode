"""Past failures context provider."""
from app.services.context_providers.base import ContextProvider


class PastFailuresProvider(ContextProvider):
    name = "past_failures"
    weight = 1.5

    async def get_context(self, org_id: int, task_description: str, files_touched: list[str] | None = None) -> dict:
        from app.core.database import AsyncSessionLocal
        from app.models.memory import MemoryRecord
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            failure_rows = (await db.execute(
                select(MemoryRecord).where(
                    MemoryRecord.org_id == org_id,
                    MemoryRecord.record_type == "coder_failure",
                ).order_by(MemoryRecord.id.desc()).limit(10)
            )).scalars().all()

        past_failures = []
        for r in failure_rows:
            content = r.content or {}
            past_failures.append({
                "task": content.get("task_description", "")[:100],
                "error": content.get("error", content.get("review_summary", ""))[:200],
                "category": content.get("failure_category", ""),
            })

        return {"past_failures": past_failures[:5]}
