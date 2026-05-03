# BirdBinder v1 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task. Use OpenCode CLI (`opencode run`) for implementation subagents. Model: `nano-gpt/minimax/minimax-m2.7` for most tasks, `nano-gpt/deepseek/deepseek-v4-flash` for simple boilerplate.

**Goal:** Build a self-hosted, API-first PWA that turns bird sightings into collectible digital cards.

**Architecture:** Monorepo with `backend/` (FastAPI) and `frontend/` (SvelteKit static adapter). SQLite via SQLAlchemy async + Alembic. Huey for background jobs (AI identification, card art generation). Local disk for image storage. Production runs in Docker (multi-stage build). Dev uses uv venvs for Python, npm for frontend.

**Tech Stack:**
- Backend: Python 3.11+, FastAPI, SQLAlchemy (async), Alembic, aiosqlite, huey, Pillow, openai, python-jose (JWT), Pydantic v2
- Frontend: SvelteKit (static adapter), Tailwind CSS v4
- Data: eBird taxonomy JSON (from audio-birdle)
- Tooling: uv for Python venvs, npm/pnpm for frontend, pytest for backend tests, vitest for frontend tests

**Environment:** No Docker available. System Python managed. `uv` venv works.

---

## Milestone 1: Core Loop

### Task 1: Project scaffolding

**Objective:** Set up monorepo structure, Python backend venv, dependencies, and git config.

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/config.py`
- Create: `.gitignore`
- Create: `backend/.env.example`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

**Step 1: Create project structure**

```bash
cd ~/repos/birdbinder
mkdir -p backend/app backend/tests backend/migrations frontend
```

**Step 2: Create backend pyproject.toml**

```toml
[project]
name = "birdbinder"
version = "0.1.0"
description = "Bird sighting collector and card generator"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "sqlalchemy[asyncio]>=2.0",
    "aiosqlite>=0.21",
    "alembic>=1.14",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "python-multipart>=0.0.20",
    "pillow>=11.0",
    "openai>=1.60",
    "python-jose[cryptography]>=3.3",
    "huey>=2.5",
    "httpx>=0.28",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "pytest-cov>=6.0",
    "httpx>=0.28",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

**Step 3: Create backend venv and install deps**

```bash
cd ~/repos/birdbinder/backend
uv venv
uv pip install -e ".[dev]"
```

**Step 4: Create .gitignore**

```
__pycache__/
*.py[cod]
.env
.venv/
node_modules/
.svelte-kit/
build/
dist/
*.db
storage/
backend/app/static/
.DS_Store
```

**Step 5: Create backend/app/config.py**

```python
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_url: str = "http://localhost:8000"
    api_keys: str = ""  # comma-separated
    cf_access_enabled: bool = False
    cf_team_domain: str = ""
    ai_base_url: Optional[str] = None
    ai_model: str = "gpt-4o"
    ai_api_key: Optional[str] = None
    birdbinder_id_prompt: Optional[str] = None
    card_style_name: str = "default"
    database_url: str = "sqlite+aiosqlite:///./data/birdbinder.db"
    storage_path: str = "./storage"
    ebird_api_key: Optional[str] = None

    @property
    def parsed_api_keys(self) -> list[str]:
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]

    model_config = {"env_file": ".env", "env_prefix": ""}


settings = Settings()
```

**Step 6: Create minimal FastAPI app**

```python
# backend/app/main.py
from fastapi import FastAPI
from app.config import settings

app = FastAPI(title="BirdBinder", version="0.1.0")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

**Step 7: Verify app starts**

```bash
cd ~/repos/birdbinder/backend
source .venv/bin/activate
python -c "from app.main import app; print('OK')"
```

**Step 8: Create backend/app/__init__.py and backend/tests/__init__.py** (empty)

**Step 9: Create backend/tests/conftest.py**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
```

**Step 10: Write first test**

