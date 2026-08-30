# BirdBinder — Prompt Strategy

BirdBinder uses three AI prompt pipelines, all configurable at runtime via the Settings page (persists to DB) or environment variables (fallback). Every pipeline targets an OpenAI-compatible API.

## Overview

| Pipeline | Endpoint | Model Setting | Configurable Prompt? |
|----------|----------|--------------|---------------------|
| Species Classification | `POST /chat/completions` (vision) | `ai_model` / `AI_MODEL` | Yes — `birdbinder_id_prompt` |
| Image-to-Image Art | `POST /images/edits` | `ai_image_model` / `AI_IMAGE_MODEL` | Style only — `card_style_name` |
| Text-to-Image Art | `POST /images/generations` | `ai_image_model` / `AI_IMAGE_MODEL` | Style only — `card_style_name` |

## Configuration Priority

All settings follow the same cascade: **DB override → Environment variable → Hardcoded default**.

| Setting | DB Key | Env Var | Default | Affects |
|---------|--------|---------|---------|---------|
| ID system prompt | `birdbinder_id_prompt` | `BIRDBINDER_ID_PROMPT` | `DEFAULT_ID_PROMPT` | Classification |
| Vision model | `ai_model` | `AI_MODEL` | `gpt-4o` | Classification |
| Art style | `card_style_name` | `CARD_STYLE_NAME` | `vibrant watercolor` | Both art pipelines |
| Image model | `ai_image_model` | `AI_IMAGE_MODEL` | _(same as `ai_model`)_ | Both art pipelines |

Settings are managed at `GET /api/settings/ai` and `PATCH /api/settings/ai`. The response includes `source` badges showing whether each value comes from the Database or Environment.

## 1. Species Classification

**Purpose:** Identify the bird species from a user-submitted photo and extract structured metadata.

**Pipeline:**
1. Photo is resized to max 1024px, converted to JPEG (quality 85), base64-encoded
2. Sent as a vision chat completion with the ID prompt as system message
3. Response is parsed as JSON

**Default Prompt (`DEFAULT_ID_PROMPT`):**
```
You are an expert bird identifier. Analyze this bird photograph and identify the species.

You MUST respond ONLY with a valid JSON object. No other text, no explanation.

Return a JSON object with exactly these fields:
- common_name: the common English name (e.g., "American Robin")
- scientific_name: the scientific name (e.g., "Turdus migratorius")
- family: the bird family (e.g., "Thrushes")
- confidence: a float from 0.0 to 1.0 indicating your confidence
- distinguishing_traits: a list of 2-4 visual traits that distinguish this bird
- pose_variant: one of: perching, flying, swimming, foraging, singing, nesting, courtship, other

If you cannot identify the bird, set confidence to 0 and put "Unknown" for names.
```

**User message:** `\"Identify this bird:\"` + base64 image

**Context injection:** After the system prompt is resolved, the sighting's location and date are appended to help the model narrow down species. This is done automatically — no prompt customization needed.

````
Location/date context: This photo was taken in Central Park, New York. Use this to narrow down likely species and subspecies. The photo was taken on May 04, 2026. Consider seasonal plumage, migration status, and expected species for that time of year.
````

Sources (priority order):
1. `location_display_name` — user-provided (via upload prompt or sighting edit)
2. GPS coordinates (`exif_lat`/`exif_lon`) — from EXIF or browser fallback
3. `exif_datetime` — photo timestamp (always injected if available)

If none are available, no context block is appended (same as before).

**Enforced parameters:**
- `response_format: {"type": "json_object"}` — forces structured output
- `max_tokens: 4096` — generous budget for reasoning models (e.g. Kimi K2)

**Output schema:**
```json
{
  "common_name": "American Robin",
  "scientific_name": "Turdus migratorius",
  "family": "Thrushes",
  "confidence": 0.95,
  "distinguishing_traits": ["Orange breast", "Dark head", "White eye ring"],
  "pose_variant": "perching"
}
```

**Reasoning model handling:** Some reasoning models (e.g. Kimi K2) may put analysis in the `reasoning` field and leave `content` empty. When this happens, a follow-up text-only call is made, re-sending the reasoning excerpt and asking the model to produce the structured JSON output.

