"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-02-26

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("clerk_org_id", sa.String(255), unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_clerk_org_id", "organizations", ["clerk_org_id"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("clerk_id", sa.String(255), unique=True, nullable=False),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("role", sa.String(100)),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_clerk_id", "users", ["clerk_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "onboarding_config",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), unique=True, nullable=False),
        sa.Column("repo_url", sa.String(500)),
        sa.Column("repo_provider", sa.String(50)),
        sa.Column("jira_project_key", sa.String(100)),
        sa.Column("jira_workspace_url", sa.String(500)),
        sa.Column("jira_status_mappings", JSONB),
        sa.Column("slack_channel_id", sa.String(255)),
        sa.Column("slack_channel_name", sa.String(255)),
        sa.Column("docs_provider", sa.String(50)),
        sa.Column("docs_scope", sa.String(500)),
        sa.Column("capabilities", JSONB),
        sa.Column("guardrails", JSONB),
        sa.Column("agent_name", sa.String(100)),
        sa.Column("agent_avatar", sa.String(100)),
        sa.Column("project_context", sa.Text),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_onboarding_config_org_id", "onboarding_config", ["org_id"])

    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("jira_ticket_id", sa.String(100)),
        sa.Column("status", sa.String(50), nullable=False, server_default="queued"),
        sa.Column("result", JSONB),
        sa.Column("error", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_tasks_org_id", "tasks", ["org_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])

    op.create_table(
        "task_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id"), nullable=False),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("payload", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"])

    op.create_table(
        "memory_records",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), sa.ForeignKey("tasks.id")),
        sa.Column("record_type", sa.String(100), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("source", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_records_org_id", "memory_records", ["org_id"])
    op.create_index("ix_memory_records_record_type", "memory_records", ["record_type"])


def downgrade() -> None:
    op.drop_table("memory_records")
    op.drop_table("task_events")
    op.drop_table("tasks")
    op.drop_table("onboarding_config")
    op.drop_table("users")
    op.drop_table("organizations")
