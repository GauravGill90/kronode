"""add plan_snapshot column to tasks

Revision ID: 009
Revises: 008
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "009"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("plan_snapshot", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "plan_snapshot")
