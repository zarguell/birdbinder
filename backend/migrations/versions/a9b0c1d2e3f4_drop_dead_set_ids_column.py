"""drop dead set_ids column from cards

The column was never written — set progress is computed from
CardSet.card_targets (species codes), not card membership.

Revision ID: a9b0c1d2e3f4
Revises: f7a8b9c0d1e2
Create Date: 2026-08-31 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

revision = "a9b0c1d2e3f4"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column("cards", "set_ids")


def downgrade():
    op.add_column("cards", sa.Column("set_ids", sa.JSON(), nullable=True))
