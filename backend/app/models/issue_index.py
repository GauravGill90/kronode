"""Issue index — lightweight issue metadata for context matching.

Stores issue titles, labels, and state from issue trackers (GitHub, Jira, Linear).
When get_context matches an issue title, the full content can be fetched on demand.
"""
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IssueIndex(Base):
    __tablename__ = "issue_index"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)  # github_issues / jira / linear
    issue_ref: Mapped[str] = mapped_column(String(100), index=True)  # issue number or key
    title: Mapped[str] = mapped_column(String(500))
    state: Mapped[str] = mapped_column(String(50))  # open / closed
    labels: Mapped[dict | None] = mapped_column(JSONB)  # list of label names
    author: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(500))
    body_preview: Mapped[str | None] = mapped_column(Text)  # first 500 chars of body
    created_at_source: Mapped[str | None] = mapped_column(String(50))  # ISO timestamp from source
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
