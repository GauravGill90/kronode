import logging
import uuid

from app.agents.base import AgentBase
from app.core.database import AsyncSessionLocal
from app.models.memory import MemoryRecord

logger = logging.getLogger(__name__)


class MemoryAgent(AgentBase):
    display_name = "Memory"

    async def run(self, context: dict) -> dict:
        task_id_str = context.get("task_id")
        org_id = context.get("org_id")
        description = context.get("description", "")
        complexity = context.get("routing", {}).get("complexity", "unknown")

        coder = context.get("coder_agent", {})
        files = coder.get("files", [])
        pr_url = coder.get("pr_url")
        branch_name = coder.get("branch_name", "")

        task_id = uuid.UUID(task_id_str) if task_id_str else None
        records_written = 0

        # ── 1. file_touched records ────────────────────────────────────────────
        if files:
            try:
                async with AsyncSessionLocal() as db:
                    records = [
                        MemoryRecord(
                            org_id=org_id,
                            task_id=task_id,
                            record_type="file_touched",
                            content={
                                "path": f["path"],
                                "description": description[:100],
                                "complexity": complexity,
                            },
                            source=pr_url,
                        )
                        for f in files
                        if f.get("path")
                    ]
                    db.add_all(records)
                    await db.commit()
                    records_written += len(records)
                    logger.info(f"[Memory] Wrote {len(records)} file_touched records")
            except Exception as exc:
                logger.warning(f"[Memory] file_touched write failed: {exc}")

        # ── 2. convention record ───────────────────────────────────────────────
        # Write only when context_builder freshly extracted conventions this run
        # (new_conventions is set; cached_conventions means we reused a DB record)
        new_conventions = context.get("new_conventions")
        if new_conventions and not context.get("cached_conventions"):
            try:
                async with AsyncSessionLocal() as db:
                    rec = MemoryRecord(
                        org_id=org_id,
                        task_id=task_id,
                        record_type="convention",
                        content={"conventions": new_conventions},
                        source="context_builder",
                    )
                    db.add(rec)
                    await db.commit()
                    records_written += 1
                    logger.info(f"[Memory] Wrote convention record ({len(new_conventions)} conventions)")
            except Exception as exc:
                logger.warning(f"[Memory] convention write failed: {exc}")

        # ── 3. pr_outcome record ───────────────────────────────────────────────
        if pr_url:
            try:
                async with AsyncSessionLocal() as db:
                    rec = MemoryRecord(
                        org_id=org_id,
                        task_id=task_id,
                        record_type="pr_outcome",
                        content={
                            "pr_url": pr_url,
                            "branch_name": branch_name,
                            "files_changed": [f["path"] for f in files if f.get("path")],
                            "merged": False,
                            "complexity": complexity,
                        },
                        source=pr_url,
                    )
                    db.add(rec)
                    await db.commit()
                    records_written += 1
                    logger.info(f"[Memory] Wrote pr_outcome record for {pr_url}")
            except Exception as exc:
                logger.warning(f"[Memory] pr_outcome write failed: {exc}")

        # ── 4. reviewer pattern records ────────────────────────────────────────
        reviewer = context.get("reviewer_agent", {})
        changes_requested = reviewer.get("changes_requested", [])
        if changes_requested and not reviewer.get("approved", True):
            try:
                async with AsyncSessionLocal() as db:
                    rec = MemoryRecord(
                        org_id=org_id,
                        task_id=task_id,
                        record_type="pattern",
                        content={
                            "changes_requested": changes_requested,
                            "verdict": reviewer.get("verdict", ""),
                            "description": description[:100],
                        },
                        source="reviewer_agent",
                    )
                    db.add(rec)
                    await db.commit()
                    records_written += 1
                    logger.info(f"[Memory] Wrote reviewer pattern record ({len(changes_requested)} change(s) requested)")
            except Exception as exc:
                logger.warning(f"[Memory] reviewer pattern write failed: {exc}")

        return {
            "summary": f"Memory write-back complete: {records_written} record(s) written.",
            "records_written": records_written,
        }
