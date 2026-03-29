"""add fork_repo_url to onboarding_config

Revision ID: 017
Revises: 016
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("onboarding_config", sa.Column("fork_repo_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_config", "fork_repo_url")
