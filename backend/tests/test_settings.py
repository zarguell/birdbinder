import pytest
from app.services.app_settings import get_setting, set_setting, get_all_settings


@pytest.mark.asyncio
async def test_upsert_setting(db_session):
    """Set a value and read it back."""
    await set_setting(db_session, "ai_model", "gpt-4o")
    val = await get_setting(db_session, "ai_model")
    assert val == "gpt-4o"


@pytest.mark.asyncio
async def test_get_nonexistent_returns_none(db_session):
    """Reading a key that doesn't exist returns None."""
    val = await get_setting(db_session, "ai_model")
    assert val is None


@pytest.mark.asyncio
async def test_set_non_configurable_key_raises(db_session):
    """Trying to set a key not in CONFIGURABLE_KEYS raises ValueError."""
    with pytest.raises(ValueError, match="not configurable"):
        await set_setting(db_session, "ai_api_key", "secret")


@pytest.mark.asyncio
async def test_update_existing_setting(db_session):
    """Set then update, verify new value."""
    await set_setting(db_session, "card_style_name", "watercolor")
    updated = await set_setting(db_session, "card_style_name", "pixel-art")
    assert updated.value == "pixel-art"
    val = await get_setting(db_session, "card_style_name")
    assert val == "pixel-art"


@pytest.mark.asyncio
async def test_get_all_settings_empty(db_session):
    """get_all_settings returns empty dict when nothing is set."""
    result = await get_all_settings(db_session)
    assert result == {}


@pytest.mark.asyncio
async def test_get_all_settings_with_values(db_session):
    """Set 2 keys, get all returns both."""
    await set_setting(db_session, "ai_model", "gpt-4o")
    await set_setting(db_session, "card_style_name", "watercolor")
    result = await get_all_settings(db_session)
    assert result["ai_model"] == "gpt-4o"
    assert result["card_style_name"] == "watercolor"
