from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.config import settings
import os

db_path = settings.database_url.replace("sqlite+aiosqlite:///", "./")
os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

_sync_db_url = settings.database_url.replace("sqlite+aiosqlite", "sqlite")
sync_engine = create_engine(_sync_db_url)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
