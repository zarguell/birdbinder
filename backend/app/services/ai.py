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


async def generate_card_art(
    image_path: str | Path,
    species_info: dict,
    style_prompt: str | None = None,
) -> str:
    """Generate stylized card art using the AI image generation API.

    Returns the URL or base64 of the generated image.
    For now, returns a placeholder - card art generation will be implemented in Task 9.
    """
    # Will be fully implemented in Task 9
    return ""