**Customization:** Replace the entire system prompt via settings. Useful for:
- Adding region-specific context ("Focus on North American species")
- Changing the output schema
- Adding behavior instructions ("Be conservative with identification")

## 2. Image-to-Image Art Generation

**Purpose:** Transform the user's original bird photo into a stylized illustration while preserving the bird's likeness. The app UI handles card frames, borders, and holographic effects — the AI should only generate clean artwork.

**Pipeline:**
1. Original photo is sent as-is (not resized/compressed like classification)
2. Prompt is built from species metadata + art style
3. Sent as multipart form data to `/images/edits`

**Prompt template (`IMAGE_TO_ART_PROMPT`):**
```
Transform this photo of a {common_name} ({scientific_name}) into a {style}
style illustration.
Keep the bird recognizable and prominent. Replace the background with a clean,
uncluttered environment.
Do NOT add any text, borders, frames, or card-like elements.
Only the bird and its environment.
```

**Multipart fields:** `image` (file), `prompt`, `model`, `n=1`, `size=1024x1024`, `response_format=b64_json`

**Style injection:** The `{style}` placeholder is filled from `card_style_name` setting (default: `"vibrant watercolor"`). Examples:
- `"vibrant watercolor"` — loose, colorful watercolor painting
- `"realistic digital art"` — photorealistic digital painting
- `"Studio Ghibli anime"` — Japanese animation style
- `"vintage field guide engraving"` — classic ornithological illustration

**Rarity modifier:** For rare, epic, and legendary birds, the prompt is appended with:
```
This is a {rarity} bird — add a subtle magical shimmer effect.
```

**Fallback:** If the `/images/edits` endpoint fails (model doesn't support it, timeout, etc.), the pipeline automatically falls back to text-to-image generation using the same style and species info.

## 3. Text-to-Image Art Generation

**Purpose:** Generate card art from scratch when no source photo is available, or as a fallback when image-to-image fails. The app UI handles card frames, borders, and holographic effects — the AI should only generate clean artwork.

**Pipeline:**
1. Prompt is built from species metadata (including pose) + art style
2. Sent as JSON to `/images/generations`

**Prompt template (`TEXT_TO_ART_PROMPT`):**
```
Create an illustration of a {common_name} ({scientific_name})
in a {pose} pose.
The style should be {style}. The bird should be prominently centered with
a clean, uncluttered background.
Do NOT add any text, borders, frames, or card-like elements.
Only the bird and its environment.
```

**Key difference from image-to-image:** This template includes `{pose}` (from `pose_variant` — perching, flying, swimming, etc.) since there's no source photo to preserve the pose from. It also explicitly asks the model to "create" rather than "transform."

**Same style and rarity logic** as image-to-image.

**JSON payload:**
```json
{
  "model": "<image_model>",
  "prompt": "<built prompt>",
  "n": 1,
  "size": "1024x1024",
  "response_format": "b64_json"
}
```

## Card Generation Flow

The full pipeline runs as an async job (Huey):

1. **Identify** — `call_vision_model()` → species JSON
2. **Determine rarity** — static taxonomy lookup, optionally enriched by eBird live frequency data
3. **Generate art** — `generate_card_art()`:
   - If source photo exists → try image-to-image first
   - If no photo or image-to-image fails → text-to-image
   - If no AI key configured → skip art (caller uses original photo as card image)
4. **Save card** — Create Card record with art path, rarity, species metadata

## Regeneration

Card art can be regenerated via `POST /api/cards/{id}/regenerate-art` (async job). This re-runs the art generation pipeline with the same species info but optionally accepts:
- `style_override` — different art style for this regeneration
- `prompt_hint` — free-text additional context (e.g., "make the background a sunset sky")

The new art replaces the old `card_art_url` on the Card record.

## API Compatibility Notes

- All three pipelines target standard OpenAI API endpoints (`/chat/completions`, `/images/edits`, `/images/generations`)
- Compatible with any OpenAI-compatible provider (nano-gpt, OpenRouter, local deployments)
- Image responses accepted as either `b64_json` or `url` (auto-downloaded and converted)
- Reasoning models (Kimi K2, etc.) are handled transparently via the follow-up extraction pattern
