from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    clerk_org_id = Column(String(255), unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    onboarding_config = relationship(
        "OnboardingConfig", back_populates="organization", uselist=False
    )
    users = relationship("User", back_populates="organization")


class OnboardingConfig(Base):
    __tablename__ = "onboarding_config"

    id = Column(Integer, primary_key=True)
    org_id = Column(
        Integer, ForeignKey("organizations.id"), unique=True, nullable=False
    )

    # GitHub
    repo_url = Column(String(500))
    repo_provider = Column(String(50))
    github_access_token = Column(Text, nullable=True)

    # Jira
    jira_project_key = Column(String(100))
    jira_workspace_url = Column(String(500))
    jira_status_mappings = Column(JSONB)

    # Slack
    slack_channel_id = Column(String(255))
    slack_channel_name = Column(String(255))

    # Confluence
    confluence_base_url = Column(Text, nullable=True)
    confluence_space_keys = Column(ARRAY(Text), nullable=True, default=list)
    confluence_include_labels = Column(ARRAY(Text), nullable=True, default=list)

    # Docs (generic)
    docs_provider = Column(String(50))
    docs_scope = Column(String(500))

    # Agent config
    capabilities = Column(JSONB)
    guardrails = Column(JSONB)
    agent_name = Column(String(100))
    agent_avatar = Column(String(100))
    project_context = Column(Text)

    completed_at = Column(DateTime(timezone=True))
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    organization = relationship("Organization", back_populates="onboarding_config")
