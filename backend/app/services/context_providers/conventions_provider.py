"""Conventions context provider — ranked team conventions."""
from app.services.context_providers.base import ContextProvider


class ConventionsProvider(ContextProvider):
    name = "conventions"
    weight = 2.0

    async def get_context(self, org_id: int, task_description: str, files_touched: list[str] | None = None) -> dict:
        from app.core.database import AsyncSessionLocal
        from app.models.convention import Convention
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            conv_rows = (await db.execute(
                select(Convention).where(
                    Convention.org_id == org_id,
                    Convention.suppressed == False,  # noqa: E712
                )
            )).scalars().all()

            from app.agents.context_builder import _rank_conventions, _get_category_relevance
            category_boost = await _get_category_relevance(task_description)
            conventions = await _rank_conventions(
                conv_rows,
                description=task_description,
                selected_paths=files_touched or [],
                category_boost=category_boost,
                max_conventions=20,
            )

        return {"conventions": conventions}
