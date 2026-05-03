import base64
import logging
import time
import uuid as _uuid
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_ID_PROMPT = """\
You are an expert bird identifier. Analyze this bird photograph and identify the species.

Return a JSON object with these fields:
- common_name: the common English name (e.g., "American Robin")
- scientific_name: the scientific name (e.g., "Turdus migratorius")
- family: the bird family (e.g., "Thrushes")
- confidence: a float from 0.0 to 1.0 indicating your confidence
- distinguishing_traits: a list of 2-4 visual traits that distinguish this bird
- pose_variant: one of: perching, flying, swimming, foraging, singing, nesting, courtship, other

If you cannot identify the bird, set confidence to 0 and put "Unknown" for names."""


async def call_vision_model(image_path: str | Path, prompt: str) -> str:
    """Send image to OpenAI-compatible vision API and return the text response."""
    if not settings.ai_api_key:
        raise ValueError("AI API key not configured")

    # Read and base64-encode the image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    # Determine MIME type
    ext = str(image_path).lower().split(".")[-1]
    mime_map = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
    }
    mime = mime_map.get(ext, "image/jpeg")

    base_url = (settings.ai_base_url or "https://api.openai.com/v1").rstrip("/")
    model = settings.ai_model
    image_size_kb = len(image_data) * 3 / 4 / 1024

    logger.info(
        "AI vision call: model=%s base_url=%s image=%s (%.0f KB, %s)",
        model, base_url, image_path, image_size_kb, mime,
    )

    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Identify this bird:"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_data}"},
                    },
                ],
            },
        ],
        "max_tokens": 500,
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{base_url}/chat/completions", headers=headers, json=payload
            )
            elapsed = time.monotonic() - t0
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            logger.info(
                "AI vision response: status=%d elapsed=%.1fs content_len=%d model=%s",
                resp.status_code, elapsed, len(content), model,
            )
            return content
    except httpx.HTTPStatusError as e:
        elapsed = time.monotonic() - t0
        logger.error(
            "AI vision HTTP error: status=%d elapsed=%.1fs body=%s",
            e.response.status_code, elapsed, e.response.text[:500],
        )
        raise
    except Exception as e:
        elapsed = time.monotonic() - t0
        logger.error("AI vision error after %.1fs: %s", elapsed, e)
        raise


# -- Card art generation -----------------------------------------------------

TEXT_TO_ART_PROMPT = """Create a collectible trading card illustration of a {common_name} ({scientific_name}) in a {pose} pose.
The style should be {style}. The illustration should be suitable for a birding card collection.
The image should show the bird prominently with a clean background suitable for card art."""

IMAGE_TO_ART_PROMPT = """Transform this photo of a {common_name} ({scientific_name}) into a collectible trading card illustration in {style} style.
Keep the bird recognizable and prominent. Replace the background with a clean card-art background suitable for a birding card collection."""


def _build_art_prompt(species_info: dict, style: str) -> str:
    """Build the prompt string, with rarity shimmer for rare+ birds."""
    common_name = species_info.get("common_name") or species_info.get("common") or "Unknown"
    scientific_name = species_info.get("scientific_name") or species_info.get("scientific") or "Unknown"
    pose = species_info.get("pose_variant") or species_info.get("pose") or "perching"
    rarity = species_info.get("rarity_tier") or "common"

    template_vars = {
        "common_name": common_name,
        "scientific_name": scientific_name,
        "pose": pose,
        "style": style,
    }

    rarity_note = ""
    if rarity in ("rare", "epic", "legendary"):
        rarity_note = f" This is a {rarity} bird — add a subtle magical shimmer effect."

    return TEXT_TO_ART_PROMPT.format(**template_vars) + rarity_note


