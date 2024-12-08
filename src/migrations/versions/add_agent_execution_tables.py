"""add agent execution tables

Revision ID: add_agent_execution_tables
Revises: add_event_log_table
Create Date: 2024-01-20 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = "add_agent_execution_tables"
down_revision = "add_event_log_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agent_executions table
    op.create_table(
        "agent_executions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("agent_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("trigger", sa.String(), nullable=True),
        sa.Column("input_data", JSON, nullable=True),
        sa.Column("result", JSON, nullable=True),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("steps_taken", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create agent_execution_steps table
    op.create_table(
        "agent_execution_steps",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("execution_id", sa.String(), nullable=False),
        sa.Column("step_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("input_data", JSON, nullable=True),
        sa.Column("output_data", JSON, nullable=True),
        sa.Column("reasoning", sa.String(), nullable=True),
        sa.Column("next_action", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["agent_executions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Add indexes
    op.create_index(op.f("ix_agent_executions_agent_type"), "agent_executions", ["agent_type"], unique=False)
    op.create_index(op.f("ix_agent_executions_status"), "agent_executions", ["status"], unique=False)
    op.create_index(op.f("ix_agent_executions_created_at"), "agent_executions", ["created_at"], unique=False)
    op.create_index(op.f("ix_agent_execution_steps_execution_id"), "agent_execution_steps", ["execution_id"], unique=False)
    op.create_index(op.f("ix_agent_execution_steps_step_number"), "agent_execution_steps", ["step_number"], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f("ix_agent_execution_steps_step_number"), table_name="agent_execution_steps")
    op.drop_index(op.f("ix_agent_execution_steps_execution_id"), table_name="agent_execution_steps")
    op.drop_index(op.f("ix_agent_executions_created_at"), table_name="agent_executions")
    op.drop_index(op.f("ix_agent_executions_status"), table_name="agent_executions")
    op.drop_index(op.f("ix_agent_executions_agent_type"), table_name="agent_executions")

    # Drop tables
    op.drop_table("agent_execution_steps")
    op.drop_table("agent_executions")
