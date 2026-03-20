"""add stack column to conventions

Revision ID: 013
Revises: 012
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conventions", sa.Column("stack", sa.String(50), nullable=True))
    # Tag existing base conventions as typescript (extracted from Cal.com)
    op.execute("UPDATE conventions SET stack = 'typescript' WHERE layer = 'base' AND stack IS NULL")


def downgrade() -> None:
    op.drop_column("conventions", "stack")
