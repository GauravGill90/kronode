"""Documentation chunks context provider."""
from app.services.context_providers.base import ContextProvider


class DocChunksProvider(ContextProvider):
    name = "doc_chunks"
    weight = 1.0

    async def get_context(self, org_id: int, task_description: str, files_touched: list[str] | None = None) -> dict:
        try:
            from app.services.doc_ingestion import query_relevant_chunks
            raw_chunks = await query_relevant_chunks(org_id, task_description, max_chunks=5)
            doc_chunks = [
                {
                    "heading": c.get("heading", ""),
                    "content": c.get("content", "")[:1000],
                    "full_available": len(c.get("content", "")) > 1000,
                }
                for c in raw_chunks
            ]
            return {"doc_chunks": doc_chunks}
        except Exception:
            return {"doc_chunks": []}
