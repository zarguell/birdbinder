import pytest
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport

from app.main import app

TEST_API_KEYS = {"test-secret-key-12345678", "another-key"}


@pytest.fixture(autouse=True)
def patch_api_keys():
    """Patch validate_api_key and settings to use known test keys."""
    def fake_validate(key: str) -> str | None:
        if key in TEST_API_KEYS:
            return f"api-key:{key[:8]}"
        return None

    with patch("app.dependencies.validate_api_key", side_effect=fake_validate), \
         patch("app.dependencies.settings", parsed_api_keys=["test-key-123"], cf_access_enabled=False), \
         patch("app.config.settings", parsed_api_keys=["test-key-123"], cf_access_enabled=False):
        yield


async def _client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# --- 1. Health endpoint works without auth ---


@pytest.mark.asyncio
async def test_health_no_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# --- 2. Missing auth returns 401 on protected endpoint ---


@pytest.mark.asyncio
async def test_protected_endpoint_no_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


# --- 3. Valid API key returns 200 ---


@pytest.mark.asyncio
async def test_valid_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/me", headers={"Authorization": "Bearer test-secret-key-12345678"})
    assert resp.status_code == 200
    assert resp.json()["user"] == "api-key:test-sec"


# --- 4. Invalid API key returns 401 ---


@pytest.mark.asyncio
async def test_invalid_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/me", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401


# --- 5. Malformed Authorization header returns 401 ---


@pytest.mark.asyncio
async def test_malformed_auth_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/me", headers={"Authorization": "NotBearer foo"})
    assert resp.status_code == 401


# --- 6. CF_Authorization with valid JWT (email present) returns 200 ---


@pytest.mark.asyncio
async def test_cf_authorization_valid_jwt():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value="user@example.com"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/me", headers={"CF_Authorization": "some.jwt.token"})
    assert resp.status_code == 200
    assert resp.json()["user"] == "user@example.com"


# --- 7. CF_Authorization with JWT missing email returns 401 ---


@pytest.mark.asyncio
async def test_cf_authorization_jwt_no_email():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/me", headers={"CF_Authorization": "some.jwt.token"})
    assert resp.status_code == 401


# --- 8. CF_Authorization with invalid JWT returns 401 ---


@pytest.mark.asyncio
async def test_cf_authorization_invalid_jwt():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/me", headers={"CF_Authorization": "garbage"})
    assert resp.status_code == 401


# --- 9. CF_Authorization takes priority over Bearer key ---


@pytest.mark.asyncio
async def test_cf_authorization_priority_over_bearer():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value="cf-user@example.com"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/me",
                headers={
                    "CF_Authorization": "some.jwt.token",
                    "Authorization": "Bearer test-secret-key-12345678",
                },
            )
    assert resp.status_code == 200
    # CF wins — returns email, not api-key:...
    assert resp.json()["user"] == "cf-user@example.com"


# --- 10. CF_Authorization fails → falls back to valid Bearer key ---


@pytest.mark.asyncio
async def test_fallback_to_bearer_when_cf_fails():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/me",
                headers={
                    "CF_Authorization": "bad.token",
                    "Authorization": "Bearer test-secret-key-12345678",
                },
            )
    assert resp.status_code == 200
    assert resp.json()["user"] == "api-key:test-sec"


# --- 11. Unit tests for auth.py functions directly ---


def test_get_user_from_cf_jwt_valid():
    from app.auth import get_user_from_cf_jwt
    from jose import jwt

    # Create a real JWT with email (signature doesn't matter since we skip verification)
    token = jwt.encode({"email": "test@example.com", "sub": "123"}, "doesntmatter", algorithm="HS256")
    result = get_user_from_cf_jwt(token)
    assert result == "test@example.com"


def test_get_user_from_cf_jwt_no_email():
    from app.auth import get_user_from_cf_jwt
    from jose import jwt

    token = jwt.encode({"sub": "123"}, "doesntmatter", algorithm="HS256")
    result = get_user_from_cf_jwt(token)
    assert result is None


def test_get_user_from_cf_jwt_invalid():
    from app.auth import get_user_from_cf_jwt

    result = get_user_from_cf_jwt("not-a-jwt")
    assert result is None