def _build_image_to_art_prompt(species_info: dict, style: str) -> str:
    """Build the prompt for image-to-image editing."""
    common_name = species_info.get("common_name") or species_info.get("common") or "Unknown"
    scientific_name = species_info.get("scientific_name") or species_info.get("scientific") or "Unknown"
    rarity = species_info.get("rarity_tier") or "common"

    template_vars = {
        "common_name": common_name,
        "scientific_name": scientific_name,
        "style": style,
    }

    rarity_note = ""
    if rarity in ("rare", "epic", "legendary"):
        rarity_note = f" This is a {rarity} bird — add a subtle magical shimmer effect."

    return IMAGE_TO_ART_PROMPT.format(**template_vars) + rarity_note


def _save_b64_image(b64_data: str) -> str:
    """Decode base64 image data and save to card_art storage. Returns relative path."""
    from app.storage import get_storage_path

    card_art_dir = get_storage_path() / "card_art"
    card_art_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_uuid.uuid4()}.png"
    filepath = card_art_dir / filename
    filepath.write_bytes(base64.b64decode(b64_data))
    return f"card_art/{filename}"


def _extract_b64_from_response(data: dict) -> str:
    """Extract base64 image from an OpenAI-compatible image API response."""
    item = data["data"][0]
    if "b64_json" in item:
        return item["b64_json"]
    # Some APIs return a URL — fetch and convert
    if "url" in item:
        resp = httpx.get(item["url"], timeout=60)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode()
    raise ValueError("No image data in response")


async def _generate_image_to_image(image_path: str | Path, prompt: str, model: str) -> str:
    """Image-to-image: transform the user's photo into styled card art via /images/edits.

    Uses multipart form upload (OpenAI-compatible).
    Returns base64-encoded image data.
    """
    base_url = (settings.ai_base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
    }

    with open(image_path, "rb") as img_file:
        files = {
            "image": ("photo.jpg", img_file, "image/jpeg"),
            "prompt": (None, prompt),
            "model": (None, model),
            "n": (None, "1"),
            "size": (None, "1024x1024"),
            "response_format": (None, "b64_json"),
        }
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/images/edits",
                headers=headers,
                files=files,
            )
            resp.raise_for_status()
            return _extract_b64_from_response(resp.json())


async def _generate_text_to_image(prompt: str, model: str) -> str:
    """Text-to-image: generate card art from scratch via /images/generations.

    Returns base64-encoded image data.
    """
    base_url = (settings.ai_base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{base_url}/images/generations",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return _extract_b64_from_response(resp.json())


async def generate_card_art(
    image_path: str | Path,
    species_info: dict,
    style_prompt: str | None = None,
) -> str:
    """Generate stylized card art for a sighting.

    Strategy (in order of preference):
    1. If AI_IMAGE_MODEL is set and image_path exists → image-to-image edit (preserves likeness)
    2. If AI_IMAGE_MODEL is set (no photo) → text-to-image generation
    3. Fallback → return empty string (caller uses original photo)

    Returns the relative storage path of the generated image, or empty string.
    """
    if not settings.ai_api_key:
        return ""

    image_model = settings.ai_image_model or settings.ai_model
    style = style_prompt or settings.card_style_name or "vibrant watercolor"

    try:
        has_source_image = image_path and Path(image_path).is_file()

        if has_source_image:
            # Try image-to-image first (better likeness preservation)
            prompt = _build_image_to_art_prompt(species_info, style)
            try:
                logger.info("Card art: trying image-to-image with model=%s", image_model)
                b64 = await _generate_image_to_image(image_path, prompt, image_model)
                logger.info("Card art: image-to-image succeeded")
                return _save_b64_image(b64)
            except Exception as e:
                logger.warning("Card art: image-to-image failed (%s), falling back to text-to-image", e)

        # Text-to-image (no photo or image-to-image failed)
        prompt = _build_art_prompt(species_info, style)
        logger.info("Card art: text-to-image with model=%s", image_model)
        b64 = await _generate_text_to_image(prompt, image_model)
        logger.info("Card art: text-to-image succeeded")
        return _save_b64_image(b64)
    except Exception as e:
        logger.error("Card art generation failed: %s", e, exc_info=True)
        return ""
