from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from app.models.user import User
from app.models.card import Card
from app.models.activity import Activity
from tests.conftest import TEST_USER


async def test_list_users_returns_list(auth_client, db_session):
    """GET /api/users returns list of users."""
    user1 = User(email="user1@example.com", display_name="Alice", region="us")
    user2 = User(email="user2@example.com", display_name="Bob", region="us")
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    resp = await auth_client.get("/api/users")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


async def test_list_users_excludes_current_user(auth_client, db_session):
    """GET /api/users excludes the current authenticated user."""
    user1 = User(email="api-key:test-key", display_name="Current User", region="us")
    user2 = User(email="other@example.com", display_name="Other User", region="us")
    db_session.add(user1)
    db_session.add(user2)
    await db_session.commit()

    resp = await auth_client.get("/api/users")
    assert resp.status_code == 200
    data = resp.json()
    emails = [u["email"] for u in data]
    assert "api-key:test-key" not in emails
    assert "other@example.com" in emails


async def test_get_user_profile_with_stats(auth_client, db_session):
    """GET /api/users/{email} returns profile with stats."""
    target_user = User(email="profile@example.com", display_name="Profile User", region="us")
    db_session.add(target_user)
    await db_session.commit()

    card1 = Card(
        user_identifier="profile@example.com",
        species_code="norcar",
        species_common="Northern Cardinal",
        rarity_tier="common",
    )
    card2 = Card(
        user_identifier="profile@example.com",
        species_code="amecro",
        species_common="American Crow",
        rarity_tier="common",
    )
    card3 = Card(
        user_identifier="profile@example.com",
        species_code="norcar",
        species_common="Northern Cardinal",
        rarity_tier="common",
    )
    db_session.add(card1)
    db_session.add(card2)
    db_session.add(card3)
    await db_session.commit()

    resp = await auth_client.get("/api/users/profile@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "profile@example.com"
    assert data["display_name"] == "Profile User"
    assert "stats" in data
    assert data["stats"]["total_cards"] == 3
    assert data["stats"]["unique_species"] == 2


async def test_get_user_profile_404(auth_client, db_session):
    """GET /api/users/{email} returns 404 for non-existent user."""
    resp = await auth_client.get("/api/users/nonexistent@example.com")
    assert resp.status_code == 404


async def test_collection_percent_calculation(auth_client, db_session):
    """collection_percent is calculated as unique_species / total region species."""
    target_user = User(email="stats@example.com", display_name="Stats User", region="us")
    db_session.add(target_user)
    await db_session.commit()

    card1 = Card(
        user_identifier="stats@example.com",
        species_code="norcar",
        species_common="Northern Cardinal",
        rarity_tier="common",
    )
    card2 = Card(
        user_identifier="stats@example.com",
        species_code="amecro",
        species_common="American Crow",
        rarity_tier="common",
    )
    db_session.add(card1)
    db_session.add(card2)
    await db_session.commit()

    resp = await auth_client.get("/api/users/stats@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert data["stats"]["unique_species"] == 2
    assert data["stats"]["total_cards"] == 2
    assert data["stats"]["collection_percent"] == round(2 / 704, 4)


async def test_get_user_profile_with_recent_activity(auth_client, db_session):
    """GET /api/users/{email} includes recent_activity."""
    target_user = User(email="activity@example.com", display_name="Activity User", region="us")
    db_session.add(target_user)
    await db_session.commit()

    for i in range(6):
        activity = Activity(
            user_identifier="activity@example.com",
            activity_type="sighting",
            reference_id=str(uuid.uuid4()),
            description=f"Test activity {i}",
        )
        db_session.add(activity)
    await db_session.commit()

    resp = await auth_client.get("/api/users/activity@example.com")
    assert resp.status_code == 200
    data = resp.json()
    assert "recent_activity" in data
    assert len(data["recent_activity"]) == 5
    assert all("activity_type" in a for a in data["recent_activity"])