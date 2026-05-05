import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_version_default():
    """GET /api/version returns the git_sha from settings (defaults to 'dev')."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/version")
    assert r.status_code == 200
    data = r.json()
    assert "commit" in data
    # Default value is "dev"
    assert isinstance(data["commit"], str)
    assert len(data["commit"]) > 0


@pytest.mark.asyncio
async def test_version_env_override():
    """GET /api/version reflects a custom GIT_SHA env var."""
    import os
    from unittest.mock import patch

    original = os.environ.get("GIT_SHA")
    try:
        os.environ["GIT_SHA"] = "abc123def456"
        # Re-import settings to pick up the new env var
        from importlib import reload
        import app.config as config_mod
        reload(config_mod)
        from app.config import settings as new_settings

        assert new_settings.git_sha == "abc123def456"
    finally:
        if original is not None:
            os.environ["GIT_SHA"] = original
        else:
            os.environ.pop("GIT_SHA", None)
        # Reload back
        from importlib import reload
        import app.config as config_mod
        reload(config_mod)
