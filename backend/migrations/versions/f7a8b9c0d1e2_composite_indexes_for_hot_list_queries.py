"""composite indexes for hot list queries

Revision ID: f7a8b9c0d1e2
Revises: e5f6a7b8c9d0
Create Date: 2026-08-30 14:00:00.000000
"""

from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


# (table, index name, columns) — every paginated list filters by
# user_identifier and orders by its timestamp column
_INDEXES = [
    ("sightings", "ix_sightings_user_submitted", ["user_identifier", "submitted_at"]),
    ("cards", "ix_cards_user_generated", ["user_identifier", "generated_at"]),
    ("activities", "ix_activities_user_created", ["user_identifier", "created_at"]),
    # identification progress polling filters on this triple
    ("jobs", "ix_jobs_sighting_type_status", ["sighting_id", "type", "status"]),
]


def upgrade():
    for table, name, cols in _INDEXES:
        op.create_index(name, table, cols)


def downgrade():
    for table, name, cols in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
