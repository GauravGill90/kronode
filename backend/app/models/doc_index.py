"""Doc index — lightweight page metadata for lazy ingestion.

Stores page titles, IDs, and last_updated from doc sources (Confluence, Notion, etc.)
without fetching or embedding the full content. Content is fetched on demand when
get_context or get_doc needs it.
"""
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, func, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocIndex(Base):
    __tablename__ = "doc_index"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), index=True)
    source_type: Mapped[str] = mapped_column(String(50), index=True)  # confluence / notion / gdrive
    source_ref: Mapped[str] = mapped_column(String(500), index=True)  # page_id or unique ref
    source_url: Mapped[str | None] = mapped_column(String(500))
    title: Mapped[str] = mapped_column(String(500))
    last_modified: Mapped[str | None] = mapped_column(String(50))  # ISO timestamp from source
    author: Mapped[str | None] = mapped_column(String(255))
    ingested: Mapped[bool] = mapped_column(Boolean, default=False)  # True = content fetched + embedded
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
