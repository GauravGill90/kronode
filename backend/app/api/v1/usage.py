"""Usage metrics endpoint — per-org analytics for dashboard and billing."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.models.convention import Convention
from app.models.doc_chunk import DocChunk
from app.models.api_key import ApiKey

router = APIRouter()


@router.get("/usage")
async def get_usage(
    days: int = 30,
    user_data: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get usage metrics for the current org."""
    org_id = user_data.get("org_id")
    if not org_id:
        return {"error": "No organization found"}

    since = datetime.now(timezone.utc) - timedelta(days=days)

    # MCP tool calls
    mcp_calls = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.org_id == org_id,
            AuditLog.action == "mcp_tool_call",
            AuditLog.created_at >= since,
        )
    )).scalar() or 0

    # API calls
    api_calls = (await db.execute(
        select(func.count(AuditLog.id)).where(
            AuditLog.org_id == org_id,
            AuditLog.action == "api_request",
            AuditLog.created_at >= since,
        )
    )).scalar() or 0

    # Most used tools
    tool_counts = (await db.execute(
        select(AuditLog.resource, func.count(AuditLog.id).label("count")).where(
            AuditLog.org_id == org_id,
            AuditLog.action == "mcp_tool_call",
            AuditLog.created_at >= since,
        ).group_by(AuditLog.resource).order_by(func.count(AuditLog.id).desc()).limit(10)
    )).all()

    # Convention count
    convention_count = (await db.execute(
        select(func.count(Convention.id)).where(
            Convention.org_id == org_id,
            Convention.suppressed == False,  # noqa: E712
        )
    )).scalar() or 0

    # Doc chunk count
    doc_chunk_count = (await db.execute(
        select(func.count(DocChunk.id)).where(DocChunk.org_id == org_id)
    )).scalar() or 0

    # Active API keys
    active_keys = (await db.execute(
        select(func.count(ApiKey.id)).where(ApiKey.org_id == org_id)
    )).scalar() or 0

    # Average latency
    avg_latency = (await db.execute(
        select(func.avg(AuditLog.duration_ms)).where(
            AuditLog.org_id == org_id,
            AuditLog.action == "mcp_tool_call",
            AuditLog.created_at >= since,
            AuditLog.duration_ms.isnot(None),
        )
    )).scalar()

    return {
        "period_days": days,
        "mcp_tool_calls": mcp_calls,
        "api_calls": api_calls,
        "most_used_tools": [{"tool": t[0], "count": t[1]} for t in tool_counts],
        "convention_count": convention_count,
        "doc_chunk_count": doc_chunk_count,
        "active_api_keys": active_keys,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency else None,
    }
