"""Startup helper: ensure all model columns exist in the database.

Runs after Alembic migrations as a safety net. Alembic handles intentional
schema changes; this catches cases where a model column was added without a
corresponding migration (e.g. quick prototyping, missed migration generation).

Only adds nullable columns — breaking changes (NOT NULL, type changes) still
require proper Alembic migrations.
"""
from __future__ import annotations

import logging
from sqlalchemy import create_engine, inspect, text

logger = logging.getLogger(__name__)


def ensure_columns(database_url: str) -> int:
    """Check all mapped columns exist in the DB; add missing nullable ones.

    Returns the number of columns added.
    """
    from app.db import Base

    # Convert async URL to sync for inspection
    sync_url = database_url.replace("sqlite+aiosqlite", "sqlite")
    engine = create_engine(sync_url)

    try:
        inspector = inspect(engine)
        added = 0

        for mapper in Base.registry.mappers:
            table = mapper.local_table
            table_name = table.name

            if table_name not in inspector.get_table_names():
                continue  # Let Alembic / create_all handle missing tables

            existing = {c["name"] for c in inspector.get_columns(table_name)}

            for col in table.columns:
                if col.name in existing:
                    continue

                # Only add nullable columns automatically
                if not col.nullable:
                    logger.warning(
                        "Column %s.%s is NOT NULL — skipping auto-add, "
                        "create a proper Alembic migration instead",
                        table_name, col.name,
                    )
                    continue

                col_type = col.type.compile(dialect=engine.dialect)
                ddl = f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}"
                logger.info("Adding missing column: %s", ddl)
                with engine.begin() as conn:
                    conn.execute(text(ddl))
                added += 1

        return added
    finally:
        engine.dispose()
