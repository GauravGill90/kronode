"""Repository model — multiple repos per org."""
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), index=True)
    repo_url: Mapped[str] = mapped_column(String(500))
    repo_provider: Mapped[str] = mapped_column(String(50))  # github / bitbucket / gitlab
    repo_name: Mapped[str] = mapped_column(String(255))  # owner/repo or workspace/slug
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
