"""add jira and slack credential columns to onboarding_config

Revision ID: 003
Revises: 002
Create Date: 2026-02-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("onboarding_config", sa.Column("jira_email", sa.String(255), nullable=True))
    op.add_column("onboarding_config", sa.Column("jira_api_token", sa.Text, nullable=True))
    op.add_column("onboarding_config", sa.Column("slack_bot_token", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("onboarding_config", "jira_email")
    op.drop_column("onboarding_config", "jira_api_token")
    op.drop_column("onboarding_config", "slack_bot_token")
