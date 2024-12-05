"""Add error field to jobs table

Revision ID: add_error_to_jobs
Revises: previous_revision
Create Date: 2024-12-05 14:53:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_error_to_jobs'
down_revision = None  # Update this to point to your last migration
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('jobs', sa.Column('error', sa.String(), nullable=True))

def downgrade():
    op.drop_column('jobs', 'error') 