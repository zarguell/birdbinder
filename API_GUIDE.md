# BirdBinder API Reference

> A self-hosted birding card-collection app. Backend: Python 3.13, FastAPI, SQLAlchemy async, SQLite, Huey task queue. Auth: Cloudflare Access JWT + Bearer API keys. AI: OpenAI-compatible API.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [Endpoint Reference](#endpoint-reference)
   - [Auth](#auth)
   - [Sightings](#sightings)
   - [Cards](#cards)
   - [Jobs](#jobs)
   - [Binders](#binders)
   - [Sets](#sets)
   - [Trades](#trades)
   - [Species](#species)
   - [Collection](#collection)
   - [Regions](#regions)
   - [Settings](#settings)
   - [Feed / Activity](#feed--activity)
4. [Error Format](#error-format)
5. [Common Patterns](#common-patterns)
6. [Consumption by AI Agents](#consumption-by-ai-agents)

---

## Quick Start

| Item | Value |
|---|---|
| **Base URL** | `http://localhost:8000/api` |
| **Swagger UI** | `http://localhost:8000/api/docs` |
| **ReDoc** | `http://localhost:8000/api/redoc` |
| **OpenAPI Spec** | `http://localhost:8000/api/openapi.json` |
| **Auth (prod)** | `Authorization: Bearer <API_KEY>` header, or Cloudflare Access JWT |
| **Auth (dev)** | No auth needed — all requests treated as `local-user` |

### Test connectivity

```bash
curl -s http://localhost:8000/api/auth/profile
```

In production, add the auth header:

```bash
curl -s -H "Authorization: Bearer bb-api-key-xxxxx" http://localhost:8000/api/auth/profile
```

---

## Authentication

There are two supported auth methods:

1. **Bearer API Key** — set in server config. Send as `Authorization: Bearer <key>`.
2. **Cloudflare Access JWT** — if deployed behind Cloudflare Access, the JWT in the `CF_Authorization` cookie is validated automatically.

In **local dev mode** (no `API_KEYS` env var set), all requests are attributed to a default `local-user`.

---

## Endpoint Reference

> All curl examples assume local dev mode (no auth header). Add `-H "Authorization: Bearer <key>"` for production use.
>
> All examples use `http://localhost:8000` — adjust the host as needed.

---

### Auth

#### Get current user profile

```bash
curl -s http://localhost:8000/api/auth/profile | python3 -m json.tool
```

Response:

```json
{
  "email": "birder@example.com",
  "display_name": "BirdLover42",
  "region": "US-CA",
  "avatar_url": "https://example.com/avatars/birder.jpg"
}
```

#### Update profile

```bash
curl -s -X PATCH http://localhost:8000/api/auth/profile \
  -H "Content-Type: application/json" \
  -d '{
    "display_name": "BirdLover42",
    "avatar_url": "https://example.com/avatars/new-avatar.jpg",
    "region": "US-OR"
  }' | python3 -m json.tool
```

---

### Sightings

#### Create a sighting (with photo upload)

Uses `multipart/form-data`. The `photo` field is the image file. `notes` is an optional text field.

```bash
curl -s -X POST http://localhost:8000/api/sightings \
  -F "photo=@/path/to/american_robin.jpg" \
  -F "notes=Spotted near the creek at Golden Gate Park, singing loudly" | python3 -m json.tool
```

Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "photo_url": "/uploads/sightings/550e8400_e29b_41d4_a716_446655440000.jpg",
  "notes": "Spotted near the creek at Golden Gate Park, singing loudly",
  "species_common": "American Robin",
  "species_scientific": "Turdus migratorius",
  "species_code": "amcro",
  "location": {
    "lat": 37.7694,
    "lng": -122.4862,
    "display_name": "Golden Gate Park"
  },
  "status": "pending",
  "cards": [],
  "created_at": "2026-05-03T15:30:00Z"
}
```

#### List sightings

```bash
# First 20 sightings (default)
curl -s "http://localhost:8000/api/sightings?limit=20&offset=0" | python3 -m json.tool

# Filter by status
curl -s "http://localhost:8000/api/sightings?status=identified"
```

Query params:

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 20 | Max results per page |
| `offset` | int | 0 | Pagination offset |
| `status` | string | — | Filter by status: `pending`, `identified`, `failed` |

#### Get a single sighting

```bash
curl -s http://localhost:8000/api/sightings/550e8400-e29b-41d4-a716-446655440000 | python3 -m json.tool
```

#### Update a sighting

```bash
curl -s -X PATCH http://localhost:8000/api/sightings/550e8400-e29b-41d4-a716-446655440000 \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Updated: confirmed ID after second look at plumage",
    "species_common": "American Robin",
    "species_scientific": "Turdus migratorius",
    "species_code": "amcro",
    "location_override": {
      "lat": 37.7749,
      "lng": -122.4194,
      "display_name": "San Francisco, CA"
    }
  }' | python3 -m json.tool
```

#### Delete a sighting

```bash
curl -s -X DELETE http://localhost:8000/api/sightings/550e8400-e29b-41d4-a716-446655440000
```

---

### Cards

#### Generate a card from a sighting

This triggers the AI pipeline (species ID confirmation, card design, art generation). Returns a `job_id` — poll `/api/jobs/{job_id}` for progress.

```bash
curl -s -X POST http://localhost:8000/api/cards/generate/550e8400-e29b-41d4-a716-446655440000 | python3 -m json.tool
```

Response:

```json
{
  "job_id": "job-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "message": "Card generation started"
}
```

#### Regenerate card art

Re-runs just the image generation for an existing card (e.g., to get a different art style).

```bash
curl -s -X POST http://localhost:8000/api/cards/card-uuid-here/generate-art | python3 -m json.tool
```

Response:

```json
{
  "job_id": "job-b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "status": "pending",
  "message": "Art regeneration started"
}
```

#### List cards

```bash
# All cards
curl -s "http://localhost:8000/api/cards?limit=20&offset=0" | python3 -m json.tool

# Cards in a specific binder
curl -s "http://localhost:8000/api/cards?binder_id=binder-uuid-here"

# Cards by rarity
curl -s "http://localhost:8000/api/cards?rarity=legendary"
```

Query params:

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 20 | Max results per page |
| `offset` | int | 0 | Pagination offset |
| `binder_id` | string | — | Filter by binder |
| `rarity` | string | — | Filter by rarity tier |

#### Get a card detail

```bash
curl -s http://localhost:8000/api/cards/card-uuid-here | python3 -m json.tool
```

Response:

```json
{
  "id": "card-uuid-here",
  "sighting_id": "550e8400-e29b-41d4-a716-446655440000",
  "species_common": "American Robin",
  "species_scientific": "Turdus migratorius",
  "species_code": "amcro",
  "rarity": "common",
  "card_image_url": "/uploads/cards/card-uuid-here.png",
  "notes": "First spring sighting this year",
  "created_at": "2026-05-03T16:00:00Z"
}
```

#### Update a card

```bash
curl -s -X PATCH http://localhost:8000/api/cards/card-uuid-here \
  -H "Content-Type: application/json" \
  -d '{
    "notes": "Beautiful male with vibrant orange breast"
  }' | python3 -m json.tool
```

#### Delete a card

**Requires confirmation** via `confirm=true` query parameter.

```bash
curl -s -X DELETE "http://localhost:8000/api/cards/card-uuid-here?confirm=true"
```

Without `confirm=true`, the request returns an error.

---

### Jobs

#### Poll async job status

Card generation and art regeneration are asynchronous. After getting a `job_id`, poll this endpoint.

```bash
curl -s http://localhost:8000/api/jobs/job-a1b2c3d4-e5f6-7890-abcd-ef1234567890 | python3 -m json.tool
```

Response (in progress):

```json
{
  "job_id": "job-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "running",
  "progress": 60,
  "message": "Generating card art..."
}
```

Response (completed):

```json
{
  "job_id": "job-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "completed",
  "result": {
    "card_id": "card-uuid-here",
    "card_image_url": "/uploads/cards/card-uuid-here.png"
  }
}
```

Response (failed):

```json
{
  "job_id": "job-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "failed",
  "error": "AI image generation timed out"
}
```

**Typical polling pattern:**

```bash
JOB_ID="job-a1b2c3d4-e5f6-7890-abcd-ef1234567890"
while true; do
  STATUS=$(curl -s http://localhost:8000/api/jobs/$JOB_ID | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "Status: $STATUS"
  [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] && break
  sleep 3
done
curl -s http://localhost:8000/api/jobs/$JOB_ID | python3 -m json.tool
```

---

### Binders

Binders organize cards into themed collections.

#### List binders

```bash
curl -s http://localhost:8000/api/binder | python3 -m json.tool
```

#### Create a binder

```bash
curl -s -X POST http://localhost:8000/api/binder \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Backyard Birds",
    "description": "All the birds I have spotted in my backyard garden"
  }' | python3 -m json.tool
```

#### Get binder with cards

```bash
curl -s http://localhost:8000/api/binder/binder-uuid-here | python3 -m json.tool
```

#### Add a card to a binder

```bash
curl -s -X POST http://localhost:8000/api/binder/binder-uuid-here/cards \
  -H "Content-Type: application/json" \
  -d '{
    "card_id": "card-uuid-here"
  }' | python3 -m json.tool
```

#### Remove a card from a binder

```bash
curl -s -X DELETE http://localhost:8000/api/binder/binder-uuid-here/cards/card-uuid-here
```

---

### Sets

Sets are goal-based collections (e.g., "Complete Set of Warblers").

#### List sets

```bash
curl -s http://localhost:8000/api/sets | python3 -m json.tool
```

#### Create a set

```bash
curl -s -X POST http://localhost:8000/api/sets \
  -H "Content-Type: application/json" \
  -d '{
    "name": "California Warblers",
    "description": "All warbler species found in California",
    "card_ids": ["card-uuid-1", "card-uuid-2", "card-uuid-3"]
  }' | python3 -m json.tool
```

#### Get set detail

```bash
curl -s http://localhost:8000/api/sets/set-uuid-here | python3 -m json.tool
```

#### Update a set

```bash
curl -s -X PATCH http://localhost:8000/api/sets/set-uuid-here \
  -H "Content-Type: application/json" \
  -d '{
    "name": "California Warblers (2026)",
    "description": "Updated warbler collection",
    "card_ids": ["card-uuid-1", "card-uuid-2", "card-uuid-3", "card-uuid-4"]
  }' | python3 -m json.tool
```

#### Get missing cards for a set

Returns the species needed to complete the set that the user hasn't discovered yet.

```bash
curl -s http://localhost:8000/api/sets/set-uuid-here/missing | python3 -m json.tool
```

Response:

```json
{
  "set_id": "set-uuid-here",
  "set_name": "California Warblers",
  "total_species": 35,
  "discovered": 22,
  "missing": [
    {
      "species_code": "palwar",
      "species_common": "Palm Warbler",
      "species_scientific": "Setophaga palmarum"
    },
    {
      "species_code": "bkpwar",
      "species_common": "Blackpoll Warbler",
      "species_scientific": "Setophaga striata"
    }
  ]
}
```

---

### Trades

Trade cards with other users on the same BirdBinder instance.

#### Create a trade offer

```bash
curl -s -X POST http://localhost:8000/api/trades \
  -H "Content-Type: application/json" \
  -d '{
    "offered_card_ids": ["card-uuid-1", "card-uuid-2"],
    "requested_card_ids": ["card-uuid-3"],
    "to_user": "birder-friend@example.com"
  }' | python3 -m json.tool
```

#### List trades

```bash
curl -s http://localhost:8000/api/trades | python3 -m json.tool
```

#### Accept a trade

```bash
curl -s -X POST http://localhost:8000/api/trades/trade-uuid-here/accept | python3 -m json.tool
```

#### Decline a trade

```bash
curl -s -X POST http://localhost:8000/api/trades/trade-uuid-here/decline | python3 -m json.tool
```

---

### Species

#### Search species

```bash
# Free-text search
curl -s "http://localhost:8000/api/species/search?q=robin" | python3 -m json.tool

# Search within a family
curl -s "http://localhost:8000/api/species/search?q=warbler&family=Parulidae" | python3 -m json.tool
```

Query params:

| Param | Type | Description |
|---|---|---|
| `q` | string | Search term (common name, scientific name, or code) |
| `family` | string | Filter by bird family (e.g., `Parulidae`, `Turdidae`) |

Response:

```json
{
  "results": [
    {
      "code": "amcro",
      "common_name": "American Robin",
      "scientific_name": "Turdus migratorius",
      "family": "Turdidae",
      "order": "Passeriformes"
    }
  ]
}
```

#### Get species detail

```bash
curl -s http://localhost:8000/api/species/amcro | python3 -m json.tool
```

#### List all families

```bash
curl -s http://localhost:8000/api/species/families | python3 -m json.tool
```

---

### Collection

#### Get collection progress

```bash
# Flat response
curl -s http://localhost:8000/api/collection/progress | python3 -m json.tool

# Grouped by family
curl -s "http://localhost:8000/api/collection/progress?family_group=true" | python3 -m json.tool
```

Response (`family_group=true`):

```json
{
  "total_species": 1100,
  "discovered": 87,
  "missing_count": 1013,
  "families": [
    {
      "family": "Turdidae",
      "common_name": "Thrushes",
      "total": 20,
      "discovered": 5
    },
    {
      "family": "Parulidae",
      "common_name": "New World Warblers",
      "total": 55,
      "discovered": 12
    }
  ]
}
```

#### Refresh eBird rarity data

Pulls live rarity data from eBird. Requires the `EBIRD_API_KEY` environment variable on the server.

```bash
curl -s -X POST http://localhost:8000/api/collection/refresh-ebird | python3 -m json.tool
```

Response:

```json
{
  "status": "refreshed",
  "species_updated": 87,
  "timestamp": "2026-05-03T16:30:00Z"
}
```

---

### Regions

#### List available regions

```bash
curl -s http://localhost:8000/api/regions | python3 -m json.tool
```

Response:

```json
{
  "regions": [
    {
      "id": "US-CA",
      "name": "California, US",
      "type": "subnational1"
    },
    {
      "id": "US-OR",
      "name": "Oregon, US",
      "type": "subnational1"
    }
  ]
}
```

#### List species for a region

```bash
curl -s http://localhost:8000/api/regions/US-CA/species | python3 -m json.tool
```

---

### Settings

#### Get AI configuration

Shows current settings, indicating which values come from database overrides vs. environment defaults.

```bash
curl -s http://localhost:8000/api/settings/ai | python3 -m json.tool
```

Response:

```json
{
  "ai_model": "gpt-4o",
  "ai_image_model": "dall-e-3",
  "card_style_name": "watercolor",
  "birdbinder_id_prompt": "Identify this bird species from the photo...",
  "source": {
    "ai_model": "database_override",
    "ai_image_model": "env_default",
    "card_style_name": "database_override",
    "birdbinder_id_prompt": "env_default"
  }
}
```

#### Update AI settings

```bash
curl -s -X PATCH http://localhost:8000/api/settings/ai \
  -H "Content-Type: application/json" \
  -d '{
    "ai_model": "gpt-4o",
    "ai_image_model": "dall-e-3",
    "card_style_name": "field-sketch",
    "birdbinder_id_prompt": "You are an expert ornithologist. Identify the bird species in this photo and provide its eBird species code."
  }' | python3 -m json.tool
```

---

### Feed / Activity

#### Get activity feed

```bash
curl -s "http://localhost:8000/api/feed?limit=20&offset=0" | python3 -m json.tool
```

Response:

```json
{
  "items": [
    {
      "id": "feed-uuid-1",
      "type": "card_generated",
      "user": "birder@example.com",
      "display_name": "BirdLover42",
      "message": "generated a card for American Robin (Common)",
      "card_image_url": "/uploads/cards/card-uuid-here.png",
      "likes_count": 5,
      "comments_count": 2,
      "liked_by_me": false,
      "created_at": "2026-05-03T16:00:00Z"
    }
  ]
}
```

#### Like an activity

```bash
curl -s -X POST http://localhost:8000/api/feed/feed-uuid-1/like | python3 -m json.tool
```

#### Unlike an activity

```bash
curl -s -X DELETE http://localhost:8000/api/feed/feed-uuid-1/like | python3 -m json.tool
```

#### Add a comment

```bash
curl -s -X POST http://localhost:8000/api/feed/feed-uuid-1/comments \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Great shot! I spotted one of these at my feeder last week too."
  }' | python3 -m json.tool
```

---

## Error Format

All errors follow a consistent format:

```json
{
  "detail": "Description of what went wrong"
}
```

Common HTTP status codes:

| Status | Meaning | Example |
|---|---|---|
| `400` | Bad request | Missing required fields, invalid parameters |
| `401` | Unauthorized | Missing or invalid auth credentials |
| `403` | Forbidden | Authenticated but not authorized for this resource |
| `404` | Not found | Resource (sighting, card, binder, etc.) does not exist |
| `409` | Conflict | Duplicate resource or state conflict |
| `422` | Validation error | Request body failed schema validation |
| `500` | Server error | Internal error — check server logs |

---

## Common Patterns

### Async Job Pattern (Card Generation)

Card generation and art regeneration are async. The flow is:

```
1. POST /api/cards/generate/{sighting_id}
   → returns {"job_id": "..."}

2. Poll GET /api/jobs/{job_id}
   → status cycles: pending → running → completed/failed

3. When completed, result contains the card_id
```

**Bash script example:**

```bash
#!/bin/bash
SIGHTING_ID="550e8400-e29b-41d4-a716-446655440000"
BASE="http://localhost:8000/api"

# 1. Start card generation
JOB_ID=$(curl -s -X POST $BASE/cards/generate/$SIGHTING_ID | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "Started job: $JOB_ID"

# 2. Poll until done
while true; do
  RESP=$(curl -s $BASE/jobs/$JOB_ID)
  STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "[$(date +%H:%M:%S)] Status: $STATUS"
  if [ "$STATUS" = "completed" ]; then
    CARD_ID=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['card_id'])")
    echo "Card created: $CARD_ID"
    break
  elif [ "$STATUS" = "failed" ]; then
    ERROR=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('error','Unknown error'))")
    echo "Job failed: $ERROR"
    exit 1
  fi
  sleep 3
done
```

### Pagination

All list endpoints accept:

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 20 | Max items per page |
| `offset` | int | 0 | Number of items to skip |

```bash
# Page 1
curl -s "http://localhost:8000/api/sightings?limit=10&offset=0"

# Page 2
curl -s "http://localhost:8000/api/sightings?limit=10&offset=10"

# Page 3
curl -s "http://localhost:8000/api/sightings?limit=10&offset=20"
```

### File Uploads

Sightings use `multipart/form-data` with a `photo` file field and optional form fields.

```bash
curl -s -X POST http://localhost:8000/api/sightings \
  -F "photo=@/path/to/bird_photo.jpg" \
  -F "notes=Morning walk sighting"
```

Supported image formats depend on the server configuration (typically JPEG, PNG, WebP).

---

## Consumption by AI Agents

The OpenAPI specification is the single source of truth for all endpoints, schemas, and authentication:

```bash
# Fetch the full OpenAPI 3.x spec
curl -s http://localhost:8000/api/openapi.json | python3 -m json.tool > openapi-spec.json
```

**Use the spec for:**

- **Tool discovery** — parse `paths` to enumerate all available endpoints
- **Schema validation** — use `components.schemas` to understand request/response shapes
- **Auth detection** — check `securitySchemes` for required authentication methods
- **Auto-client generation** — feed the spec into OpenAPI client generators for any language

**Python example — load and explore:**

```python
import json
import urllib.request

spec = json.loads(urllib.request.urlopen("http://localhost:8000/api/openapi.json").read())

# List all endpoints
for path, methods in spec["paths"].items():
    for method in methods:
        if method in ("get", "post", "patch", "delete"):
            summary = methods[method].get("summary", "")
            print(f"{method.upper():7s} {path:45s} — {summary}")
```

**Interactive docs:**

- **Swagger UI**: http://localhost:8000/api/docs — try endpoints in-browser, with auth
- **ReDoc**: http://localhost:8000/api/redoc — clean, readable documentation

---

*Last updated: 2026-05-03*
