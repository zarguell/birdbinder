from __future__ import annotations

import pytest
from app.models.user import User


async def test_user_region_field(db_session):
    """User model should accept a region value."""
    user = User(email="test@example.com", region="us")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.region == "us"