```python
# backend/tests/test_health.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

**Step 11: Run test to verify pass**

```bash
cd ~/repos/birdbinder/backend
source .venv/bin/activate
pytest tests/test_health.py -v
```

**Step 12: Create backend/.env.example**

```
APP_URL=http://localhost:8000
API_KEYS=
CF_ACCESS_ENABLED=false
CF_TEAM_DOMAIN=
AI_BASE_URL=
AI_MODEL=gpt-4o
AI_API_KEY=
BIRDBINDER_ID_PROMPT=
CARD_STYLE_NAME=default
DATABASE_URL=sqlite+aiosqlite:///./data/birdbinder.db
STORAGE_PATH=./storage
EBIRD_API_KEY=
```

**Step 13: Commit**

```bash
git add -A
git commit -m "chore: project scaffolding with FastAPI backend"
```

---

### Task 2: Database models and Alembic setup

**Objective:** Define all SQLAlchemy models and set up Alembic migrations.

**Files:**
- Create: `backend/app/db.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/sighting.py`
- Create: `backend/app/models/card.py`
- Create: `backend/app/models/set.py`
- Create: `backend/app/models/trade.py`
- Create: `backend/app/models/species.py`
- Create: `backend/app/models/job.py`
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Modify: `backend/app/main.py` (add DB engine)
- Test: `backend/tests/test_models.py`

**Step 1: Create backend/app/db.py** — async engine, session factory, Base class.

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
import os

os.makedirs(os.path.dirname(settings.database_url.replace("sqlite+aiosqlite:///", "./")), exist_ok=True)

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        yield session
```

**Step 2: Create PoseVariant enum and all models.** Each model uses UUID primary keys, timestamps, and proper relationships.

Key models (full code in task context for subagent):
- **Sighting:** id (UUID), user_identifier, photo_path, thumbnail_path, submitted_at, exif_datetime, exif_lat, exif_lon, exif_camera_model, location_display_name, notes, manual_species_override, status (enum: pending/identified/failed/cancelled)
- **Card:** id (UUID), sighting_id (FK), user_identifier, species_common, species_scientific, species_code, family, pose_variant (enum), rarity_tier, set_ids (JSON), card_number, card_art_url, id_method, id_confidence, duplicate_count (default 1), tradeable (default True), generated_at
- **Set:** id (UUID), creator_identifier, name, description, region, season, release_date, expiry_date, rules (JSON), card_targets (JSON — list of {species_code, pose_variant})
- **Trade:** id (UUID), offered_by, offered_to, offered_card_ids (JSON), requested_card_ids (JSON), status (enum: pending/accepted/declined/cancelled), created_at, resolved_at
- **Job:** id (UUID), type (enum: identify/generate_card), sighting_id, status (enum: pending/running/completed/failed), result (JSON nullable), error (nullable), created_at, completed_at

**Step 3: Set up Alembic**

```bash
cd ~/repos/birdbinder/backend
source .venv/bin/activate
alembic init migrations
```

Configure `alembic.ini` and `migrations/env.py` to use async engine.

**Step 4: Write tests** — create tables in-memory, insert and query each model.

**Step 5: Generate initial migration**

```bash
alembic revision --autogenerate -m "initial schema"
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: database models and Alembic migrations"
```

---

### Task 3: Auth middleware

**Objective:** Implement dual auth — CF_Authorization JWT decode + Bearer API key.

**Files:**
- Create: `backend/app/auth.py`
- Create: `backend/app/dependencies.py`
- Modify: `backend/app/main.py` (add auth middleware)
- Test: `backend/tests/test_auth.py`

**Step 1: Write failing test for API key auth**

```python
# backend/tests/test_auth.py
@pytest.mark.asyncio
async def test_api_key_auth(client, app_settings):
    # Set API keys in settings
    ...

@pytest.mark.asyncio
async def test_missing_auth_returns_401(client):
    r = await client.get("/api/sightings")
    assert r.status_code == 401

@pytest.mark.asyncio
async def test_invalid_api_key_returns_401(client, app_settings):
    r = await client.get("/api/sightings", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401
```

**Step 2: Implement auth.py** — decode CF_Authorization JWT (extract email), validate Bearer API key. Return user_identifier string.

```python
# CF JWT decode (no verification needed — Cloudflare already verified)
from jose import jwt, JWTError

def get_user_from_cf_jwt(token: str) -> str | None:
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        return payload.get("email")
    except JWTError:
        return None
```

**Step 3: Implement dependencies.py** — `get_current_user` FastAPI dependency that checks both auth paths and raises 401 if neither works.

