import base64
from pathlib import Path

import httpx

from app.config import settings

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

    base_url = settings.ai_base_url or "https://api.openai.com/v1"
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.ai_model,
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

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url}/chat/completions", headers=headers, json=payload
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


CARD_ART_PROMPT_TEMPLATE = """Create a collectible trading card illustration of a {common_name} ({scientific_name}) in a {pose} pose.
The style should be {style}. The illustration should be suitable for a birding card collection.
The image should show the bird prominently with a clean background suitable for card art."""


async def generate_card_art(
    image_path: str | Path,
    species_info: dict,
    style_prompt: str | None = None,
) -> str:
    """Generate stylized card art using an OpenAI-compatible image generation API.

    Returns the relative storage path of the generated image, or empty string on
    failure / when no API key is configured.
    """
    if not settings.ai_api_key:
        return ""

    base_url = (settings.ai_base_url or "https://api.openai.com/v1").rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.ai_api_key}",
        "Content-Type": "application/json",
    }

    common_name = species_info.get("common_name") or species_info.get("common") or "Unknown"
    scientific_name = species_info.get("scientific_name") or species_info.get("scientific") or "Unknown"
    pose = species_info.get("pose_variant") or species_info.get("pose") or "perching"
    rarity = species_info.get("rarity_tier") or "common"

    style = style_prompt or settings.card_style_name or "vibrant watercolor"
    rarity_note = ""
    if rarity in ("rare", "epic", "legendary"):
        rarity_note = f" This is a {rarity} bird — add a subtle magical shimmer effect."

    prompt = CARD_ART_PROMPT_TEMPLATE.format(
        common_name=common_name,
        scientific_name=scientific_name,
        pose=pose,
        style=style,
    ) + rarity_note

    payload = {
        "model": settings.ai_model,
        "prompt": prompt,
        "n": 1,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/images/generations",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        b64_image = data["data"][0]["b64_json"]

        # Save to storage
        from app.storage import get_storage_path
        import uuid as _uuid

        card_art_dir = get_storage_path() / "card_art"
        card_art_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{_uuid.uuid4()}.png"
        filepath = card_art_dir / filename
        filepath.write_bytes(base64.b64decode(b64_image))

        return f"card_art/{filename}"
    except Exception:
        return ""
