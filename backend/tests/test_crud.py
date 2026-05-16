"""Tests for CRUD utility functions."""

import uuid
import pytest
from sqlalchemy import select
from app.models.sighting import Sighting


async def test_get_owned_or_404_returns_object(db_session, sighting):
    from app.crud import get_owned_or_404
    obj = await get_owned_or_404(db_session, Sighting, sighting.id, sighting.user_identifier)
    assert obj.id == sighting.id
    assert obj.notes == "Test sighting"


async def test_get_owned_or_404_raises_on_wrong_user(db_session, sighting):
    from app.crud import get_owned_or_404
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_owned_or_404(db_session, Sighting, sighting.id, "other-user")
    assert exc.value.status_code == 404


async def test_get_owned_or_404_raises_on_missing_id(db_session):
    from app.crud import get_owned_or_404
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await get_owned_or_404(db_session, Sighting, str(uuid.uuid4()), "any-user")
    assert exc.value.status_code == 404


async def test_paginated_owned_list_empty(db_session):
    from app.crud import paginated_owned_list
    from app.models.sighting import Sighting
    items, total = await paginated_owned_list(
        db_session, Sighting, "no-sightings-user", limit=20, offset=0
    )
    assert items == []
    assert total == 0


async def test_paginated_owned_list_with_data(db_session, sighting):
    from app.crud import paginated_owned_list
    from app.models.sighting import Sighting
    items, total = await paginated_owned_list(
        db_session, Sighting, sighting.user_identifier, limit=20, offset=0
    )
    assert len(items) == 1
    assert total == 1
    assert items[0].id == sighting.id


async def test_paginated_owned_list_respects_limit(db_session, sighting):
    from app.crud import paginated_owned_list
    from app.models.sighting import Sighting
    s2 = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=sighting.user_identifier,
        photo_path=None,
        thumbnail_path=None,
        submitted_at=sighting.submitted_at,
        notes="Second sighting",
        status="pending",
    )
    db_session.add(s2)
    await db_session.commit()

    items, total = await paginated_owned_list(
        db_session, Sighting, sighting.user_identifier, limit=1, offset=0
    )
    assert len(items) == 1
    assert total == 2


async def test_delete_owned_removes_object(db_session, sighting):
    from app.crud import delete_owned
    result = await db_session.execute(
        select(Sighting).where(Sighting.id == sighting.id)
    )
    assert result.scalar_one_or_none() is not None
    await delete_owned(db_session, Sighting, sighting.id, sighting.user_identifier)
    result = await db_session.execute(
        select(Sighting).where(Sighting.id == sighting.id)
    )
    assert result.scalar_one_or_none() is None


async def test_delete_owned_raises_on_wrong_user(db_session, sighting):
    from app.crud import delete_owned
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        await delete_owned(db_session, Sighting, sighting.id, "other-user")
    assert exc.value.status_code == 404
    # Verify sighting still exists
    result = await db_session.execute(
        select(Sighting).where(Sighting.id == sighting.id)
    )
    assert result.scalar_one_or_none() is not None


async def test_paginated_owned_list_with_custom_order(db_session, sighting):
    """Verify custom order_field works."""
    from app.crud import paginated_owned_list
    from app.models.sighting import Sighting
    s2 = Sighting(
        id=str(uuid.uuid4()),
        user_identifier=sighting.user_identifier,
        photo_path=None,
        thumbnail_path=None,
        submitted_at=sighting.submitted_at,
        notes="Second sighting",
        status="pending",
    )
    db_session.add(s2)
    await db_session.commit()
    items, total = await paginated_owned_list(
        db_session, Sighting, sighting.user_identifier, limit=20, offset=0, order_field="submitted_at"
    )
    assert total == 2
    assert len(items) == 2
