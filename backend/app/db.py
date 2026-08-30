from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
import os

db_path = settings.database_url.replace("sqlite+aiosqlite:///", "./")
os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)


def _sqlite_pragmas(dbapi_conn, _record):
    """Harden SQLite for concurrent writers (uvicorn + huey workers).

    WAL allows readers during writes; busy_timeout makes concurrent writers
    wait instead of failing with 'database is locked'; FK enforcement matches
    the SQLAlchemy model declarations.
    """
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


engine = create_async_engine(settings.database_url, echo=False)
event.listen(engine.sync_engine, "connect", _sqlite_pragmas)
async_session = async_sessionmaker(engine, expire_on_commit=False)

_sync_db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
sync_engine = create_engine(_sync_db_url)
event.listen(sync_engine, "connect", _sqlite_pragmas)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
