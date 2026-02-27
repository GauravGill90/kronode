"""add github_access_token to onboarding_config

Revision ID: 002
Revises: 001
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "onboarding_config",
        sa.Column("github_access_token", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("onboarding_config", "github_access_token")
