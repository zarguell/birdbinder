import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import settings
from app.dependencies import get_current_user
from app.routers import cards, sightings, species, jobs, binders, sets, trades, auth, settings as settings_router, activity as activity_router, users, version
from app.routers.collection import router as collection_router
from app import storage

logger = logging.getLogger(__name__)

app = FastAPI(
    title="BirdBinder",
    version="0.1.0",
    description="Birding card-collection app — upload sightings, collect cards, complete sets, trade with friends.",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(sightings.router, prefix="/api", tags=["sightings"])
app.include_router(species.router, prefix="/api", tags=["species"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(cards.router, prefix="/api", tags=["cards"])
app.include_router(binders.router, prefix="/api", tags=["binders"])
app.include_router(sets.router, prefix="/api", tags=["sets"])
app.include_router(trades.router, prefix="/api", tags=["trades"])
app.include_router(settings_router.router, prefix="/api", tags=["settings"])
app.include_router(activity_router.router, prefix="/api", tags=["activity"])
app.include_router(collection_router, prefix="/api", tags=["collection"])
app.include_router(users.router, prefix="/api", tags=["users"])
app.include_router(version.router, prefix="/api", tags=["version"])

# Warn if running without authentication
if not settings.parsed_api_keys and not settings.cf_access_enabled:
    logger.warning(
        "⚠ No authentication configured (API_KEYS and CF_ACCESS_ENABLED both unset). "
        "All requests will be accepted as 'local-user'. "
        "Do NOT use this configuration in production."
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve user-uploaded files (avatars, sightings photos, card art)
storage_dir = storage.get_storage_path()
if storage_dir.exists():
    app.mount("/storage", StaticFiles(directory=storage_dir), name="storage")


# Serve frontend static assets (SvelteKit adapter-static output)
static_dir = Path(__file__).parent / "static"
app_dir = static_dir / "_app"
if static_dir.exists() and app_dir.exists():
    # Mount SvelteKit build artifacts
    app.mount("/_app", StaticFiles(directory=app_dir), name="sveltekit-app")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        # Serve root-level static files (manifest.json, icons, robots.txt, etc.)
        file = static_dir / path
        if file.is_file():
            return FileResponse(file)
        # SPA fallback — let client-side router handle it
        return FileResponse(static_dir / "index.html")
