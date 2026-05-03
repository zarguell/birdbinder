"""Tests for /api/settings/ai endpoints."""

import pytest


async def test_get_ai_settings_returns_all_keys(auth_client):
    resp = await auth_client.get("/api/settings/ai")
    assert resp.status_code == 200
    data = resp.json()
    assert "ai_model" in data
    assert "ai_image_model" in data
    assert "card_style_name" in data
    assert "birdbinder_id_prompt" in data
    # Each key has value, label, description, type, source
    for key in data:
        assert "value" in data[key]
        assert "label" in data[key]
        assert "source" in data[key]


async def test_update_ai_settings(auth_client):
    resp = await auth_client.patch("/api/settings/ai", json={"ai_model": "test-model-v2"})
    assert resp.status_code == 200
    assert resp.json()["ai_model"] == "test-model-v2"
    # Verify it's persisted
    resp = await auth_client.get("/api/settings/ai")
    assert resp.json()["ai_model"]["value"] == "test-model-v2"
    assert resp.json()["ai_model"]["source"] == "database"


async def test_update_multiple_settings(auth_client):
    resp = await auth_client.patch("/api/settings/ai", json={
        "ai_model": "new-model",
        "card_style_name": "pixel art",
    })
    assert resp.status_code == 200


async def test_cannot_set_protected_keys(auth_client):
    resp = await auth_client.patch("/api/settings/ai", json={"ai_api_key": "stolen"})
    assert resp.status_code == 422


async def test_cannot_set_nonexistent_keys(auth_client):
    resp = await auth_client.patch("/api/settings/ai", json={"bogus_key": "value"})
    assert resp.status_code == 422


async def test_value_must_be_string(auth_client):
    resp = await auth_client.patch("/api/settings/ai", json={"ai_model": 42})
    assert resp.status_code == 422
