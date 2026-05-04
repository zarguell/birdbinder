"""Tests for card art regeneration endpoint."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from app.models.card import Card
from app.models.sighting import Sighting

TEST_API_KEY = "test-key-123"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"
OTHER_USER = f"api-key:other123"


def _make_card(db_session, user=TEST_USER, **kwargs):
    """Create a card directly in the DB."""
    card_id = str(uuid.uuid4())
    card = Card(
        id=card_id,
        sighting_id=kwargs.pop("sighting_id", str(uuid.uuid4())),
        user_identifier=user,
        species_common=kwargs.pop("species_common", "American Robin"),
        species_scientific=kwargs.pop("species_scientific", "Turdus migratorius"),
        species_code=kwargs.pop("species_code", "robib"),
        family=kwargs.pop("family", "Thrushes"),
        pose_variant=kwargs.pop("pose_variant", "perching"),
        rarity_tier=kwargs.pop("rarity_tier", "common"),
        card_art_url=kwargs.pop("card_art_url", "/storage/card_art/test.png"),
        id_method="ai",
        id_confidence=0.95,
        generated_at=datetime.now(timezone.utc),
        **kwargs,
    )
    db_session.add(card)
    return card


def _make_sighting_with_photo(db_session, user=TEST_USER, **kwargs):
    """Create a sighting with a photo path."""
    sighting = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=user,
        photo_path=kwargs.pop("photo_path", "sightings/test.jpg"),
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
    db_session.add(sighting)
    return sighting


async def test_regenerate_art_returns_job_id(auth_client, db_session):
    """POST /api/cards/{id}/regenerate-art should return job_id and 202."""
    card = _make_card(db_session)
    await db_session.commit()

    fake_job_id = str(uuid.uuid4())

    async def mock_start(card_id_arg, db, prompt_hint=None, style_override=None):
        return fake_job_id

    with patch(
        "app.services.card_gen.start_card_art_regeneration",
        side_effect=mock_start,
    ):
        response = await auth_client.post(f"/api/cards/{card.id}/regenerate-art")

    assert response.status_code == 202
    data = response.json()
    assert data["job_id"] == fake_job_id
    assert data["status"] == "pending"


async def test_regenerate_art_with_prompt_hint(auth_client, db_session):
    """POST /api/cards/{id}/regenerate-art with prompt_hint should pass it through."""
    card = _make_card(db_session)
    await db_session.commit()

    captured_args = {}

    async def mock_start(card_id_arg, db, prompt_hint=None, style_override=None):
        captured_args["card_id"] = card_id_arg
        captured_args["prompt_hint"] = prompt_hint
        captured_args["style_override"] = style_override
        return str(uuid.uuid4())

    with patch(
        "app.services.card_gen.start_card_art_regeneration",
        side_effect=mock_start,
    ):
        response = await auth_client.post(
            f"/api/cards/{card.id}/regenerate-art",
            json={"prompt_hint": "make it more vibrant"},
        )

    assert response.status_code == 202
    assert captured_args["card_id"] == card.id
    assert captured_args["prompt_hint"] == "make it more vibrant"
    assert captured_args["style_override"] is None


async def test_regenerate_art_with_style_override(auth_client, db_session):
    """POST /api/cards/{id}/regenerate-art with style_override should pass it through."""
    card = _make_card(db_session)
    await db_session.commit()

    captured_args = {}

    async def mock_start(card_id_arg, db, prompt_hint=None, style_override=None):
        captured_args["card_id"] = card_id_arg
        captured_args["prompt_hint"] = prompt_hint
        captured_args["style_override"] = style_override
        return str(uuid.uuid4())

    with patch(
        "app.services.card_gen.start_card_art_regeneration",
        side_effect=mock_start,
    ):
        response = await auth_client.post(
            f"/api/cards/{card.id}/regenerate-art",
            json={"style_override": "watercolor"},
        )

    assert response.status_code == 202
    assert captured_args["card_id"] == card.id
    assert captured_args["prompt_hint"] is None
    assert captured_args["style_override"] == "watercolor"


async def test_regenerate_art_with_both_hints(auth_client, db_session):
    """POST /api/cards/{id}/regenerate-art with both hints should pass both through."""
    card = _make_card(db_session)
    await db_session.commit()

    captured_args = {}

    async def mock_start(card_id_arg, db, prompt_hint=None, style_override=None):
        captured_args["card_id"] = card_id_arg
        captured_args["prompt_hint"] = prompt_hint
        captured_args["style_override"] = style_override
        return str(uuid.uuid4())

    with patch(
        "app.services.card_gen.start_card_art_regeneration",
        side_effect=mock_start,
    ):
        response = await auth_client.post(
            f"/api/cards/{card.id}/regenerate-art",
            json={"prompt_hint": "add flowers", "style_override": "oil painting"},
        )

    assert response.status_code == 202
    assert captured_args["card_id"] == card.id
    assert captured_args["prompt_hint"] == "add flowers"
    assert captured_args["style_override"] == "oil painting"


async def test_regenerate_art_nonexistent_card_returns_404(auth_client):
    """POST /api/cards/{id}/regenerate-art with non-existent card should return 404."""
    response = await auth_client.post(f"/api/cards/{str(uuid.uuid4())}/regenerate-art")
    assert response.status_code == 404


async def test_regenerate_art_wrong_user_returns_404(auth_client, db_session):
    """POST /api/cards/{id}/regenerate-art with wrong user should return 404."""
    card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    response = await auth_client.post(f"/api/cards/{card.id}/regenerate-art")
    assert response.status_code == 404


async def test_regenerate_art_no_body_still_works(auth_client, db_session):
    """POST /api/cards/{id}/regenerate-art without body should still work."""
    card = _make_card(db_session)
    await db_session.commit()

    fake_job_id = str(uuid.uuid4())

    async def mock_start(card_id_arg, db, prompt_hint=None, style_override=None):
        return fake_job_id

    with patch(
        "app.services.card_gen.start_card_art_regeneration",
        side_effect=mock_start,
    ):
        response = await auth_client.post(f"/api/cards/{card.id}/regenerate-art")

    assert response.status_code == 202
    assert response.json()["job_id"] == fake_job_id