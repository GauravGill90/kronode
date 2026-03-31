"""Generic webhook inflow receiver.

Accepts webhooks from any source (PagerDuty, CI/CD, custom tools).
Routes to source-specific processors via X-Kronode-Source header.
All processing is async (Celery) — returns 200 immediately.
"""
import hashlib
import hmac
import logging

from fastapi import APIRouter, Request, HTTPException

from app.api.v1.context import get_org_from_api_key

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhooks/ingest")
async def ingest_webhook(request: Request):
    """Receive a webhook event and queue for processing.

    Headers:
        Authorization: Bearer kron_xxx (required)
        X-Kronode-Source: pagerduty | github_ci | gitlab_ci | custom (optional)
        X-Kronode-Idempotency-Key: <unique-id> (optional, for dedup)
        X-Kronode-Signature: <hmac-sha256> (optional, for verification)
    """
    # Auth
    auth_header = request.headers.get("Authorization", "")
    try:
        from fastapi import Header
        org_id = await get_org_from_api_key(auth_header)
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

    body = await request.body()
    source = request.headers.get("X-Kronode-Source", "custom")
    idempotency_key = request.headers.get("X-Kronode-Idempotency-Key", "")

    import json
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = {"raw": body.decode("utf-8", errors="replace")[:10000]}

    # Queue for async processing
    from app.pipeline.task_queue import process_webhook
    process_webhook.delay(org_id, source, payload, idempotency_key)

    logger.info(f"[Webhook] Queued {source} event for org {org_id}")
    return {"ok": True, "source": source, "queued": True}
