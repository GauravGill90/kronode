"""add celery_task_id to tasks

Revision ID: 005
Revises: 004
Create Date: 2026-02-26
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("celery_task_id", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("tasks", "celery_task_id")