**Step 4: Add middleware to FastAPI app** — health endpoint exempt, all `/api/*` require auth.

**Step 5: Run tests, verify pass**

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: dual auth (CF JWT + API key)"
```

---

### Task 4: Image storage and EXIF extraction

**Objective:** Handle file uploads, generate thumbnails, extract EXIF metadata.

**Files:**
- Create: `backend/app/storage.py`
- Create: `backend/app/image.py`
- Test: `backend/tests/test_image.py`

**Step 1: Write failing tests**

```python
# backend/tests/test_image.py
def test_extract_exif_from_jpeg(tmp_path):
    # Create a test JPEG with EXIF data using Pillow
    ...

def test_generate_thumbnail(tmp_path):
    # Test thumbnail generation creates smaller image
    ...

def test_extract_exif_missing_gracefully(tmp_path):
    # PNG without EXIF should return empty dict, not crash
    ...
```

**Step 2: Implement storage.py** — save uploaded file to disk under `STORAGE_PATH/sightings/{uuid}.{ext}`, return path and URL.

**Step 3: Implement image.py** — `extract_exif(path)` returns dict with datetime, lat, lon, camera_model. `generate_thumbnail(src_path, thumb_path)` creates 300x300 thumbnail. Both use Pillow.

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: image storage, thumbnail generation, EXIF extraction"
```

---

### Task 5: Sighting CRUD endpoints

**Objective:** Create sighting submission and listing endpoints.

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/sightings.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/sighting.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_sightings.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_create_sighting_with_image(client, auth_headers, tmp_path):
    # Upload multipart form with image
    ...

@pytest.mark.asyncio
async def test_list_sightings_paginated(client, auth_headers):
    ...

@pytest.mark.asyncio
async def test_get_sighting_by_id(client, auth_headers):
    ...

@pytest.mark.asyncio
async def test_delete_sighting(client, auth_headers):
    ...
```

**Step 2: Implement schemas** — `SightingCreate`, `SightingRead`, `SightingList` (paginated).

**Step 3: Implement router** — `POST /api/sightings` (multipart upload + EXIF + thumbnail), `GET /api/sightings` (paginated, filterable), `GET /api/sightings/{id}`, `DELETE /api/sightings/{id}`.

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: sighting CRUD endpoints"
```

---

### Task 6: Bundle eBird taxonomy data + species search

**Objective:** Load eBird taxonomy JSON, provide species search API.

**Files:**
- Create: `backend/app/data/` directory
- Copy: eBird taxonomy data from `~/repos/audio-birdle/scripts/data/ebird-taxonomy.json`
- Create: `backend/app/services/species.py`
- Create: `backend/app/schemas/species.py`
- Create: `backend/app/routers/species.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_species.py`

**Step 1: Copy and filter eBird data**

Keep only `category == "species"` entries. Fields: sciName, comName, speciesCode, familyComName, familySciName, order, familyCode. Save as `backend/app/data/birds.json`.

**Step 2: Write failing tests**

```python
@pytest.mark.asyncio
async def test_search_species_by_common_name(client, auth_headers):
    r = await client.get("/api/species/search?q=robin")
    assert r.status_code == 200
    assert len(r.json()["items"]) > 0
    assert any(b["com_name"] == "American Robin" for b in r.json()["items"])

@pytest.mark.asyncio
async def test_search_species_empty(client, auth_headers):
    r = await client.get("/api/species/search?q=zzzzz")
    assert r.json()["items"] == []

@pytest.mark.asyncio
async def test_get_species_by_code(client, auth_headers):
    r = await client.get("/api/species/amerob")
    assert r.json()["com_name"] == "American Robin"
```

**Step 3: Implement species service** — load JSON at startup, provide search (case-insensitive substring on common/scientific name, paginated) and get-by-code.

**Step 4: Implement router** — `GET /api/species/search?q=...&limit=20&offset=0`, `GET /api/species/{code}`.

