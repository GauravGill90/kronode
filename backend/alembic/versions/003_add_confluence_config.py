"""add confluence config columns to onboarding_config

Revision ID: 003
Revises: 002
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "onboarding_config",
        sa.Column("confluence_base_url", sa.Text, nullable=True),
    )
    op.add_column(
        "onboarding_config",
        sa.Column(
            "confluence_space_keys",
            ARRAY(sa.Text),
            nullable=True,
            server_default="{}",
        ),
    )
    op.add_column(
        "onboarding_config",
        sa.Column(
            "confluence_include_labels",
            ARRAY(sa.Text),
            nullable=True,
            server_default="{}",
        ),
    )


def downgrade() -> None:
    op.drop_column("onboarding_config", "confluence_include_labels")
    op.drop_column("onboarding_config", "confluence_space_keys")
    op.drop_column("onboarding_config", "confluence_base_url")
