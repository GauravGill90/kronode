from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, JSON, func
from sqlalchemy.orm import Mapped, mapped_column

from kronode.core.database import Base


class MemoryRecord(Base):
    __tablename__ = "memory_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, index=True)

    # pattern | reviewer_feedback | pitfall | convention | clarification
    record_type: Mapped[str] = mapped_column(String(100), index=True)
    content: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(String(500))  # task_id, PR URL, reviewer comment URL

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
