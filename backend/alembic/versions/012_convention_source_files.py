"""add source_files column to conventions

Revision ID: 012
Revises: 011
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("conventions", sa.Column("source_files", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("conventions", "source_files")
