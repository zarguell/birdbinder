"""Tests for trading API endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.models.card import Card
from app.models.trade import Trade
from tests.conftest import TEST_API_KEY, TEST_USER

OTHER_USER = "other-user"


def _make_card(db_session, user=TEST_USER, tradeable=True, duplicate_count=2, **kwargs):
    """Create a card directly in the DB for trade tests."""
    card = Card(
        id=kwargs.pop("card_id", str(uuid.uuid4())),
        sighting_id=kwargs.pop("sighting_id", str(uuid.uuid4())),
        user_identifier=user,
        species_common=kwargs.pop("species_common", "American Robin"),
        species_scientific=kwargs.pop("species_scientific", "Turdus migratorius"),
        species_code=kwargs.pop("species_code", "robib"),
        family=kwargs.pop("family", "Thrushes"),
        pose_variant=kwargs.pop("pose_variant", "perching"),
        rarity_tier=kwargs.pop("rarity_tier", "common"),
        card_art_url="/api/storage/test.jpg",
        id_method="ai",
        id_confidence=0.95,
        duplicate_count=duplicate_count,
        tradeable=tradeable,
        generated_at=datetime.now(timezone.utc),
        **kwargs,
    )
    db_session.add(card)
    return card


# ---------------------------------------------------------------------------
# Create trade tests
# ---------------------------------------------------------------------------


async def test_create_trade(auth_client, db_session):
    """POST /api/trades should create a trade and return 201."""
    offered_card = _make_card(db_session)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    response = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["offered_by"] == TEST_USER
    assert data["offered_to"] == OTHER_USER
    assert data["status"] == "pending"
    assert data["offered_card_ids"] == [offered_card.id]
    assert data["requested_card_ids"] == [requested_card.id]


async def test_create_trade_self_fails(auth_client, db_session):
    """POST /api/trades with offered_to == offered_by should return 422."""
    card = _make_card(db_session)
    await db_session.commit()

    response = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": TEST_USER,
            "offered_card_ids": [card.id],
            "requested_card_ids": [],
        },
    )
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("yourself" in e for e in errors)


async def test_create_trade_nonexistent_card_fails(auth_client, db_session):
    """POST /api/trades with nonexistent offered card should return 422."""
    fake_id = str(uuid.uuid4())
    response = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [fake_id],
            "requested_card_ids": [],
        },
    )
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("not found" in e for e in errors)


async def test_create_trade_other_user_card_fails(auth_client, db_session):
    """POST /api/trades offering someone else's card should return 422."""
    # Card belongs to OTHER_USER, not TEST_USER
    other_card = _make_card(db_session, user=OTHER_USER)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    response = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [other_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("does not belong" in e for e in errors)


async def test_create_trade_non_tradeable_card_fails(auth_client, db_session):
    """POST /api/trades with non-tradeable card should return 422."""
    card = _make_card(db_session, tradeable=False)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    response = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    assert response.status_code == 422
    errors = response.json()["detail"]["errors"]
    assert any("not tradeable" in e for e in errors)


# ---------------------------------------------------------------------------
# List trades tests
# ---------------------------------------------------------------------------


async def test_list_trades(auth_client, db_session):
    """GET /api/trades should return trades involving the current user."""
    offered_card = _make_card(db_session)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    # Create a trade
    trade_resp = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    assert trade_resp.status_code == 201

    response = await auth_client.get("/api/trades")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["id"] == trade_resp.json()["id"]


async def test_list_trades_filtered(auth_client, db_session):
    """GET /api/trades?status=accepted should filter by status."""
    offered_card = _make_card(db_session)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    # Create trade
    trade_resp = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    trade_id = trade_resp.json()["id"]

    # Accept it as OTHER_USER
    with patch("app.dependencies.validate_api_key", return_value=OTHER_USER):
        with patch("app.auth.validate_api_key", return_value=OTHER_USER):
            accept_resp = await auth_client.post(f"/api/trades/{trade_id}/accept")
    assert accept_resp.status_code == 200

    # List pending trades — should be empty
    response = await auth_client.get("/api/trades?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0

    # List accepted trades — should have 1
    response = await auth_client.get("/api/trades?status=accepted")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1


# ---------------------------------------------------------------------------
# Get trade tests
# ---------------------------------------------------------------------------


async def test_get_trade(auth_client, db_session):
    """GET /api/trades/{id} should return the trade."""
    offered_card = _make_card(db_session)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    create_resp = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    trade_id = create_resp.json()["id"]

    response = await auth_client.get(f"/api/trades/{trade_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == trade_id
    assert data["status"] == "pending"


async def test_get_trade_not_yours(auth_client, db_session):
    """GET /api/trades/{id} for a trade not involving user should return 403."""
    # Create a trade between two other users
    trade = Trade(
        id=str(uuid.uuid4()),
        offered_by="user-a",
        offered_to="user-b",
        offered_card_ids=[str(uuid.uuid4())],
        requested_card_ids=[str(uuid.uuid4())],
        status="pending",
    )
    db_session.add(trade)
    await db_session.commit()

    response = await auth_client.get(f"/api/trades/{trade.id}")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Accept trade tests
# ---------------------------------------------------------------------------


async def test_accept_trade(auth_client, db_session):
    """POST /api/trades/{id}/accept should transfer card ownership."""
    offered_card = _make_card(db_session, duplicate_count=3)
    requested_card = _make_card(db_session, user=OTHER_USER, duplicate_count=2)
    await db_session.commit()

    # Create trade as TEST_USER
    create_resp = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    trade_id = create_resp.json()["id"]

    # Accept as OTHER_USER
    with patch("app.dependencies.validate_api_key", return_value=OTHER_USER):
        with patch("app.auth.validate_api_key", return_value=OTHER_USER):
            accept_resp = await auth_client.post(f"/api/trades/{trade_id}/accept")

    assert accept_resp.status_code == 200
    data = accept_resp.json()
    assert data["status"] == "accepted"
    assert data["resolved_at"] is not None

    # Verify card ownership swapped
    await db_session.refresh(offered_card)
    await db_session.refresh(requested_card)
    assert offered_card.user_identifier == OTHER_USER
    assert requested_card.user_identifier == TEST_USER
    # Verify duplicate_count decreased
    assert offered_card.duplicate_count == 2
    assert requested_card.duplicate_count == 1


async def test_accept_trade_already_resolved(auth_client, db_session):
    """POST /api/trades/{id}/accept on a non-pending trade should return 409."""
    offered_card = _make_card(db_session)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    create_resp = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    trade_id = create_resp.json()["id"]

    # Cancel first
    cancel_resp = await auth_client.post(f"/api/trades/{trade_id}/cancel")
    assert cancel_resp.status_code == 200

    # Now try to accept — should fail
    with patch("app.dependencies.validate_api_key", return_value=OTHER_USER):
        with patch("app.auth.validate_api_key", return_value=OTHER_USER):
            accept_resp = await auth_client.post(f"/api/trades/{trade_id}/accept")
    assert accept_resp.status_code == 409


# ---------------------------------------------------------------------------
# Decline trade tests
# ---------------------------------------------------------------------------


async def test_decline_trade(auth_client, db_session):
    """POST /api/trades/{id}/decline should mark trade as declined."""
    offered_card = _make_card(db_session)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    create_resp = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    trade_id = create_resp.json()["id"]

    # Decline as OTHER_USER
    with patch("app.dependencies.validate_api_key", return_value=OTHER_USER):
        with patch("app.auth.validate_api_key", return_value=OTHER_USER):
            decline_resp = await auth_client.post(f"/api/trades/{trade_id}/decline")

    assert decline_resp.status_code == 200
    data = decline_resp.json()
    assert data["status"] == "declined"
    assert data["resolved_at"] is not None


# ---------------------------------------------------------------------------
# Cancel trade tests
# ---------------------------------------------------------------------------


async def test_cancel_trade(auth_client, db_session):
    """POST /api/trades/{id}/cancel should mark trade as cancelled."""
    offered_card = _make_card(db_session)
    requested_card = _make_card(db_session, user=OTHER_USER)
    await db_session.commit()

    create_resp = await auth_client.post(
        "/api/trades",
        json={
            "offered_to": OTHER_USER,
            "offered_card_ids": [offered_card.id],
            "requested_card_ids": [requested_card.id],
        },
    )
    trade_id = create_resp.json()["id"]

    cancel_resp = await auth_client.post(f"/api/trades/{trade_id}/cancel")
    assert cancel_resp.status_code == 200
    data = cancel_resp.json()
    assert data["status"] == "cancelled"
    assert data["resolved_at"] is not None


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


async def test_unauthenticated_returns_401(client):
    """All trade endpoints should require authentication."""
    # Create
    response = await client.post(
        "/api/trades",
        json={
            "offered_to": "other-user",
            "offered_card_ids": [],
            "requested_card_ids": [],
        },
    )
    assert response.status_code == 401

    # List
    response = await client.get("/api/trades")
    assert response.status_code == 401

    # Get
    response = await client.get(f"/api/trades/{str(uuid.uuid4())}")
    assert response.status_code == 401

    # Accept
    response = await client.post(f"/api/trades/{str(uuid.uuid4())}/accept")
    assert response.status_code == 401

    # Decline
    response = await client.post(f"/api/trades/{str(uuid.uuid4())}/decline")
    assert response.status_code == 401

    # Cancel
    response = await client.post(f"/api/trades/{str(uuid.uuid4())}/cancel")
    assert response.status_code == 401