**Step 5: Run tests, verify pass**

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: bundled eBird taxonomy and species search API"
```

---

### Task 7: AI bird identification (async job)

**Objective:** Send sighting image to AI model, get identification back via async job queue.

**Files:**
- Create: `backend/app/services/ai.py`
- Create: `backend/app/services/identifier.py`
- Create: `backend/app/routers/jobs.py`
- Create: `backend/app/schemas/job.py`
- Create: `backend/app/schemas/identification.py`
- Modify: `backend/app/main.py` (include router, start huey)
- Test: `backend/tests/test_identification.py`

**Step 1: Write failing tests** (mock the OpenAI call)

```python
@pytest.mark.asyncio
async def test_identify_sighting_creates_job(client, auth_headers, db_session):
    # POST to identify, get job_id back
    ...

@pytest.mark.asyncio
async def test_get_job_status(client, auth_headers):
    # Poll job status
    ...

def test_parse_ai_response():
    # Test parsing structured AI output into identification result
    ...

def test_pose_variant_from_allowed_list():
    # Ensure pose is constrained to taxonomy
    ...
```

**Step 2: Implement default identification prompt** — instruct model to return JSON with: common_name, scientific_name, family, confidence (0-1), distinguishing_traits, pose_variant (from allowed list).

**Step 3: Implement ai.py** — `call_vision_model(image_path, prompt)` sends image to OpenAI-compatible API. `generate_card_art(image_path, species_info, style_prompt)` generates stylized card art.

**Step 4: Implement identifier.py** — `start_identification(sighting_id, db)` creates a huey job, returns job_id. Huey task calls AI, updates sighting with results, changes status to `identified`.

**Step 5: Implement jobs router** — `GET /api/jobs/{job_id}` returns status and result.

**Step 6: Wire up huey** — start huey consumer as background thread in FastAPI startup event (for dev). Separate `huey_consumer.py` script for production.

**Step 7: Run tests, verify pass**

**Step 8: Commit**

```bash
git add -A
git commit -m "feat: AI bird identification with async job queue"
```

---

### Task 8: Manual identification override

**Objective:** Allow manual species/pose/confidence editing on sightings.

**Files:**
- Modify: `backend/app/routers/sightings.py`
- Modify: `backend/app/schemas/sighting.py`
- Test: `backend/tests/test_manual_id.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_manual_species_override(client, auth_headers, sighting):
    r = await client.patch(f"/api/sightings/{sighting.id}", json={
        "manual_species_override": "American Robin",
        "species_code": "amerob",
        "pose_variant": "perched_branch",
        "status": "identified"
    })
    assert r.status_code == 200
    assert r.json()["species_code"] == "amerob"

@pytest.mark.asyncio
async def test_invalid_pose_rejected(client, auth_headers, sighting):
    r = await client.patch(f"/api/sightings/{sighting.id}", json={
        "pose_variant": "breakdancing"
    })
    assert r.status_code == 422
```

**Step 2: Implement PATCH endpoint** on sightings router for manual overrides.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: manual identification override"
```

---

### Task 9: Card generation (AI art + fallback)

**Objective:** Generate cards with AI art from sightings, fallback to photo.

**Files:**
- Create: `backend/app/services/card_gen.py`
- Create: `backend/app/routers/cards.py`
- Create: `backend/app/schemas/card.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_cards.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_generate_card_creates_job(client, auth_headers, identified_sighting):
    r = await client.post(f"/api/cards/generate/{identified_sighting.id}")
    assert r.status_code == 202
    assert "job_id" in r.json()

@pytest.mark.asyncio
async def test_generate_card_fallback_no_ai_key(client, auth_headers, identified_sighting, app_settings_no_ai):
    # Without AI key, card should use original photo
    ...

@pytest.mark.asyncio
async def test_list_cards(client, auth_headers):
    ...

@pytest.mark.asyncio
async def test_get_card_detail(client, auth_headers, card):
    ...
```

**Step 2: Implement card_gen.py** — `start_card_generation(sighting_id)`. If AI_API_KEY set: call vision model for card art. If not: use original photo as card art. Create Card record in DB.

**Step 3: Implement card art prompt** — style-agnostic prompt that generates a "collectible trading card illustration" of the bird species in the observed pose, matching the global `CARD_STYLE_NAME`.

**Step 4: Implement cards router** — `POST /api/cards/generate/{sighting_id}`, `GET /api/cards`, `GET /api/cards/{id}`, `PATCH /api/cards/{id}`, `DELETE /api/cards/{id}`.

