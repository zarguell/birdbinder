import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.activity import Activity
from app.models.like import Like
from app.models.comment import Comment


@pytest.mark.asyncio
async def test_activity_model_creation(db_session):
    """Create an Activity, commit, and verify all fields."""
    activity = Activity(
        user_identifier="api-key:12345678",
        activity_type="sighting",
        reference_id="00000000-0000-0000-0000-000000000001",
        description="Spotted a red cardinal!",
        like_count=0,
        comment_count=0,
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    assert activity.id is not None
    assert len(activity.id) == 36
    assert activity.user_identifier == "api-key:12345678"
    assert activity.activity_type == "sighting"
    assert activity.reference_id == "00000000-0000-0000-0000-000000000001"
    assert activity.description == "Spotted a red cardinal!"
    assert activity.like_count == 0
    assert activity.comment_count == 0
    assert activity.created_at is not None


@pytest.mark.asyncio
async def test_like_model_creation_and_count(db_session):
    """Create an Activity, add a Like, verify like relationship via eager load."""
    activity = Activity(
        user_identifier="api-key:12345678",
        activity_type="sighting",
        reference_id="00000000-0000-0000-0000-000000000001",
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    like = Like(
        activity_id=activity.id,
        user_identifier="api-key:aaaaaaaa",
    )
    db_session.add(like)
    await db_session.commit()
    await db_session.refresh(like)

    assert like.id is not None
    assert like.activity_id == activity.id
    assert like.user_identifier == "api-key:aaaaaaaa"
    assert like.created_at is not None

    # Verify relationship via eager load (async-safe)
    result = await db_session.execute(
        select(Activity).options(selectinload(Activity.likes)).where(Activity.id == activity.id)
    )
    loaded = result.scalar_one()
    assert len(loaded.likes) == 1


@pytest.mark.asyncio
async def test_comment_model_creation_and_count(db_session):
    """Create an Activity, add a Comment, verify comment relationship via eager load."""
    activity = Activity(
        user_identifier="api-key:12345678",
        activity_type="card",
        reference_id="00000000-0000-0000-0000-000000000002",
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    comment = Comment(
        activity_id=activity.id,
        user_identifier="api-key:bbbbbbbb",
        content="Nice card!",
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)

    assert comment.id is not None
    assert comment.activity_id == activity.id
    assert comment.user_identifier == "api-key:bbbbbbbb"
    assert comment.content == "Nice card!"
    assert comment.created_at is not None

    # Verify relationship via eager load (async-safe)
    result = await db_session.execute(
        select(Activity).options(selectinload(Activity.comments)).where(Activity.id == activity.id)
    )
    loaded = result.scalar_one()
    assert len(loaded.comments) == 1


@pytest.mark.asyncio
async def test_like_unique_constraint(db_session):
    """Adding a duplicate Like (same activity + user) should raise IntegrityError."""
    activity = Activity(
        user_identifier="api-key:12345678",
        activity_type="set_completion",
        reference_id="00000000-0000-0000-0000-000000000003",
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    like1 = Like(
        activity_id=activity.id,
        user_identifier="api-key:cccccccc",
    )
    db_session.add(like1)
    await db_session.commit()

    like2 = Like(
        activity_id=activity.id,
        user_identifier="api-key:cccccccc",
    )
    db_session.add(like2)
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.mark.asyncio
async def test_comment_creation(db_session):
    """Create Activity + Comment, verify all comment fields."""
    activity = Activity(
        user_identifier="api-key:12345678",
        activity_type="sighting",
        reference_id="00000000-0000-0000-0000-000000000004",
        description="Morning walk sighting",
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)

    comment = Comment(
        activity_id=activity.id,
        user_identifier="api-key:dddddddd",
        content="Beautiful photo! What camera did you use?",
    )
    db_session.add(comment)
    await db_session.commit()
    await db_session.refresh(comment)

    assert comment.id is not None
    assert comment.activity_id == activity.id
    assert comment.user_identifier == "api-key:dddddddd"
    assert comment.content == "Beautiful photo! What camera did you use?"
    assert comment.created_at is not None

    # Verify relationship via eager load (async-safe)
    result = await db_session.execute(
        select(Activity).options(selectinload(Activity.comments)).where(Activity.id == activity.id)
    )
    loaded = result.scalar_one()
    assert loaded.comments[0].activity.id == activity.id
