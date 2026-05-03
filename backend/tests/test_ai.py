"""Tests for app.services.ai — vision model calls, card art generation, prompt building."""

import base64
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from app.services.ai import (
    DEFAULT_ID_PROMPT,
    call_vision_model,
    generate_card_art,
    _build_art_prompt,
    _build_image_to_art_prompt,
    _extract_b64_from_response,
    _save_b64_image,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_B64 = base64.b64encode(b"fake-image-bytes").decode()
FAKE_JPEG = base64.b64encode(
    bytes([0xFF, 0xD8, 0xFF, 0xE0] + [0] * 100)  # minimal JPEG header
).decode()


@pytest.fixture
def fake_image(tmp_path):
    """Create a real 100x100 JPEG file and return its path."""
    from PIL import Image
    import io
    img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    p = tmp_path / "test.jpg"
    img.save(p, format="JPEG")
    return p


@pytest.fixture
def fake_png(tmp_path):
    """Create a real PNG file."""
    from PIL import Image
    img = Image.new("RGB", (100, 100), color=(200, 100, 100))
    p = tmp_path / "test.png"
    img.save(p, format="PNG")
    return p


@pytest.fixture
def large_image(tmp_path):
    """Create a 3000x2000 JPEG (will be resized before sending)."""
    from PIL import Image
    img = Image.new("RGB", (3000, 2000), color=(50, 50, 50))
    p = tmp_path / "large.jpg"
    img.save(p, format="JPEG", quality=95)
    return p


# ---------------------------------------------------------------------------
# call_vision_model
# ---------------------------------------------------------------------------


@patch("app.services.ai.settings")
async def test_call_vision_model_no_api_key(mock_settings, fake_image):
    """Raises ValueError when AI API key is not configured."""
    mock_settings.ai_api_key = None
    with pytest.raises(ValueError, match="AI API key not configured"):
        await call_vision_model(str(fake_image), "test prompt")


@patch("app.services.ai.settings")
async def test_call_vision_model_successful(mock_settings, fake_image):
    """Happy path: sends request, returns content, logs appropriately."""
    mock_settings.ai_api_key = "test-key-123"
    mock_settings.ai_base_url = "https://fake-ai.example.com/v1"
    mock_settings.ai_model = "gpt-4o"

    fake_response = {
        "choices": [
            {"message": {"content": '{"common_name": "Robin"}'}}
        ]
    }

    mock_http_post = AsyncMock()
    mock_http_post.return_value = MagicMock(
        status_code=200,
        json=lambda: fake_response,
    )
    mock_http_post.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_http_post

    with (
        patch("app.services.ai.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.ai.logger") as mock_logger,
    ):
        result = await call_vision_model(str(fake_image), "Identify this bird:")

    assert result == '{"common_name": "Robin"}'

    # Verify the POST was called with correct URL and auth
    mock_http_post.assert_called_once()
    call_kwargs = mock_http_post.call_args
    assert "fake-ai.example.com/v1/chat/completions" in call_kwargs[0][0]
    assert call_kwargs[1]["headers"]["Authorization"] == "Bearer test-key-123"

    # Verify payload structure
    payload = call_kwargs[1]["json"]
    assert payload["model"] == "gpt-4o"
    assert len(payload["messages"]) == 2  # system + user
    user_content = payload["messages"][1]["content"]
    assert any(item["type"] == "image_url" for item in user_content)

    # Verify logging happened (request + response)
    assert mock_logger.info.call_count >= 2
    log_messages = [str(c) for c in mock_logger.info.call_args_list]
    assert any("AI vision call:" in m for m in log_messages)
    assert any("AI vision response:" in m for m in log_messages)


@patch("app.services.ai.settings")
async def test_call_vision_model_http_error(mock_settings, fake_image):
    """HTTP errors are logged with status code and response body."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None  # use default
    mock_settings.ai_model = "gpt-4o"

    from httpx import HTTPStatusError, Request, Response

    mock_response = Response(429, request=Request("POST", "https://api.openai.com/v1/chat/completions"))
    mock_response._content = b'{"error": "rate limited"}'

    mock_post = AsyncMock(side_effect=HTTPStatusError("429", request=mock_response.request, response=mock_response))

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with (
        patch("app.services.ai.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.ai.logger") as mock_logger,
        pytest.raises(HTTPStatusError),
    ):
        await call_vision_model(str(fake_image), "test")

    # Verify error was logged with status and body excerpt
    error_calls = [str(c) for c in mock_logger.error.call_args_list]
    assert any("429" in m for m in error_calls)
    assert any("rate limited" in m for m in error_calls)


@patch("app.services.ai.settings")
async def test_call_vision_model_network_error(mock_settings, fake_image):
    """Network errors (timeouts, connection refused) are logged."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_model = "gpt-4o"

    import httpx

    mock_post = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with (
        patch("app.services.ai.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.ai.logger") as mock_logger,
        pytest.raises(httpx.ConnectError),
    ):
        await call_vision_model(str(fake_image), "test")

    error_calls = [str(c) for c in mock_logger.error.call_args_list]
    assert any("Connection refused" in m for m in error_calls)


@patch("app.services.ai.settings")
async def test_call_vision_model_empty_content_raises(mock_settings, fake_image):
    """Empty content from AI raises ValueError with response details."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_model = "gpt-4o"

    fake_response = {"choices": [{"message": {"content": ""}}]}
    mock_post = AsyncMock(return_value=MagicMock(
        status_code=200, json=lambda: fake_response,
    ))
    mock_post.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with (
        patch("app.services.ai.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(ValueError, match="empty content"),
    ):
        await call_vision_model(str(fake_image), "test")


@patch("app.services.ai.settings")
async def test_call_vision_model_malformed_response_raises(mock_settings, fake_image):
    """Response with no choices key raises ValueError."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_model = "gpt-4o"

    fake_response = {"unexpected": "structure"}
    mock_post = AsyncMock(return_value=MagicMock(
        status_code=200, json=lambda: fake_response,
    ))
    mock_post.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with (
        patch("app.services.ai.httpx.AsyncClient", return_value=mock_client),
        pytest.raises(ValueError, match="empty content"),
    ):
        await call_vision_model(str(fake_image), "test")


@patch("app.services.ai.settings")
async def test_call_vision_model_png_converts_to_jpeg(mock_settings, fake_png):
    """PNG images are converted to JPEG before sending."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_model = "test-model"

    fake_response = {"choices": [{"message": {"content": "{}"}}]}
    mock_post = AsyncMock(return_value=MagicMock(
        status_code=200, json=lambda: fake_response,
    ))
    mock_post.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("app.services.ai.httpx.AsyncClient", return_value=mock_client):
        await call_vision_model(str(fake_png), "test")

    payload = mock_post.call_args[1]["json"]
    image_url = payload["messages"][1]["content"][1]["image_url"]["url"]
    # All images are converted to JPEG before encoding
    assert "image/jpeg" in image_url


@patch("app.services.ai.settings")
async def test_call_vision_model_resizes_large_image(mock_settings, large_image):
    """Images larger than 1024px are resized before sending."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_model = "test"

    fake_response = {"choices": [{"message": {"content": "{}"}}]}
    mock_post = AsyncMock(return_value=MagicMock(
        status_code=200, json=lambda: fake_response,
    ))
    mock_post.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with (
        patch("app.services.ai.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.ai.logger") as mock_logger,
    ):
        await call_vision_model(str(large_image), "test")

    # Verify resize was logged
    info_msgs = [str(c) for c in mock_logger.info.call_args_list]
    assert any("Resized" in m for m in info_msgs)

    # Verify the payload was sent (request went through)
    mock_post.assert_called_once()


# ---------------------------------------------------------------------------
# _extract_b64_from_response
# ---------------------------------------------------------------------------


def test_extract_b64_from_b64_json_response():
    """Extract from b64_json format (DALL-E style)."""
    data = {"data": [{"b64_json": FAKE_B64}]}
    assert _extract_b64_from_response(data) == FAKE_B64


def test_extract_b64_from_url_response():
    """Fetch image from URL and return as b64."""
    mock_resp = MagicMock()
    mock_resp.content = b"fake-image-bytes"
    mock_resp.raise_for_status = MagicMock()

    data = {"data": [{"url": "https://example.com/img.png"}]}

    with patch("app.services.ai.httpx.get", return_value=mock_resp):
        result = _extract_b64_from_response(data)

    assert result == FAKE_B64


def test_extract_b64_from_response_no_data():
    """Raises ValueError when response has no image data at all."""
    data = {"data": [{"alt_text": "no image here"}]}
    with pytest.raises(ValueError, match="No image data"):
        _extract_b64_from_response(data)


# ---------------------------------------------------------------------------
# _save_b64_image
# ---------------------------------------------------------------------------


def test_save_b64_image(tmp_path):
    """Decodes b64 and saves to card_art storage."""
    with patch("app.storage.get_storage_path", return_value=tmp_path / "storage"):
        result = _save_b64_image(FAKE_B64)

    assert result.startswith("card_art/")
    assert result.endswith(".png")
    saved_path = tmp_path / "storage" / result
    assert saved_path.exists()
    assert saved_path.read_bytes() == b"fake-image-bytes"


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------


def test_build_art_prompt_basic():
    """Text-to-image prompt includes species info and style."""
    info = {
        "common_name": "Blue Jay",
        "scientific_name": "Cyanocitta cristata",
        "pose_variant": "perching",
        "rarity_tier": "common",
    }
    prompt = _build_art_prompt(info, "vibrant watercolor")
    assert "Blue Jay" in prompt
    assert "Cyanocitta cristata" in prompt
    assert "perching" in prompt
    assert "vibrant watercolor" in prompt
    assert "shimmer" not in prompt  # common birds don't get shimmer


def test_build_art_prompt_rare_shimmer():
    """Rare/epic/legendary birds get a shimmer note."""
    info = {
        "common_name": "Whooping Crane",
        "scientific_name": "Grus americana",
        "pose_variant": "flying",
        "rarity_tier": "legendary",
    }
    prompt = _build_art_prompt(info, "anime")
    assert "magical shimmer" in prompt


@pytest.mark.parametrize("rarity", ["rare", "epic", "legendary"])
def test_build_art_prompt_all_rare_tiers_get_shimmer(rarity):
    """All rare+ tiers get shimmer."""
    info = {"common_name": "X", "scientific_name": "Y", "pose_variant": "perching", "rarity_tier": rarity}
    prompt = _build_art_prompt(info, "test")
    assert "shimmer" in prompt


@pytest.mark.parametrize("rarity", ["common", "uncommon"])
def test_build_art_prompt_common_no_shimmer(rarity):
    """Common/uncommon birds don't get shimmer."""
    info = {"common_name": "X", "scientific_name": "Y", "pose_variant": "perching", "rarity_tier": rarity}
    prompt = _build_art_prompt(info, "test")
    assert "shimmer" not in prompt


def test_build_art_prompt_missing_fields_uses_defaults():
    """Missing fields fall back to 'Unknown' / 'perching'."""
    prompt = _build_art_prompt({}, "test-style")
    assert "Unknown" in prompt
    assert "perching" in prompt
    assert "test-style" in prompt


def test_build_image_to_art_prompt_basic():
    """Image-to-image prompt includes species info."""
    info = {
        "common_name": "Cardinal",
        "scientific_name": "Cardinalis cardinalis",
        "rarity_tier": "common",
    }
    prompt = _build_image_to_art_prompt(info, "oil painting")
    assert "Cardinal" in prompt
    assert "Cardinalis cardinalis" in prompt
    assert "oil painting" in prompt


def test_build_image_to_art_prompt_missing_fields():
    """Missing fields get defaults."""
    prompt = _build_image_to_art_prompt({}, "test")
    assert "Unknown" in prompt


# ---------------------------------------------------------------------------
# generate_card_art
# ---------------------------------------------------------------------------


@patch("app.services.ai.settings")
async def test_generate_card_art_no_api_key(mock_settings):
    """Returns empty string when no API key configured."""
    mock_settings.ai_api_key = None
    result = await generate_card_art("/fake/path.jpg", {})
    assert result == ""


@patch("app.services.ai.settings")
async def test_generate_card_art_text_to_image_fallback(mock_settings, fake_image):
    """When image-to-image fails, falls back to text-to-image."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_image_model = "dall-e-3"
    mock_settings.ai_model = "gpt-4o"
    mock_settings.card_style_name = None  # use default

    # image-to-image raises
    mock_i2i = AsyncMock(side_effect=Exception("edits endpoint not supported"))

    # text-to-image succeeds
    mock_t2i = AsyncMock(return_value=FAKE_B64)

    with (
        patch("app.services.ai._generate_image_to_image", mock_i2i),
        patch("app.services.ai._generate_text_to_image", mock_t2i),
        patch("app.services.ai._save_b64_image", return_value="card_art/fake.png"),
        patch("app.services.ai.logger") as mock_logger,
    ):
        result = await generate_card_art(str(fake_image), {
            "common_name": "Test", "scientific_name": "T", "pose_variant": "perching",
        })

    assert result == "card_art/fake.png"
    mock_i2i.assert_called_once()
    mock_t2i.assert_called_once()

    # Verify warning was logged for i2i failure
    warning_msgs = [str(c) for c in mock_logger.warning.call_args_list]
    assert any("image-to-image failed" in m for m in warning_msgs)


@patch("app.services.ai.settings")
async def test_generate_card_art_image_to_image_preferred(mock_settings, fake_image):
    """When both work, image-to-image is tried first (no t2i fallback)."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_image_model = "dall-e-3"
    mock_settings.ai_model = "gpt-4o"
    mock_settings.card_style_name = "watercolor"

    mock_i2i = AsyncMock(return_value=FAKE_B64)
    mock_t2i = AsyncMock()  # should NOT be called

    with (
        patch("app.services.ai._generate_image_to_image", mock_i2i),
        patch("app.services.ai._generate_text_to_image", mock_t2i),
        patch("app.services.ai._save_b64_image", return_value="card_art/i2i.png"),
        patch("app.services.ai.logger"),
    ):
        result = await generate_card_art(str(fake_image), {
            "common_name": "Test", "scientific_name": "T", "pose_variant": "perching",
        })

    assert result == "card_art/i2i.png"
    mock_i2i.assert_called_once()
    mock_t2i.assert_not_called()


@patch("app.services.ai.settings")
async def test_generate_card_art_both_fail_returns_empty(mock_settings, fake_image):
    """When both image-to-image and text-to-image fail, returns empty string (logs error)."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_image_model = "dall-e-3"
    mock_settings.ai_model = "gpt-4o"

    with (
        patch("app.services.ai._generate_image_to_image", side_effect=Exception("i2i fail")),
        patch("app.services.ai._generate_text_to_image", side_effect=Exception("t2i fail")),
        patch("app.services.ai.logger") as mock_logger,
    ):
        result = await generate_card_art(str(fake_image), {
            "common_name": "Test", "scientific_name": "T",
        })

    assert result == ""

    # Verify error was logged (not silently swallowed)
    error_msgs = [str(c) for c in mock_logger.error.call_args_list]
    assert any("Card art generation failed" in m for m in error_msgs)


@patch("app.services.ai.settings")
async def test_generate_card_art_no_source_image_uses_text_to_image(mock_settings):
    """When image_path doesn't exist, skips straight to text-to-image."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_image_model = "dall-e-3"
    mock_settings.ai_model = "gpt-4o"
    mock_settings.card_style_name = None

    mock_t2i = AsyncMock(return_value=FAKE_B64)

    with (
        patch("app.services.ai._generate_text_to_image", mock_t2i),
        patch("app.services.ai._save_b64_image", return_value="card_art/t2i.png"),
        patch("app.services.ai.logger"),
    ):
        result = await generate_card_art("/nonexistent/image.jpg", {
            "common_name": "Robin", "scientific_name": "Turdus migratorius",
            "pose_variant": "perching",
        })

    assert result == "card_art/t2i.png"
    mock_t2i.assert_called_once()


@patch("app.services.ai.settings")
async def test_generate_card_art_uses_ai_image_model_setting(mock_settings, fake_image):
    """Uses ai_image_model when set, falls back to ai_model."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_image_model = "dall-e-3"
    mock_settings.ai_model = "gpt-4o"
    mock_settings.card_style_name = None

    mock_i2i = AsyncMock(return_value=FAKE_B64)

    with (
        patch("app.services.ai._generate_image_to_image", mock_i2i),
        patch("app.services.ai._save_b64_image", return_value="card_art/x.png"),
        patch("app.services.ai.logger"),
    ):
        await generate_card_art(str(fake_image), {
            "common_name": "Test", "scientific_name": "T",
        })

    # i2i positional args: (image_path, prompt, model)
    call_args = mock_i2i.call_args[0]
    assert call_args[2] == "dall-e-3"


@patch("app.services.ai.settings")
async def test_generate_card_art_falls_back_to_ai_model(mock_settings, fake_image):
    """When ai_image_model is not set, uses ai_model."""
    mock_settings.ai_api_key = "test-key"
    mock_settings.ai_base_url = None
    mock_settings.ai_image_model = None  # not set
    mock_settings.ai_model = "gpt-4o"
    mock_settings.card_style_name = None

    mock_i2i = AsyncMock(return_value=FAKE_B64)

    with (
        patch("app.services.ai._generate_image_to_image", mock_i2i),
        patch("app.services.ai._save_b64_image", return_value="card_art/x.png"),
        patch("app.services.ai.logger"),
    ):
        await generate_card_art(str(fake_image), {
            "common_name": "Test", "scientific_name": "T",
        })

    call_args = mock_i2i.call_args[0]
    assert call_args[2] == "gpt-4o"


# ---------------------------------------------------------------------------
# _generate_text_to_image and _generate_image_to_image (unit-level)
# ---------------------------------------------------------------------------


def test_huey_tasks_registered_on_app_import():
    """Importing app should register all @huey.task() decorated functions.

    The huey consumer only loads app.huey_instance — if task modules aren't
    imported in __init__.py, the registry is empty and dequeue fails with
    'X not found in TaskRegistry'.
    """
    import importlib
    import app
    importlib.reload(app)  # ensure fresh import

    from app.huey_instance import huey
    registry = huey._registry

    expected_tasks = {
        "app.services.identifier.identify_task",
        "app.services.card_gen.generate_card_task",
    }
    registered = set(registry._registry.keys())

    missing = expected_tasks - registered
    assert not missing, f"Tasks not registered after app import: {missing}"
    assert expected_tasks.issubset(registered), (
        f"Expected {expected_tasks}, got {registered}"
    )


@patch("app.services.ai.settings")
async def test_generate_text_to_image_happy_path(mock_settings):
    """Sends correct payload to /images/generations."""
    mock_settings.ai_api_key = "key"
    mock_settings.ai_base_url = "https://api.example.com/v2"

    fake_resp = MagicMock()
    fake_resp.json.return_value = {"data": [{"b64_json": FAKE_B64}]}
    fake_resp.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=fake_resp)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("app.services.ai.httpx.AsyncClient", return_value=mock_client):
        from app.services.ai import _generate_text_to_image
        result = await _generate_text_to_image("test prompt", "dall-e-3")

    assert result == FAKE_B64
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "/images/generations" in call_args[0][0]
    payload = call_args[1]["json"]
    assert payload["model"] == "dall-e-3"
    assert payload["n"] == 1
    assert payload["size"] == "1024x1024"
    assert payload["response_format"] == "b64_json"


@patch("app.services.ai.settings")
async def test_generate_image_to_image_happy_path(mock_settings, fake_image):
    """Sends multipart form to /images/edits."""
    mock_settings.ai_api_key = "key"
    mock_settings.ai_base_url = "https://api.example.com/v2"

    fake_resp = MagicMock()
    fake_resp.json.return_value = {"data": [{"b64_json": FAKE_B64}]}
    fake_resp.raise_for_status = MagicMock()

    mock_post = AsyncMock(return_value=fake_resp)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = mock_post

    with patch("app.services.ai.httpx.AsyncClient", return_value=mock_client):
        from app.services.ai import _generate_image_to_image
        result = await _generate_image_to_image(str(fake_image), "test prompt", "dall-e-3")

    assert result == FAKE_B64
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert "/images/edits" in call_args[0][0]
    # Should have files (multipart)
    assert "files" in call_args[1]
