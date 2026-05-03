import io
import uuid
from PIL import Image

import pytest
from httpx import AsyncClient

from app.main import app
from app.models.sighting import Sighting

TEST_API_KEY = "test-key-123"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"


def _make_jpeg_bytes(width=800, height=600):
    """Create a minimal JPEG image in memory."""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)
    return buf


@pytest.mark.asyncio
async def test_create_sighting_with_image(auth_client, tmp_path):
    jpeg_bytes = _make_jpeg_bytes()
    response = await auth_client.post(
        "/api/sightings",
        files={"file": ("test.jpg", jpeg_bytes, "image/jpeg")},
        data={"notes": "Beautiful bird!", "location_display_name": "Central Park"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["user_identifier"] == TEST_USER
    assert data["photo_path"] is not None
    assert data["thumbnail_path"] is not None
    assert data["notes"] == "Beautiful bird!"
    assert data["location_display_name"] == "Central Park"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_create_sighting_without_image(auth_client):
    response = await auth_client.post(
        "/api/sightings",
        data={"notes": "No photo sighting"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["photo_path"] is None
    assert data["thumbnail_path"] is None
    assert data["notes"] == "No photo sighting"


@pytest.mark.asyncio
async def test_list_sightings_empty(auth_client):
    response = await auth_client.get("/api/sightings")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_list_sightings_paginated(auth_client, sighting):
    response = await auth_client.get("/api/sightings")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == sighting.id


@pytest.mark.asyncio
async def test_get_sighting_by_id(auth_client, sighting):
    response = await auth_client.get(f"/api/sightings/{sighting.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sighting.id
    assert data["user_identifier"] == TEST_USER
    assert data["notes"] == "Test sighting"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_sighting_not_found(auth_client):
    fake_id = str(uuid.uuid4())
    response = await auth_client.get(f"/api/sightings/{fake_id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_sighting(auth_client, sighting, db_session):
    # Delete
    response = await auth_client.delete(f"/api/sightings/{sighting.id}")
    assert response.status_code == 204

    # Verify it's gone
    response = await auth_client.get(f"/api/sightings/{sighting.id}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_no_auth_config_returns_local_user(client, db_engine):
    """When no auth is configured, requests without auth header proceed as 'local-user'."""
    from app.db import get_db
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Test list — should succeed (empty list)
        response = await client.get("/api/sightings")
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

        # Test get — should return 404 (no sighting found, not 401)
        response = await client.get(f"/api/sightings/{uuid.uuid4()}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
