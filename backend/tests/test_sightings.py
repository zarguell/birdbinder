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
async def test_delete_sighting_cascades_to_cards(auth_client, db_session):
    """Deleting a sighting should also delete its cards."""
    from app.models.sighting import Sighting
    from app.models.card import Card

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        status="identified",
        species_code="norcar",
        species_common="Northern Cardinal",
    )
    db_session.add(sighting)
    await db_session.flush()

    card = Card(
        id=str(uuid.uuid4()),
        sighting_id=sighting.id,
        user_identifier=TEST_USER,
        species_common="Northern Cardinal",
        species_code="norcar",
    )
    db_session.add(card)
    await db_session.commit()

    # Delete the sighting
    resp = await auth_client.delete(f"/api/sightings/{sighting.id}")
    assert resp.status_code == 204

    # Verify sighting is gone
    resp = await auth_client.get(f"/api/sightings/{sighting.id}")
    assert resp.status_code == 404

    # Verify card is gone
    from sqlalchemy import select as sa_select
    result = await db_session.execute(sa_select(Card).where(Card.id == card.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_sighting_cascades_to_jobs(auth_client, db_session):
    """Deleting a sighting should also delete its jobs."""
    from app.models.sighting import Sighting
    from app.models.job import Job

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        status="pending",
    )
    db_session.add(sighting)
    await db_session.flush()

    job = Job(
        id=str(uuid.uuid4()),
        sighting_id=sighting.id,
        type="identify",
        status="completed",
    )
    db_session.add(job)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/sightings/{sighting.id}")
    assert resp.status_code == 204

    from sqlalchemy import select as sa_select
    result = await db_session.execute(sa_select(Job).where(Job.id == job.id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_sighting_cascades_to_activities(auth_client, db_session):
    """Deleting a sighting should delete sighting and card activities."""
    from app.models.sighting import Sighting
    from app.models.card import Card
    from app.models.activity import Activity
    from sqlalchemy import select as sa_select

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        status="identified",
        species_code="norcar",
        species_common="Northern Cardinal",
    )
    db_session.add(sighting)
    await db_session.flush()

    card = Card(
        id=str(uuid.uuid4()),
        sighting_id=sighting.id,
        user_identifier=TEST_USER,
        species_common="Northern Cardinal",
        species_code="norcar",
    )
    db_session.add(card)
    await db_session.flush()

    sighting_activity = Activity(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        activity_type="sighting",
        reference_id=sighting.id,
        description="New sighting",
    )
    card_activity = Activity(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        activity_type="card",
        reference_id=card.id,
        description="New card earned",
    )
    db_session.add(sighting_activity)
    db_session.add(card_activity)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/sightings/{sighting.id}")
    assert resp.status_code == 204

    # Both activities should be gone
    result = await db_session.execute(
        sa_select(Activity).where(Activity.id == sighting_activity.id)
    )
    assert result.scalar_one_or_none() is None

    result = await db_session.execute(
        sa_select(Activity).where(Activity.id == card_activity.id)
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_delete_sighting_cascades_to_binder_cards(auth_client, db_session):
    """Deleting a sighting should cascade: sighting → card → binder_card."""
    from app.models.sighting import Sighting
    from app.models.card import Card
    from app.models.binder import Binder, BinderCard
    from sqlalchemy import select as sa_select

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        status="identified",
        species_code="norcar",
        species_common="Northern Cardinal",
    )
    db_session.add(sighting)
    await db_session.flush()

    card = Card(
        id=str(uuid.uuid4()),
        sighting_id=sighting.id,
        user_identifier=TEST_USER,
        species_common="Northern Cardinal",
        species_code="norcar",
    )
    db_session.add(card)
    await db_session.flush()

    binder = Binder(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        name="My Binder",
    )
    db_session.add(binder)
    await db_session.flush()

    binder_card = BinderCard(
        id=str(uuid.uuid4()),
        binder_id=binder.id,
        card_id=card.id,
        position=0,
    )
    db_session.add(binder_card)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/sightings/{sighting.id}")
    assert resp.status_code == 204

    # Binder card should be gone (cascade via card FK)
    result = await db_session.execute(
        sa_select(BinderCard).where(BinderCard.id == binder_card.id)
    )
    assert result.scalar_one_or_none() is None

    # Card should be gone
    result = await db_session.execute(
        sa_select(Card).where(Card.id == card.id)
    )
    assert result.scalar_one_or_none() is None

    # Binder itself should still exist
    result = await db_session.execute(
        sa_select(Binder).where(Binder.id == binder.id)
    )
    assert result.scalar_one_or_none() is not None


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


@pytest.mark.asyncio
async def test_update_sighting_location(auth_client, db_session):
    """PATCH location fields (latitude, longitude, location_display_name)."""
    from app.models.sighting import Sighting

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path="sightings/test.jpg",
    )
    db_session.add(sighting)
    await db_session.commit()
    sid = sighting.id

    resp = await auth_client.patch(
        f"/api/sightings/{sid}",
        json={
            "latitude": 40.7128,
            "longitude": -74.0060,
            "location_display_name": "New York, NY",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exif_lat"] == 40.7128
    assert data["exif_lon"] == -74.0060
    assert data["location_display_name"] == "New York, NY"


@pytest.mark.asyncio
async def test_update_location_invalid_lat(auth_client, db_session):
    """Latitude out of range returns 422."""
    from app.models.sighting import Sighting

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path="sightings/test.jpg",
    )
    db_session.add(sighting)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"latitude": 999},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_location_invalid_lon(auth_client, db_session):
    """Longitude out of range returns 422."""
    from app.models.sighting import Sighting

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path="sightings/test.jpg",
    )
    db_session.add(sighting)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"longitude": 999},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_location_partial(auth_client, db_session):
    """Patching only latitude leaves longitude unchanged."""
    from app.models.sighting import Sighting

    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path="sightings/test.jpg",
        exif_lat=0.0,
        exif_lon=0.0,
    )
    db_session.add(sighting)
    await db_session.commit()

    resp = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"latitude": 40.0},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["exif_lat"] == 40.0
    assert data["exif_lon"] == 0.0  # unchanged
