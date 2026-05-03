import uuid

import pytest
from httpx import AsyncClient

from app.main import app

TEST_API_KEY = "***"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"


async def test_manual_species_override(auth_client, sighting):
    """Override with valid species_code 'amerob', verify fields populated."""
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"species_code": "amerob"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["species_code"] == "amerob"
    assert data["species_common"] == "American Robin"
    assert data["species_scientific"] == "Turdus migratorius"
    assert data["family"] == "Thrushes and Allies"
    assert data["manual_species_override"] is True
    assert data["status"] == "identified"
    assert data["id_method"] == "manual"
    assert data["id_confidence"] == 1.0


async def test_species_code_is_case_insensitive(auth_client, sighting):
    """Species code lookup should be case-insensitive."""
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"species_code": "AMEROB"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["species_code"] == "amerob"
    assert data["species_common"] == "American Robin"


async def test_invalid_pose_rejected(auth_client, sighting):
    """PATCH with pose_variant 'breakdancing' should return 422."""
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"pose_variant": "breakdancing"},
    )
    assert response.status_code == 422
    assert "Invalid pose variant" in response.json()["detail"]


async def test_unknown_species_code_rejected(auth_client, sighting):
    """PATCH with species_code 'notexist' should return 422."""
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"species_code": "notexist"},
    )
    assert response.status_code == 422
    assert "Unknown species code" in response.json()["detail"]


async def test_override_nonexistent_sighting(auth_client):
    """PATCH to non-existent ID should return 404."""
    fake_id = str(uuid.uuid4())
    response = await auth_client.patch(
        f"/api/sightings/{fake_id}",
        json={"species_code": "amerob"},
    )
    assert response.status_code == 404


async def test_override_other_user_sighting_rejected(auth_client, db_session):
    """PATCH to another user's sighting should return 404."""
    from datetime import datetime, timezone
    from app.models.sighting import Sighting

    s = Sighting(
        id=str(uuid.uuid4()),
        user_identifier="api-key:other",
        submitted_at=datetime.now(timezone.utc),
        notes="Other user sighting",
        status="pending",
    )
    db_session.add(s)
    await db_session.commit()
    await db_session.refresh(s)

    response = await auth_client.patch(
        f"/api/sightings/{s.id}",
        json={"species_code": "amerob"},
    )
    assert response.status_code == 404


async def test_pose_only_override(auth_client, sighting):
    """PATCH with only pose_variant should set pose without touching species."""
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"pose_variant": "flying"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pose_variant"] == "flying"
    # Species fields should remain null since no species was provided
    assert data["species_code"] is None
    assert data["species_common"] is None
    # Status should NOT change to identified when only pose is set
    assert data["status"] == "pending"


async def test_override_with_both_species_and_pose(auth_client, sighting):
    """PATCH with both species_code and pose_variant sets both."""
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"species_code": "amerob", "pose_variant": "perching"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["species_code"] == "amerob"
    assert data["species_common"] == "American Robin"
    assert data["pose_variant"] == "perching"
    assert data["status"] == "identified"


async def test_override_updates_existing_species(auth_client, sighting):
    """Re-overriding species replaces the previous values."""
    # First override
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"species_code": "amerob"},
    )
    assert response.status_code == 200
    assert response.json()["species_common"] == "American Robin"

    # Second override to a different species
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={"species_code": "ostric2"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["species_code"] == "ostric2"
    assert data["species_common"] == "Common Ostrich"
    assert data["species_scientific"] == "Struthio camelus"
    assert data["manual_species_override"] is True


async def test_override_empty_body_has_no_effect(auth_client, sighting):
    """PATCH with empty JSON body should return sighting unchanged."""
    response = await auth_client.patch(
        f"/api/sightings/{sighting.id}",
        json={},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["species_code"] is None
    assert data["status"] == "pending"


async def test_override_no_auth_config_returns_local_user(client, db_engine):
    """When no auth is configured, PATCH proceeds as 'local-user'."""
    from app.db import get_db
    from sqlalchemy.ext.asyncio import async_sessionmaker

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Should return 404 (sighting not found, not 401)
        response = await client.patch(
            f"/api/sightings/{uuid.uuid4()}",
            json={"species_code": "amerob"},
        )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
