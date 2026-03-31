from datetime import datetime

from sqlalchemy import String, DateTime, Integer, ForeignKey, func, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    clerk_org_id: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OnboardingConfig(Base):
    __tablename__ = "onboarding_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id"), unique=True, index=True)

    # Step 2 — git org/workspace (multi-repo)
    git_org_name: Mapped[str | None] = mapped_column(String(255))  # GitHub org / Bitbucket workspace / GitLab group
    repo_url: Mapped[str | None] = mapped_column(String(500))  # primary repo (backward compat)
    # TEMP: fork_repo_url commented out due to asyncpg prepared statement cache issue
    # fork_repo_url: Mapped[str | None] = mapped_column(String(500))  # fork repo (write: branches, commits, PRs)
    repo_provider: Mapped[str | None] = mapped_column(String(50))  # github / gitlab / bitbucket
    repo_name: Mapped[str | None] = mapped_column(String(255))

    # Step 3 — jira
    jira_project_key: Mapped[str | None] = mapped_column(String(100))
    jira_workspace_url: Mapped[str | None] = mapped_column(String(500))
    jira_status_mappings: Mapped[dict | None] = mapped_column(JSONB)
    jira_email: Mapped[str | None] = mapped_column(String(255))
    jira_api_token: Mapped[str | None] = mapped_column(Text)

    # Step 4 — slack
    slack_channel_id: Mapped[str | None] = mapped_column(String(255))
    slack_channel_name: Mapped[str | None] = mapped_column(String(255))
    slack_bot_token: Mapped[str | None] = mapped_column(Text)

    # Step 5 — docs
    docs_provider: Mapped[str | None] = mapped_column(String(50))  # confluence / gdrive
    docs_scope: Mapped[str | None] = mapped_column(String(500))

    # Step 6 — capabilities
    capabilities: Mapped[dict | None] = mapped_column(JSONB)

    # Step 7 — guardrails
    guardrails: Mapped[dict | None] = mapped_column(JSONB)  # restricted_paths, max_files, risk_level

    # Step 8 — agent identity
    agent_name: Mapped[str | None] = mapped_column(String(100))
    agent_avatar: Mapped[str | None] = mapped_column(String(100))
    agent_profile: Mapped[str | None] = mapped_column(String(50))  # web|backend|fullstack|devops|mobile_ios|mobile_android|data

    # Step 9 — project context + org coding standards
    project_context: Mapped[str | None] = mapped_column(Text)
    coding_standards: Mapped[str | None] = mapped_column(Text)  # org-defined coding standards injected into every task

    # GitHub PAT (plain-text for now; will be encrypted in Phase 3 OAuth)
    github_access_token: Mapped[str | None] = mapped_column(Text)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