**Step 5: Run tests, verify pass**

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: card generation with AI art and photo fallback"
```

---

### Task 10: Rarity tiers from taxonomy data

**Objective:** Assign rarity tiers to birds based on taxonomy/frequency data.

**Files:**
- Create: `backend/app/services/rarity.py`
- Modify: `backend/app/services/card_gen.py` (assign rarity during card generation)
- Test: `backend/tests/test_rarity.py`

**Step 1: Write failing tests**

```python
def test_rarity_assignment():
    # Test that common birds get lower rarity, rare birds get higher
    ...

def test_rarity_tiers():
    # Test all expected tiers exist: common, uncommon, rare, epic, legendary
    ...
```

**Step 2: Implement rarity.py** — Load taxonomy data, assign rarity tiers based on observation frequency or taxonomic order grouping. Tiers: common, uncommon, rare, epic, legendary.

**Step 3: Integrate into card generation** — set rarity_tier on Card when generating.

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: rarity tier assignment from taxonomy data"
```

---

### Task 11: Binder API

**Objective:** Implement binder listing with grouping, filtering, and card detail.

**Files:**
- Create: `backend/app/routers/binder.py`
- Create: `backend/app/schemas/binder.py`
- Modify: `backend/app/main.py` (include router)
- Test: `backend/tests/test_binder.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_get_binder(client, auth_headers, cards):
    r = await client.get("/api/binder")
    assert r.status_code == 200
    assert len(r.json()["cards"]) > 0

@pytest.mark.asyncio
async def test_filter_binder_by_rarity(client, auth_headers):
    ...

@pytest.mark.asyncio
async def test_group_binder_by_set(client, auth_headers):
    ...

@pytest.mark.asyncio
async def test_binder_duplicate_counts(client, auth_headers, duplicate_cards):
    ...
```

**Step 2: Implement binder router** — `GET /api/binder?group_by=set|species|family&filter_rarity=...&filter_pose=...&filter_date_from=...&filter_date_to=...&limit=50&offset=0`. Returns cards with duplicate counts, missing-card placeholders for incomplete sets.

**Step 3: Run tests, verify pass**

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: binder API with grouping, filtering, and duplicates"
```

---

## Milestone 2: Sets

### Task 12: Set CRUD and auto-matching

**Objective:** Create/manage sets, auto-match cards, track completion.

**Files:**
- Create: `backend/app/routers/sets.py`
- Create: `backend/app/schemas/set.py`
- Create: `backend/app/services/set_matching.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_sets.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_create_set(client, auth_headers):
    ...

@pytest.mark.asyncio
async def test_get_set_completion(client, auth_headers, set_with_cards):
    ...

@pytest.mark.asyncio
async def test_get_set_missing_cards(client, auth_headers, incomplete_set):
    ...

@pytest.mark.asyncio
async def test_any_user_can_create_set(client, auth_headers):
    ...
```

**Step 2: Implement set_matching.py** — given a set's card_targets (species_code + optional pose_variant), find matching cards, calculate completion %, return missing cards.

**Step 3: Implement sets router** — `POST /api/sets`, `GET /api/sets`, `GET /api/sets/{id}`, `PATCH /api/sets/{id}`, `DELETE /api/sets/{id}`, `GET /api/sets/{id}/missing`.

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: set CRUD with auto-matching and completion tracking"
```

---

## Milestone 3: Trading

### Task 13: Trading endpoints

**Objective:** Create/accept/decline trades, handle duplicates.

**Files:**
- Create: `backend/app/routers/trades.py`
- Create: `backend/app/schemas/trade.py`
- Create: `backend/app/services/trading.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_trades.py`

**Step 1: Write failing tests**

```python
@pytest.mark.asyncio
async def test_create_trade(client, auth_headers, duplicate_card):
    ...

@pytest.mark.asyncio
async def test_accept_trade(client, auth_headers, pending_trade):
    ...

@pytest.mark.asyncio
async def test_decline_trade(client, auth_headers, pending_trade):
    ...

@pytest.mark.asyncio
async def test_cannot_trade_non_duplicate(client, auth_headers, single_card):
    ...
```

