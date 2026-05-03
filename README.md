# BirdBinder

Self-hosted, API-first PWA that turns bird sightings into collectible digital cards. Upload a photo, identify the bird with AI or manual entry, generate a card, and build your collection in digital binders organized by species, rarity, and curated sets.

## Features

- **Sighting Upload** — Camera capture or file upload with automatic EXIF extraction (GPS, date, camera)
- **AI Identification** — OpenAI Vision API identifies species, pose, and distinguishing traits. Manual override supported.
- **Card Generation** — Each sighting becomes a collectible card with AI-generated art (or original photo fallback)
- **Rarity System** — 5-tier rarity (Common → Legendary) derived from eBird taxonomy data (~17K species)
- **Binders** — Organize cards in custom binders with filtering by rarity, pose, date, and species
- **Sets** — Create curated card sets with completion tracking and missing-card detection
- **Trading** — Offer and accept card-for-card trades between users
- **PWA** — Installable on mobile with responsive card grid and touch-friendly UI

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.13, FastAPI, SQLAlchemy (async), Alembic |
| Frontend | SvelteKit (static adapter), Tailwind CSS v4 |
| Database | SQLite (aiosqlite) |
| Jobs | Huey (SQLite-backed) |
| Auth | Cloudflare Access JWT + Bearer API key |
| AI | OpenAI Vision (identification) + Image Gen (card art) |
| Deploy | Docker multi-stage, GitHub Actions CI/CD |

## Quick Start (Docker)

```bash
# Clone
git clone https://github.com/zarguell/birdbinder.git
cd birdbinder

# Create environment
cp backend/.env.example .env
# Edit .env — at minimum set API_KEYS (or leave empty for local-only mode)

# Start
docker compose up -d

# Check health
curl http://localhost:8000/api/health
```

Open `http://localhost:8000` in your browser. The API docs are at `/api/docs`.

## Authentication

BirdBinder supports two auth mechanisms:

| Method | Config | How it works |
|--------|--------|-------------|
| Bearer API key | `API_KEYS=key1,key2` | `Authorization: Bearer <key>` header |
| Cloudflare Access | `CF_ACCESS_ENABLED=true` + `CF_TEAM_DOMAIN` | `CF_Authorization` JWT header |

**Local development mode:** If neither `API_KEYS` nor `CF_ACCESS_ENABLED` is set, all requests are accepted as `local-user` with no authentication. This is convenient for local testing but **must not be used in production** — the server logs a warning at startup when running unauthenticated.

## Configuration

All config via environment variables (or `.env` file):

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEYS` | — | Comma-separated API keys for Bearer auth (omit for local mode) |
| `APP_URL` | `http://localhost:8000` | Base URL for the app |
| `AI_API_KEY` | — | OpenAI API key (enables AI identification + card art) |
| `AI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible API base URL |
| `AI_MODEL` | `gpt-4o` | Model for bird identification |
| `CF_ACCESS_ENABLED` | `false` | Enable Cloudflare Access JWT auth |
| `CF_TEAM_DOMAIN` | — | Cloudflare team domain for JWT verification |
| `BIRDBINDER_ID_PROMPT` | _(built-in)_ | Custom system prompt for bird identification |
| `CARD_STYLE_NAME` | `default` | Card art style name |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/birdbinder.db` | SQLAlchemy database URL |
| `STORAGE_PATH` | `./storage` | Directory for uploaded images and card art |
| `EBIRD_API_KEY` | — | eBird API key (optional, for data enrichment) |

## Development

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install uv && uv pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start dev server
uvicorn app.main:app --reload

# Start background worker (separate terminal)
huey_consumer.py app.huey_instance
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # Dev server at localhost:5173
npm run build        # Build to backend/app/static/
```

### API Docs

When the server is running:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Project Structure

```
birdbinder/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI app, routers, static serving
│   │   ├── config.py        # Pydantic Settings
│   │   ├── models/          # SQLAlchemy models (User, Sighting, Card, Binder, etc.)
│   │   ├── routers/         # API endpoints (sightings, cards, binders, sets, trades)
│   │   ├── services/        # Business logic (AI ID, card gen, rarity, species)
│   │   └── data/            # SQLite DB, eBird taxonomy JSON, uploaded images
│   ├── migrations/          # Alembic migrations
│   └── tests/               # pytest (152 tests)
├── frontend/
│   └── src/
│       ├── routes/          # SvelteKit pages (upload, sightings, binders, sets, trades)
│       └── lib/
│           ├── api.ts       # Typed API client
│           └── components/  # Svelte components (CardComponent, CardModal, etc.)
├── Dockerfile               # Multi-stage build (Node → Python)
├── docker-compose.yml
└── .github/workflows/       # CI (tests + Docker build)
```

## License

MIT
