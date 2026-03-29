from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Text, Index, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), index=True)

    source_type: Mapped[str] = mapped_column(String(50), index=True)  # git | confluence | gdrive | notion
    source_ref: Mapped[str] = mapped_column(String(500), index=True)  # unique id within source, e.g. "owner/repo:path/to/file.md"
    source_url: Mapped[str | None] = mapped_column(String(500))  # full URL to the source page/file
    file_sha: Mapped[str | None] = mapped_column(String(64))  # for delta sync — only re-fetch when SHA changes

    heading: Mapped[str | None] = mapped_column(String(500))  # section heading this chunk was extracted from
    content: Mapped[str] = mapped_column(Text)  # chunk body text (max ~2KB)
    embedding: Mapped[dict | None] = mapped_column(JSONB)  # float vector as JSON array
    extra: Mapped[dict | None] = mapped_column("metadata", JSONB)  # provider-specific (heading_level, file_path, page_id, etc.)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_doc_chunks_org_source", "org_id", "source_type"),
    )
