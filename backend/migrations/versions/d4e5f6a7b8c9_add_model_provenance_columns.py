"""add_model_provenance_columns

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-05

Adds art_model to cards (which AI model generated the card art)
and id_model to sightings (which AI model identified the species).
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cards", sa.Column("art_model", sa.String(255), nullable=True))
    op.add_column("sightings", sa.Column("id_model", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("sightings", "id_model")
    op.drop_column("cards", "art_model")
