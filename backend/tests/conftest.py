import os
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db import Base, get_db

# Test API key matching what auth expects
TEST_API_KEY = "test-key-123"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {TEST_API_KEY}"}


@pytest.fixture(scope="session")
def event_loop_policy():
    """Use default event loop policy."""
    import asyncio
    return asyncio.DefaultEventLoopPolicy()


@pytest.fixture(scope="function")
async def db_engine(tmp_path):
    """Create an in-memory SQLite engine for tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(db_engine):
    """Provide an async database session for tests."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest.fixture
async def client():
    """Unauthenticated client (no auth header)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_client(db_engine):
    """Authenticated test client with in-memory DB override."""
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db

    # Mock API key validation to accept our test key
    with patch("app.dependencies.validate_api_key", return_value=TEST_USER):
        with patch("app.auth.validate_api_key", return_value=TEST_USER):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                ac.headers["Authorization"] = f"Bearer {TEST_API_KEY}"
                yield ac

    # Clean up overrides
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def sighting(auth_client, db_session):
    """Create a test sighting in the DB and return it."""
    from app.models.sighting import Sighting

    s = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path=None,
        thumbnail_path=None,
        submitted_at=datetime.now(timezone.utc),
        notes="Test sighting",
        status="pending",
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)
    return s