**Step 2: Implement trading.py** — validate trade (offered cards must have duplicate_count > 1 or be marked tradeable), execute trade (transfer duplicate counts, update tradeable status).

**Step 3: Implement trades router** — `POST /api/trades`, `GET /api/trades`, `POST /api/trades/{id}/accept`, `POST /api/trades/{id}/decline`.

**Step 4: Run tests, verify pass**

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: trading endpoints with duplicate handling"
```

---

## Milestone 4: Frontend

### Task 14: SvelteKit frontend scaffolding + PWA

**Objective:** Set up SvelteKit project with static adapter, Tailwind CSS, and PWA manifest.

**Files:**
- Create: `frontend/` (via `npm create svelte@latest`)
- Create: `frontend/src/app.html`
- Create: `frontend/src/routes/+layout.svelte`
- Create: `frontend/static/manifest.json`
- Create: `frontend/static/icon-192.png` (placeholder)
- Create: `frontend/static/icon-512.png` (placeholder)
- Create: `frontend/svelte.config.js`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tailwind.config.js` (or v4 CSS)

**Step 1: Scaffold SvelteKit**

```bash
cd ~/repos/birdbinder
npx sv create frontend --template minimal --types ts
cd frontend
npm install
```

**Step 2: Configure static adapter** (output to `../backend/app/static`)

**Step 3: Add Tailwind CSS v4**

```bash
cd frontend
npm install -D tailwindcss @tailwindcss/vite
```

**Step 4: Create PWA manifest** with `standalone` display mode, app icons, theme color.

**Step 5: Verify build**

```bash
cd frontend
npm run build
# Check output in backend/app/static/
```

**Step 6: Update FastAPI to serve static files**

Add static file mounting in `backend/app/main.py` for the built frontend.

**Step 7: Commit**

```bash
git add -A
git commit -m "feat: SvelteKit frontend scaffolding with PWA and Tailwind"
```

---

### Task 15: Frontend upload page

**Objective:** Mobile-friendly photo upload with camera capture and library selection.

**Files:**
- Create: `frontend/src/routes/upload/+page.svelte`
- Create: `frontend/src/lib/api.ts` (API client)
- Create: `frontend/src/lib/auth.ts`

**Step 1: Implement API client** — fetch wrapper with auth headers, typed responses.

**Step 2: Implement upload page** — camera button, file picker, preview, submit, EXIF display, progress indication.

**Step 3: Verify manually or with component test**

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: upload page with camera and file picker"
```

---

### Task 16: Frontend sighting detail + identification

**Objective:** Show sighting detail, trigger AI identification, allow manual override.

**Files:**
- Create: `frontend/src/routes/sightings/[id]/+page.svelte`
- Create: `frontend/src/lib/components/SpeciesAutocomplete.svelte`

**Step 1: Implement sighting detail page** — photo, EXIF data, identification status, manual override form with species autocomplete.

**Step 2: Implement SpeciesAutocomplete** — typeahead from `/api/species/search`.

**Step 3: Implement "Generate Card" button** — triggers card generation job, polls for completion.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: sighting detail with AI ID and manual override"
```

---

### Task 17: Frontend binder view

**Objective:** Card grid with grouping, filtering, and card detail modal.

**Files:**
- Create: `frontend/src/routes/binder/+page.svelte`
- Create: `frontend/src/lib/components/CardGrid.svelte`
- Create: `frontend/src/lib/components/CardModal.svelte`
- Create: `frontend/src/lib/components/CardComponent.svelte`

**Step 1: Implement binder page** — group selector (set/species/family), filter controls (rarity, pose, date), card grid.

**Step 2: Implement CardComponent** — renders card front with art, species name, rarity badge, pose label.

**Step 3: Implement CardModal** — card detail with front/back flip, metadata, EXIF info.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: binder view with card grid and detail modal"
```

---

### Task 18: Frontend sets and trading pages

**Objective:** Set management, completion tracking, and trade flow.

**Files:**
- Create: `frontend/src/routes/sets/+page.svelte`
- Create: `frontend/src/routes/sets/[id]/+page.svelte`
- Create: `frontend/src/routes/trades/+page.svelte`
- Create: `frontend/src/lib/components/CompletionBar.svelte`
- Create: `frontend/src/lib/components/MissingCards.svelte`

**Step 1: Implement sets list page** — all sets with completion bars, create new set button.

**Step 2: Implement set detail page** — card grid for set, missing cards, completion progress.

**Step 3: Implement trades page** — pending trades, accept/decline, create trade offer.

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: sets management and trading pages"
```

