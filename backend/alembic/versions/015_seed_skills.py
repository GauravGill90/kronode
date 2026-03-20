"""seed curated skills from presets

Revision ID: 015
Revises: 014
Create Date: 2026-03-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import json


revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.skills.presets import SEED_SKILLS

    skills_table = sa.table(
        "skills",
        sa.column("key", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("category", sa.String),
        sa.column("stack_chips", JSONB),
        sa.column("system_prompt", sa.Text),
        sa.column("allowed_extensions", JSONB),
        sa.column("allowed_dirs", JSONB),
        sa.column("context_priorities", JSONB),
        sa.column("is_preset", sa.Boolean),
        sa.column("org_id", sa.Integer),
    )

    for skill in SEED_SKILLS:
        op.execute(
            skills_table.insert().values(
                key=skill["key"],
                name=skill["name"],
                description=skill.get("description", ""),
                category=skill["category"],
                stack_chips=skill.get("stack_chips", []),
                system_prompt=skill.get("system_prompt", ""),
                allowed_extensions=skill.get("allowed_extensions", []),
                allowed_dirs=skill.get("allowed_dirs", []),
                context_priorities=skill.get("context_priorities", []),
                is_preset=True,
                org_id=None,
            )
        )


def downgrade() -> None:
    op.execute("DELETE FROM skills WHERE is_preset = true AND org_id IS NULL")
