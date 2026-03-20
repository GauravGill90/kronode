"""create skills and agent_skills tables

Revision ID: 014
Revises: 013
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("stack_chips", JSONB, server_default="[]"),
        sa.Column("system_prompt", sa.Text, server_default=""),
        sa.Column("allowed_extensions", JSONB, server_default="[]"),
        sa.Column("allowed_dirs", JSONB, server_default="[]"),
        sa.Column("context_priorities", JSONB, server_default="[]"),
        sa.Column("is_preset", sa.Boolean, server_default="false"),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "agent_skills",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("skill_id", sa.Integer, sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("position", sa.Integer, server_default="0"),
        sa.UniqueConstraint("org_id", "skill_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_skills")
    op.drop_table("skills")
