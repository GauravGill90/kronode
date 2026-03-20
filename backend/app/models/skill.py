from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Boolean, ForeignKey, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)  # frontend | backend | mobile | devops | data | testing
    stack_chips: Mapped[dict] = mapped_column(JSONB, default=list)  # ["React", "Next.js"]

    system_prompt: Mapped[str] = mapped_column(Text, default="")
    allowed_extensions: Mapped[dict] = mapped_column(JSONB, default=list)  # [".ts", ".tsx"]
    allowed_dirs: Mapped[dict] = mapped_column(JSONB, default=list)  # ["frontend/", "src/"]
    context_priorities: Mapped[dict] = mapped_column(JSONB, default=list)  # [".tsx", ".ts"]

    is_preset: Mapped[bool] = mapped_column(Boolean, default=False)  # Kronode-curated vs custom
    org_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("organizations.id"))  # NULL = global

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AgentSkill(Base):
    __tablename__ = "agent_skills"
    __table_args__ = (UniqueConstraint("org_id", "skill_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), index=True)
    skill_id: Mapped[int] = mapped_column(Integer, ForeignKey("skills.id"))
    position: Mapped[int] = mapped_column(Integer, default=0)  # ordering for prompt composition
