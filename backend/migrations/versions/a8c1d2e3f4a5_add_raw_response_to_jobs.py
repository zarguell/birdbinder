"""add raw_response to jobs

Revision ID: a8c1d2e3f4a5
Revises: 359718292a7e
Create Date: 2026-05-03 17:55:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "a8c1d2e3f4a5"
down_revision = "359718292a7e"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("jobs", sa.Column("raw_response", sa.String(5000), nullable=True))


def downgrade():
    op.drop_column("jobs", "raw_response")
