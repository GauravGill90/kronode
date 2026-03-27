import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, Integer, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TaskStatus(str, Enum):
    """Task execution status."""
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_CLARIFICATION = "waiting_clarification"
    PAUSED = "paused"
    IN_REVIEW = "in_review"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    description: Mapped[str] = mapped_column(Text)
    jira_ticket_id: Mapped[str | None] = mapped_column(String(100))

    # queued | running | done | failed | paused | cancelled
    status: Mapped[str] = mapped_column(String(50), default="queued", index=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(255))

    result: Mapped[dict | None] = mapped_column(JSONB)  # final output from Coder Agent
    plan_snapshot: Mapped[dict | None] = mapped_column(JSONB)  # approved plan for audit
    error: Mapped[str | None] = mapped_column(Text)

    # New orchestrator state (stores complete PipelineState)
    pipeline_state: Mapped[dict | None] = mapped_column(JSONB)

    # PR info (set by orchestrator)
    pr_url: Mapped[str | None] = mapped_column(String(500))
    pr_number: Mapped[int | None] = mapped_column(Integer)
    branch_name: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TaskEvent(Base):
    __tablename__ = "task_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), index=True)
    agent_name: Mapped[str] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(100))  # started | progress | completed | failed
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