---

### Task 19: Final integration, OpenAPI, and polish

**Objective:** Serve frontend from FastAPI, verify OpenAPI docs, final test sweep.

**Files:**
- Modify: `backend/app/main.py` (static file serving, CORS, SPA fallback)
- Create: `backend/app/routers/docs.py` (if needed)
- Modify: `frontend/src/routes/+layout.svelte` (nav, meta tags)

**Step 1: Serve built frontend** — FastAPI mounts static files, SPA fallback to index.html for client-side routing.

**Step 2: Verify OpenAPI** — navigate to `/docs` and `/openapi.json`, ensure all endpoints documented.

**Step 3: Add navigation** — app shell with nav to Upload, Binder, Sets, Trades.

**Step 4: Run full backend test suite**

```bash
cd ~/repos/birdbinder/backend
pytest tests/ -v --cov=app
```

**Step 5: Build frontend, verify**

```bash
cd ~/repos/birdbinder/frontend
npm run build
npm run test  # if vitest configured
```

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: final integration, OpenAPI docs, app shell navigation"
```

---

## Deployment

### Task 20: Dockerfile and docker-compose

**Objective:** Multi-stage Dockerfile for production, docker-compose for local dev/deploy.

**Reference:** `zarguell/sprout` Dockerfile pattern — multi-stage build, non-root user, entrypoint for volume-safe dir creation, healthcheck.

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `entrypoint.sh`
- Create: `.dockerignore`

**Step 1: Create Dockerfile** — multi-stage build:

```
Stage 1: node:22-slim — build SvelteKit frontend
Stage 2: python:3.13-slim — production runtime
```

Key details:
- `RUN adduser --system --group appuser`
- Copy built frontend from stage 1 into `/app/static/`
- Install backend deps from `backend/pyproject.toml` via pip
- Copy backend code, alembic config, bird taxonomy data
- Create `/app/data/db` and `/app/storage` dirs owned by appuser
- Non-root: `USER appuser`
- Expose 8000
- Entrypoint creates runtime dirs (volume-safe), runs alembic upgrade, starts uvicorn + huey worker
- CMD: runs both uvicorn and huey consumer (supervisor or shell script)

**Step 2: Create entrypoint.sh**

```sh
#!/bin/sh
set -e

# Ensure data directories exist (volume mounts overlay image dirs)
mkdir -p /app/data/db /app/storage

# Run migrations
alembic upgrade head

# Start uvicorn + huey worker
exec "$@"
```

**Step 3: Create docker-compose.yml**

```yaml
services:
  birdbinder:
    image: zarguell/birdbinder:latest
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - birdbinder-data:/app/data
      - birdbinder-storage:/app/storage
    env_file:
      - .env
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"]
      interval: 30s
      timeout: 5s
      retries: 3

volumes:
  birdbinder-data:
  birdbinder-storage:
```

**Step 4: Create .dockerignore**

```
.git
node_modules
.venv
__pycache__
*.pyc
.env
backend/data/
backend/storage/
.svelte-kit
*.db
```

**Step 5: Commit**

```bash
git add -A
git commit -m "feat: Dockerfile, docker-compose, and entrypoint"
```

---

### Task 21: CI/CD pipelines

**Objective:** GitHub Actions for tests + Docker build/push. Follows sprout pattern: reusable workflow_call for Docker.

**Reference:** `zarguell/sprout` — `.github/workflows/test.yml` (triggers, lint+test job, calls docker workflow) and `.github/workflows/docker.yml` (reusable, multi-platform, GHA cache, semver tags).

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/docker.yml`

**Step 1: Create .github/workflows/docker.yml** — reusable callable workflow:

