"""Audit log for tracking all data access and admin actions.

Every MCP tool call, API request, and admin action is logged here.
Retention: 1 year minimum (SOC 2 requirement).
"""
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, func, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int | None] = mapped_column(Integer, index=True)
    user_id: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(100), index=True)  # mcp_tool_call, api_request, admin_action, data_deletion
    resource: Mapped[str | None] = mapped_column(String(255))  # tool name, endpoint path, etc.
    details: Mapped[dict | None] = mapped_column(JSONB)  # request params, response summary, etc.
    ip_address: Mapped[str | None] = mapped_column(String(45))
    duration_ms: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
