"""Webhook processors — one per source type."""
import logging

logger = logging.getLogger(__name__)


async def process(org_id: int, source: str, payload: dict, idempotency_key: str = ""):
    """Route webhook to the appropriate processor."""
    from app.core.database import AsyncSessionLocal
    from app.models.memory import MemoryRecord

    # Dedup check
    if idempotency_key:
        from sqlalchemy import select
        async with AsyncSessionLocal() as db:
            existing = (await db.execute(
                select(MemoryRecord).where(
                    MemoryRecord.org_id == org_id,
                    MemoryRecord.source == f"webhook:{idempotency_key}",
                )
            )).scalar_one_or_none()
            if existing:
                logger.info(f"[Webhook] Skipping duplicate: {idempotency_key}")
                return

    # Route to processor
    if source == "pagerduty":
        record = _process_pagerduty(payload)
    elif source in ("github_ci", "gitlab_ci"):
        record = _process_ci(payload, source)
    else:
        record = _process_generic(payload)

    # Store as memory record
    async with AsyncSessionLocal() as db:
        memory = MemoryRecord(
            org_id=org_id,
            record_type=record.get("type", "webhook_event"),
            content=record,
            source=f"webhook:{idempotency_key}" if idempotency_key else f"webhook:{source}",
        )
        db.add(memory)
        await db.commit()
        logger.info(f"[Webhook] Stored {source} event for org {org_id}")


def _process_pagerduty(payload: dict) -> dict:
    """Extract incident context from PagerDuty webhook."""
    event = payload.get("event", {})
    incident = event.get("data", {})
    return {
        "type": "incident",
        "title": incident.get("title", ""),
        "status": incident.get("status", ""),
        "urgency": incident.get("urgency", ""),
        "service": incident.get("service", {}).get("summary", ""),
        "url": incident.get("html_url", ""),
        "source": "pagerduty",
    }


def _process_ci(payload: dict, source: str) -> dict:
    """Extract CI/CD build context."""
    return {
        "type": "ci_event",
        "status": payload.get("status", payload.get("state", "")),
        "pipeline": payload.get("pipeline", payload.get("workflow", {}).get("name", "")),
        "branch": payload.get("branch", payload.get("ref", "")),
        "commit": payload.get("commit", payload.get("sha", ""))[:12],
        "url": payload.get("url", payload.get("html_url", "")),
        "source": source,
    }


def _process_generic(payload: dict) -> dict:
    """Store generic webhook payload as-is."""
    return {
        "type": "webhook_event",
        "payload": {k: str(v)[:500] for k, v in payload.items()} if isinstance(payload, dict) else {"raw": str(payload)[:2000]},
        "source": "custom",
    }
