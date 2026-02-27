"""add coding_standards to onboarding_config

Revision ID: 007
Revises: 006
Create Date: 2026-02-27
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("onboarding_config", sa.Column("coding_standards", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_config", "coding_standards")
