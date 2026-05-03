"""Tests for card generation and CRUD endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.models.card import Card
from app.models.sighting import Sighting

TEST_API_KEY = "test-key-123"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"


def _make_identified_sighting(db_session, user=TEST_USER, **kwargs):
    """Create a sighting with status='identified' for card generation tests."""
    s = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=user,
        photo_path="sightings/test.jpg",
        thumbnail_path=None,
        submitted_at=datetime.now(timezone.utc),
        status="identified",
        species_code="robib",
        species_common="American Robin",
        species_scientific="Turdus migratorius",
        family="Thrushes",
        pose_variant="perching",
        id_confidence=0.95,
        id_method="ai",
        **kwargs,
    )
    db_session.add(s)
    return s


def _make_card(db_session, user=TEST_USER, rarity_tier="common", **kwargs):
    """Create a card directly in the DB for CRUD tests."""
    card_id = str(uuid.uuid4())
    card = Card(
        id=card_id,
        sighting_id=kwargs.pop("sighting_id", str(uuid.uuid4())),
        user_identifier=user,
        species_common=kwargs.pop("species_common", "American Robin"),
        species_scientific=kwargs.pop(
            "species_scientific", "Turdus migratorius"
        ),
        species_code=kwargs.pop("species_code", "robib"),
        family=kwargs.pop("family", "Thrushes"),
        pose_variant=kwargs.pop("pose_variant", "perching"),
        rarity_tier=rarity_tier,
        card_art_url="/api/storage/sightings/test.jpg",
        id_method="ai",
        id_confidence=0.95,
        generated_at=datetime.now(timezone.utc),
        **kwargs,
    )
    db_session.add(card)
    return card


# ---------------------------------------------------------------------------
# Card generation endpoint tests
# ---------------------------------------------------------------------------


async def test_generate_card_creates_job(auth_client, db_session):
    """POST /api/cards/generate/{sighting_id} should create a job and return 202."""
    sighting = _make_identified_sighting(db_session)
    await db_session.commit()

    fake_job_id = str(uuid.uuid4())

    async def mock_start_card_generation(sighting_id_arg, db):
        return fake_job_id

    with patch(
        "app.services.card_gen.start_card_generation",
        side_effect=mock_start_card_generation,
    ):
        response = await auth_client.post(f"/api/cards/generate/{sighting.id}")

    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == fake_job_id
    assert data["status"] == "pending"


async def test_generate_card_unidentified_returns_400(auth_client, db_session):
    """POST /api/cards/generate on a pending sighting should return 400."""
    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=TEST_USER,
        photo_path="sightings/test.jpg",
        submitted_at=datetime.now(timezone.utc),
        status="pending",
    )
    db_session.add(sighting)
    await db_session.commit()

    response = await auth_client.post(f"/api/cards/generate/{sighting.id}")
    assert response.status_code == 400
    assert "identified" in response.json()["detail"].lower()


async def test_generate_card_not_found_returns_404(auth_client):
    """POST /api/cards/generate on a non-existent sighting should return 404."""
    response = await auth_client.post(
        f"/api/cards/generate/{str(uuid.uuid4())}"
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# List cards tests
# ---------------------------------------------------------------------------


async def test_list_cards_empty(auth_client):
    """GET /api/cards with no cards should return empty list."""
    response = await auth_client.get("/api/cards")
    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["limit"] == 20
    assert data["offset"] == 0


async def test_list_cards_with_items(auth_client, db_session):
    """GET /api/cards should return cards for the authenticated user."""
    _make_card(db_session)
    _make_card(db_session, species_common="Blue Jay", species_code="blujay")
    await db_session.commit()

    response = await auth_client.get("/api/cards")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


async def test_list_cards_with_rarity_filter(auth_client, db_session):
    """GET /api/cards?rarity=rare should filter by rarity tier."""
    _make_card(db_session, rarity_tier="common")
    _make_card(
        db_session,
        rarity_tier="rare",
        species_common="Snowy Owl",
        species_code="snowl",
    )
    _make_card(db_session, rarity_tier="common", species_common="House Sparrow", species_code="housp")
    await db_session.commit()

    response = await auth_client.get("/api/cards?rarity=rare")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["species_common"] == "Snowy Owl"
    assert data["items"][0]["rarity_tier"] == "rare"


async def test_list_cards_pagination(auth_client, db_session):
    """GET /api/cards?limit=1&offset=0 should paginate correctly."""
    _make_card(db_session, species_common="Card A", species_code="carda")
    _make_card(db_session, species_common="Card B", species_code="cardb")
    _make_card(db_session, species_common="Card C", species_code="cardc")
    await db_session.commit()

    response = await auth_client.get("/api/cards?limit=1&offset=1")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 1


# ---------------------------------------------------------------------------
# Get card tests
# ---------------------------------------------------------------------------


async def test_get_card_by_id(auth_client, db_session):
    """GET /api/cards/{id} should return a single card."""
    card = _make_card(db_session)
    await db_session.commit()

    response = await auth_client.get(f"/api/cards/{card.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == card.id
    assert data["species_common"] == "American Robin"
    assert data["rarity_tier"] == "common"
    assert data["card_art_url"] == "/api/storage/sightings/test.jpg"
    assert data["user_identifier"] == TEST_USER


async def test_get_card_not_found_returns_404(auth_client):
    """GET /api/cards/{id} with unknown id should return 404."""
    response = await auth_client.get(f"/api/cards/{str(uuid.uuid4())}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Delete card tests
# ---------------------------------------------------------------------------


async def test_delete_card(auth_client, db_session):
    """DELETE /api/cards/{id} should delete the card."""
    card = _make_card(db_session)
    await db_session.commit()

    # Delete
    response = await auth_client.delete(f"/api/cards/{card.id}")
    assert response.status_code == 204

    # Verify it's gone
    response = await auth_client.get(f"/api/cards/{card.id}")
    assert response.status_code == 404


async def test_delete_card_not_found_returns_404(auth_client):
    """DELETE /api/cards/{id} with unknown id should return 404."""
    response = await auth_client.delete(f"/api/cards/{str(uuid.uuid4())}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


async def test_unauthenticated_returns_401(client):
    """All card endpoints should require authentication."""
    # Generate
    response = await client.post(
        f"/api/cards/generate/{str(uuid.uuid4())}"
    )
    assert response.status_code == 401

    # List
    response = await client.get("/api/cards")
    assert response.status_code == 401

    # Get
    response = await client.get(f"/api/cards/{str(uuid.uuid4())}")
    assert response.status_code == 401

    # Delete
    response = await client.delete(f"/api/cards/{str(uuid.uuid4())}")
    assert response.status_code == 401
