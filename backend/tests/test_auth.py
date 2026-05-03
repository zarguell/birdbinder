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
        resp = await ac.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Authentication required"


# --- 3. Valid API key returns 200 ---


@pytest.mark.asyncio
async def test_valid_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/auth/me", headers={"Authorization": "Bearer test-secret-key-12345678"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_identifier"] == "api-key:test-sec"
    assert data["auth_source"] == "api-key"


# --- 4. Invalid API key returns 401 ---


@pytest.mark.asyncio
async def test_invalid_api_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/auth/me", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401


# --- 5. Malformed Authorization header returns 401 ---


@pytest.mark.asyncio
async def test_malformed_auth_header():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/auth/me", headers={"Authorization": "NotBearer foo"})
    assert resp.status_code == 401


# --- 6. Cf-Access-Jwt-Assertion with valid JWT returns 200 ---


@pytest.mark.asyncio
async def test_cf_jwt_assertion_valid():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value="user@example.com"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/auth/me", headers={"Cf-Access-Jwt-Assertion": "some.jwt.token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_identifier"] == "user@example.com"
    assert data["auth_source"] == "cf-jwt-header"
    assert data["has_cf_jwt_header"] is True


# --- 7. Cf-Access-Jwt-Assertion with JWT missing email returns 401 ---


@pytest.mark.asyncio
async def test_cf_jwt_assertion_no_email():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/auth/me", headers={"Cf-Access-Jwt-Assertion": "some.jwt.token"})
    assert resp.status_code == 401


# --- 8. CF_Authorization (cookie fallback) still works ---


@pytest.mark.asyncio
async def test_cf_authorization_cookie_fallback():
    """CF_Authorization sent as a header still works (matches header path)."""
    with patch("app.dependencies.get_user_from_cf_jwt", return_value="user@example.com"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/auth/me", headers={"CF_Authorization": "some.jwt.token"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_identifier"] == "user@example.com"
    assert data["auth_source"] == "cf-header"
    assert data["has_cf_raw_header"] is True


# --- 9. Cf-Access-Jwt-Assertion takes priority over CF_Authorization ---


@pytest.mark.asyncio
async def test_cf_jwt_assertion_priority_over_cookie():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value="jwt-user@example.com"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/auth/me",
                headers={
                    "Cf-Access-Jwt-Assertion": "jwt.token",
                    "CF_Authorization": "cookie.token",
                },
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_identifier"] == "jwt-user@example.com"
    assert data["auth_source"] == "cf-jwt-header"


# --- 10. CF JWT takes priority over Bearer key ---


@pytest.mark.asyncio
async def test_cf_jwt_priority_over_bearer():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value="cf-user@example.com"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/auth/me",
                headers={
                    "Cf-Access-Jwt-Assertion": "some.jwt.token",
                    "Authorization": "Bearer test-secret-key-12345678",
                },
            )
    assert resp.status_code == 200
    data = resp.json()
    # CF wins — returns email, not api-key:...
    assert data["user_identifier"] == "cf-user@example.com"
    assert data["auth_source"] == "cf-jwt-header"


# --- 11. CF JWT fails → falls back to valid Bearer key ---


@pytest.mark.asyncio
async def test_fallback_to_bearer_when_cf_fails():
    with patch("app.dependencies.get_user_from_cf_jwt", return_value=None):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get(
                "/api/auth/me",
                headers={
                    "Cf-Access-Jwt-Assertion": "bad.token",
                    "Authorization": "Bearer test-secret-key-12345678",
                },
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_identifier"] == "api-key:test-sec"
    assert data["auth_source"] == "api-key"


# --- 12. /auth/settings returns non-sensitive config ---


@pytest.mark.asyncio
async def test_auth_settings_no_secrets():
    with patch("app.routers.auth.settings", cf_access_enabled=False, parsed_api_keys=["test-key-123"], ai_base_url="https://custom.api/v1", ai_model="test-model", ai_api_key="secret-key", ai_image_model=None, card_style_name="watercolor", storage_path="./storage", database_url="sqlite+aiosqlite:///./data/db.sqlite", cf_team_domain=""):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/auth/settings", headers={"Authorization": "Bearer test-secret-key-12345678"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["auth_mode"] == "api_key"
    assert data["ai_base_url"] == "https://custom.api/v1"
    assert data["ai_model"] == "test-model"
    assert data["ai_enabled"] is True


# --- 13. Unit tests for auth.py functions directly ---


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
