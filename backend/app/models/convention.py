from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Float, Boolean, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Convention(Base):
    __tablename__ = "conventions"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"), index=True)  # null = base convention
    repo_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("repositories.id"), index=True)  # null = org-wide

    rule: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)  # naming | error_handling | testing | logging | architecture | style
    examples: Mapped[dict | None] = mapped_column(JSONB)  # list of code snippets
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    layer: Mapped[str] = mapped_column(String(20), default="customer")  # "base" | "customer"
    stack: Mapped[str | None] = mapped_column(String(50))  # typescript | python | go | ruby | etc. — for base conventions
    source_prs: Mapped[dict | None] = mapped_column(JSONB)  # list of PR URLs
    source_files: Mapped[dict | None] = mapped_column(JSONB)  # list of file paths this convention was extracted from
    enforced_by: Mapped[dict | None] = mapped_column(JSONB)  # list of reviewer logins who enforce this
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    suppressed_by: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
