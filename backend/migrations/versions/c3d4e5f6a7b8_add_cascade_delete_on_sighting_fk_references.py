"""add cascade delete on sighting fk references

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-05-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite requires batch mode to modify FK constraints.
    # ondelete CASCADE on cards.sighting_id
    with op.batch_alter_table('cards') as batch_op:
        batch_op.drop_constraint('cards_sighting_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'cards_sighting_id_fkey', 'sightings', ['sighting_id'], ['id'],
            ondelete='CASCADE',
        )

    # ondelete CASCADE on jobs.sighting_id
    with op.batch_alter_table('jobs') as batch_op:
        batch_op.drop_constraint('jobs_sighting_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'jobs_sighting_id_fkey', 'sightings', ['sighting_id'], ['id'],
            ondelete='CASCADE',
        )


def downgrade() -> None:
    with op.batch_alter_table('cards') as batch_op:
        batch_op.drop_constraint('cards_sighting_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'cards_sighting_id_fkey', 'sightings', ['sighting_id'], ['id'],
        )

    with op.batch_alter_table('jobs') as batch_op:
        batch_op.drop_constraint('jobs_sighting_id_fkey', type_='foreignkey')
        batch_op.create_foreign_key(
            'jobs_sighting_id_fkey', 'sightings', ['sighting_id'], ['id'],
        )
