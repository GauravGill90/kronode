"""Reviewer patterns context provider."""
from app.services.context_providers.base import ContextProvider


class ReviewerPatternsProvider(ContextProvider):
    name = "reviewer_patterns"
    weight = 1.0

    async def get_context(self, org_id: int, task_description: str, files_touched: list[str] | None = None) -> dict:
        from app.core.database import AsyncSessionLocal
        from app.models.convention import Convention
        from app.models.memory import MemoryRecord
        from sqlalchemy import select

        reviewer_patterns = []

        async with AsyncSessionLocal() as db:
            # From memory records
            pattern_rows = (await db.execute(
                select(MemoryRecord).where(
                    MemoryRecord.org_id == org_id,
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

            # From enforced_by conventions
            enforced = (await db.execute(
                select(Convention).where(
                    Convention.org_id == org_id,
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

        return {"reviewer_patterns": reviewer_patterns[:10]}
