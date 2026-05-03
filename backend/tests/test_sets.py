import uuid
from unittest.mock import patch

TEST_API_KEY = "test-key-123"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"
TEST_USER_2 = "api-key:otherus"


async def test_create_set(auth_client, db_session):
    resp = await auth_client.post("/api/sets", json={
        "name": "Spring Migrants",
        "description": "Common spring birds",
        "region": "Northeast",
        "card_targets": ["AMROB", "NOCAH", "BAWWAR"],
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Spring Migrants"
    assert data["description"] == "Common spring birds"
    assert data["region"] == "Northeast"
    assert data["card_targets"] == ["AMROB", "NOCAH", "BAWWAR"]
    assert data["creator_identifier"] == TEST_USER
    assert "id" in data
    assert data["created_at"] is not None


async def test_create_set_minimal(auth_client, db_session):
    resp = await auth_client.post("/api/sets", json={"name": "Minimal Set"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Minimal Set"
    assert data["description"] is None
    assert data["card_targets"] == []
    assert data["region"] is None


async def test_list_sets_empty(auth_client):
    resp = await auth_client.get("/api/sets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


async def test_list_sets_with_items(auth_client, db_session):
    from app.models.set import CardSet

    for name in ["Set A", "Set B", "Set C"]:
        db_session.add(CardSet(creator_identifier=TEST_USER, name=name))
    await db_session.commit()

    resp = await auth_client.get("/api/sets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    # Most recent first (order by created_at desc)
    names = [i["name"] for i in data["items"]]
    assert names == ["Set C", "Set B", "Set A"]


async def test_get_set_by_id(auth_client, db_session):
    from app.models.set import CardSet

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="Test Set",
        card_targets=["AMROB", "NOCAH"],
    )
    db_session.add(card_set)
    await db_session.commit()
    await db_session.refresh(card_set)

    resp = await auth_client.get(f"/api/sets/{card_set.id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == card_set.id
    assert data["name"] == "Test Set"
    assert data["card_targets"] == ["AMROB", "NOCAH"]


async def test_get_set_not_found(auth_client):
    resp = await auth_client.get("/api/sets/nonexistent-id")
    assert resp.status_code == 404


async def test_update_set(auth_client, db_session):
    from app.models.set import CardSet

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="Original Name",
        description="Original desc",
    )
    db_session.add(card_set)
    await db_session.commit()
    await db_session.refresh(card_set)

    resp = await auth_client.patch(f"/api/sets/{card_set.id}", json={
        "description": "Updated desc",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Original Name"  # unchanged
    assert data["description"] == "Updated desc"


async def test_update_non_creator_returns_404(auth_client, db_session):
    from app.models.set import CardSet

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="My Set",
    )
    db_session.add(card_set)
    await db_session.commit()
    await db_session.refresh(card_set)

    # Simulate a different user by patching auth
    with patch("app.dependencies.validate_api_key", return_value=TEST_USER_2):
        with patch("app.auth.validate_api_key", return_value=TEST_USER_2):
            resp = await auth_client.patch(f"/api/sets/{card_set.id}", json={
                "name": "Hacked"
            })
    assert resp.status_code == 404


async def test_delete_set(auth_client, db_session):
    from app.models.set import CardSet

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="To Delete",
    )
    db_session.add(card_set)
    await db_session.commit()
    await db_session.refresh(card_set)

    resp = await auth_client.delete(f"/api/sets/{card_set.id}")
    assert resp.status_code == 204

    # Verify it's gone
    resp = await auth_client.get(f"/api/sets/{card_set.id}")
    assert resp.status_code == 404


async def test_delete_non_creator_returns_404(auth_client, db_session):
    from app.models.set import CardSet

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="My Set",
    )
    db_session.add(card_set)
    await db_session.commit()
    await db_session.refresh(card_set)

    with patch("app.dependencies.validate_api_key", return_value=TEST_USER_2):
        with patch("app.auth.validate_api_key", return_value=TEST_USER_2):
            resp = await auth_client.delete(f"/api/sets/{card_set.id}")
    assert resp.status_code == 404


async def test_get_set_progress(auth_client, db_session):
    from app.models.set import CardSet
    from app.models.card import Card

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="Target Set",
        card_targets=["AMROB", "NOCAH", "BAWWAR", "CBCHU"],
    )
    db_session.add(card_set)

    # Give user 2 of 4 targets
    for code in ["AMROB", "BAWWAR"]:
        db_session.add(Card(
            id=str(uuid.uuid4()),
            user_identifier=TEST_USER,
            species_common=f"Bird {code}",
            species_code=code,
        ))
    await db_session.commit()
    await db_session.refresh(card_set)

    resp = await auth_client.get(f"/api/sets/{card_set.id}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["set_id"] == card_set.id
    assert data["set_name"] == "Target Set"
    assert data["total_targets"] == 4
    assert data["collected"] == 2
    assert set(data["missing"]) == {"NOCAH", "CBCHU"}
    assert data["progress_percent"] == 50.0


async def test_get_set_progress_empty(auth_client, db_session):
    from app.models.set import CardSet

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="Empty Progress Set",
        card_targets=["AMROB", "NOCAH"],
    )
    db_session.add(card_set)
    await db_session.commit()
    await db_session.refresh(card_set)

    resp = await auth_client.get(f"/api/sets/{card_set.id}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_targets"] == 2
    assert data["collected"] == 0
    assert data["progress_percent"] == 0.0
    assert set(data["missing"]) == {"AMROB", "NOCAH"}


async def test_get_set_progress_complete(auth_client, db_session):
    from app.models.set import CardSet
    from app.models.card import Card

    card_set = CardSet(
        id=str(uuid.uuid4()),
        creator_identifier=TEST_USER,
        name="Complete Set",
        card_targets=["AMROB", "NOCAH"],
    )
    db_session.add(card_set)

    for code in ["AMROB", "NOCAH"]:
        db_session.add(Card(
            id=str(uuid.uuid4()),
            user_identifier=TEST_USER,
            species_common=f"Bird {code}",
            species_code=code,
        ))
    await db_session.commit()
    await db_session.refresh(card_set)

    resp = await auth_client.get(f"/api/sets/{card_set.id}/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["collected"] == 2
    assert data["missing"] == []
    assert data["progress_percent"] == 100.0


async def test_unauthenticated_returns_401(client):
    resp = await client.get("/api/sets")
    assert resp.status_code == 401

    resp = await client.post("/api/sets", json={"name": "Nope"})
    assert resp.status_code == 401