- Triggers: `workflow_call` with `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets
- QEMU + Buildx setup
- DockerHub login
- Metadata: `zarguell/birdbinder` image, tags: `latest` on main, `dev` on dev branch, semver on tags, SHA
- Build and push: `linux/amd64,linux/arm64`, GHA cache

Pin all third-party actions to SHA (not tags), matching sprout convention.

**Step 2: Create .github/workflows/test.yml**:

- Triggers: push to main/dev, tags `v*`, PRs to main/dev
- `lint-and-test` job: checkout, setup Python, install deps (pip), compile check, run pytest
- `frontend-test` job: checkout, setup Node, install deps, run `npm run build` (and test if configured)
- `docker` job: needs lint-and-test, calls `.github/workflows/docker.yml`, secrets inherit

**Step 3: Verify workflow YAML is valid**

```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/docker.yml'))"
python -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"
```

**Step 4: Commit**

```bash
git add -A
git commit -m "ci: test and Docker build pipelines"
```

---

## PRD Coverage Mapping

| # | Criterion | Task(s) |
|---|-----------|---------|
| 1 | CF_Authorization JWT → user email | Task 3 |
| 2 | Bearer API key auth | Task 3 |
| 3 | API keys from env var | Task 3 |
| 4 | Both paths equal trust | Task 3 |
| 5 | POST /api/sightings image upload | Task 5 |
| 6 | Sighting stores all fields | Tasks 2, 5 |
| 7 | Thumbnail generation | Task 4 |
| 8 | EXIF extraction | Task 4 |
| 9 | Missing EXIF OK | Task 4 |
| 10 | Sighting status tracking | Task 2 |
| 11 | AI ID via OpenAI-compatible API | Task 7 |
| 12 | AI returns all fields | Task 7 |
| 13 | Pose from fixed taxonomy | Task 7 |
| 14 | Configurable ID prompt | Task 7 |
| 15 | Async job for ID | Task 7 |
| 16 | Manual species/pose/confidence | Task 8 |
| 17 | Species search endpoint | Task 6 |
| 18 | Manual as first-class path | Task 8 |
| 19 | POST /api/cards/generate/{id} | Task 9 |
| 20 | Card gen async job | Task 9 |
| 21 | Card stores all fields | Task 2 |
| 22 | AI card art generation | Task 9 |
| 23 | Fallback to original photo | Task 9 |
| 24 | Card front layout | Task 17 |
| 25 | Card back/detail | Task 17 |
| 26 | Bundled taxonomy data | Task 6 |
| 27 | Rarity tiers from taxonomy | Task 10 |
| 28 | Optional eBird API enrichment | Task 6 |
| 29 | GET /api/binder | Task 11 |
| 30 | Group by set/species/family | Task 11 |
| 31 | Filter by rarity/pose/date/dupes | Task 11 |
| 32 | Missing-card placeholders | Tasks 11, 12 |
| 33 | Duplicate count indicators | Task 11 |
| 34 | Card detail from binder | Task 17 |
| 35 | Any user can create set | Task 12 |
| 36 | Set fields | Task 2, 12 |
| 37 | Cards auto-match to sets | Task 12 |
| 38 | Completion percentage | Task 12 |
| 39 | GET /api/sets/{id}/missing | Task 12 |
| 40 | POST /api/trades | Task 13 |
| 41 | GET /api/trades | Task 13 |
| 42 | Accept/decline trade | Task 13 |
| 43 | Duplicates tradeable | Task 13 |
| 44 | No money/marketplace | Task 13 (verified by absence) |
| 45 | RESTful JSON endpoints | All tasks |
| 46 | UUID stable IDs | Task 2 |
| 47 | Pagination | Tasks 5, 6, 11 |
| 48 | Filterable resources | Tasks 5, 6, 11 |
| 49 | OpenAPI spec | Task 19 |
| 50 | Cloudflare + LAN access | Tasks 3, 19 |
| 51 | PWA manifest | Task 14 |
| 52 | Standalone display mode | Task 14 |
| 53 | App icons | Task 14 |
| 54 | Mobile-friendly layout | Tasks 15-18 |
| 55 | Responsive upload/binder | Tasks 15, 17 |
| 56 | All env vars | Task 1 |
| 57 | FastAPI backend | Task 1 |
| 58 | SvelteKit frontend | Task 14 |
| 59 | SQLite database | Task 2 |
| 60 | Local disk storage | Task 4 |
| 61 | Huey async jobs | Task 7 |
