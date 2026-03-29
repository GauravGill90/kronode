"""add pipeline_state column to tasks

Revision ID: 001_pipeline_state
Revises:
Create Date: 2025-03-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_pipeline_state'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade():
    # Add JSONB column for pipeline state
    op.add_column(
        'tasks',
        sa.Column('pipeline_state', postgresql.JSONB(), nullable=True)
    )
    # Add PR info columns (used by orchestrator)
    op.add_column('tasks', sa.Column('pr_url', sa.String(500), nullable=True))
    op.add_column('tasks', sa.Column('pr_number', sa.Integer(), nullable=True))
    op.add_column('tasks', sa.Column('branch_name', sa.String(255), nullable=True))
    op.add_column('tasks', sa.Column('error_message', sa.Text(), nullable=True))

    # Add index for faster queries on state status
    op.execute("""
        CREATE INDEX idx_tasks_pipeline_state_status
        ON tasks ((pipeline_state->>'status'))
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_tasks_pipeline_state_status")
    op.drop_column('tasks', 'error_message')
    op.drop_column('tasks', 'branch_name')
    op.drop_column('tasks', 'pr_number')
    op.drop_column('tasks', 'pr_url')
    op.drop_column('tasks', 'pipeline_state')
