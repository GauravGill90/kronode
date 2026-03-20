"""create conventions table

Revision ID: 010
Revises: 009
Create Date: 2026-03-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conventions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=True, index=True),
        sa.Column("rule", sa.Text, nullable=False),
        sa.Column("category", sa.String(50), nullable=False, index=True),
        sa.Column("examples", JSONB, nullable=True),
        sa.Column("frequency", sa.Integer, default=1),
        sa.Column("confidence", sa.Float, default=0.5),
        sa.Column("layer", sa.String(20), default="customer"),
        sa.Column("source_prs", JSONB, nullable=True),
        sa.Column("suppressed", sa.Boolean, default=False),
        sa.Column("suppressed_by", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("conventions")
