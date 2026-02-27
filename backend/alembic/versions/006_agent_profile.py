"""add agent_profile to onboarding_config

Revision ID: 006
Revises: 005
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onboarding_config", sa.Column("agent_profile", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_config", "agent_profile")
