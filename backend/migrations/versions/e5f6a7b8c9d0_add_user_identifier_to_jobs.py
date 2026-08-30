"""add user_identifier to jobs

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-30 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "jobs", sa.Column("user_identifier", sa.String(255), nullable=True)
    )
    # Backfill ownership from the sighting each job belongs to
    op.execute(
        """
        UPDATE jobs
        SET user_identifier = (
            SELECT s.user_identifier FROM sightings s WHERE s.id = jobs.sighting_id
        )
        WHERE user_identifier IS NULL AND sighting_id IS NOT NULL
        """
    )
    op.create_index("ix_jobs_user_identifier", "jobs", ["user_identifier"])


def downgrade():
    op.drop_index("ix_jobs_user_identifier", table_name="jobs")
    op.drop_column("jobs", "user_identifier")
