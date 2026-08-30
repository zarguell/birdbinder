"""Tests for activity feed service, router (like/unlike/comment), and auto-publish."""

import uuid

from app.models.activity import Activity

TEST_API_KEY = "***"
TEST_USER = f"api-key:{TEST_API_KEY[:8]}"


async def test_get_feed_empty(auth_client):
    resp = await auth_client.get("/api/feed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


async def test_like_activity(auth_client, db_session):
    activity = Activity(
        user_identifier=TEST_USER,
        activity_type="sighting",
        reference_id="s1",
        description="test",
    )
    db_session.add(activity)
    await db_session.commit()

    resp = await auth_client.post(f"/api/feed/{activity.id}/like")
    assert resp.status_code == 201
    assert resp.json()["like_count"] == 1

    # Feed should show liked=True
    resp = await auth_client.get("/api/feed")
    assert resp.json()["items"][0]["current_user_liked"] is True


async def test_unlike_activity(auth_client, db_session):
    activity = Activity(
        user_identifier=TEST_USER,
        activity_type="sighting",
        reference_id="s1",
        description="test",
    )
    db_session.add(activity)
    await db_session.commit()

    await auth_client.post(f"/api/feed/{activity.id}/like")
    resp = await auth_client.delete(f"/api/feed/{activity.id}/like")
    assert resp.status_code == 200
    assert resp.json()["like_count"] == 0


async def test_like_already_liked_returns_409(auth_client, db_session):
    activity = Activity(
        user_identifier=TEST_USER,
        activity_type="sighting",
        reference_id="s1",
        description="test",
    )
    db_session.add(activity)
    await db_session.commit()

    await auth_client.post(f"/api/feed/{activity.id}/like")
    resp = await auth_client.post(f"/api/feed/{activity.id}/like")
    assert resp.status_code == 409


async def test_comment_on_activity(auth_client, db_session):
    activity = Activity(
        user_identifier=TEST_USER,
        activity_type="sighting",
        reference_id="s1",
        description="test",
    )
    db_session.add(activity)
    await db_session.commit()

    resp = await auth_client.post(
        f"/api/feed/{activity.id}/comments",
        json={"content": "Nice bird!"},
    )
    assert resp.status_code == 201
    assert resp.json()["content"] == "Nice bird!"

    # Feed should show the comment
    resp = await auth_client.get("/api/feed")
    assert len(resp.json()["items"][0]["comments"]) == 1


async def test_comment_empty_rejected(auth_client, db_session):
    activity = Activity(
        user_identifier=TEST_USER,
        activity_type="sighting",
        reference_id="s1",
        description="test",
    )
    db_session.add(activity)
    await db_session.commit()

    resp = await auth_client.post(
        f"/api/feed/{activity.id}/comments",
        json={"content": "   "},
    )
    assert resp.status_code == 422


async def test_activity_not_found(auth_client):
    resp = await auth_client.post(f"/api/feed/{str(uuid.uuid4())}/like")
    assert resp.status_code == 404


async def test_unlike_not_liked_returns_404(auth_client, db_session):
    activity = Activity(
        user_identifier=TEST_USER,
        activity_type="sighting",
        reference_id="s1",
        description="test",
    )
    db_session.add(activity)
    await db_session.commit()

    resp = await auth_client.delete(f"/api/feed/{activity.id}/like")
    assert resp.status_code == 404


async def test_activity_service_publish(db_session):
    from app.services.activity import publish_activity

    a = await publish_activity(
        db_session, TEST_USER, "sighting", "ref1", "spotted a Robin"
    )
    assert a.id is not None
    assert a.like_count == 0
    assert a.description == "spotted a Robin"
