"""create doc_chunks table for agnostic document ingestion

Revision ID: 016
Revises: 015
Create Date: 2026-03-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "016"
down_revision: Union[str, None] = "001_pipeline_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doc_chunks",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("source_type", sa.String(50), nullable=False, index=True),
        sa.Column("source_ref", sa.String(500), nullable=False, index=True),
        sa.Column("source_url", sa.String(500), nullable=True),
        sa.Column("file_sha", sa.String(64), nullable=True),
        sa.Column("heading", sa.String(500), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_doc_chunks_org_source", "doc_chunks", ["org_id", "source_type"])


def downgrade() -> None:
    op.drop_index("ix_doc_chunks_org_source", table_name="doc_chunks")
    op.drop_table("doc_chunks")
