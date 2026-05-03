import logging

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from app.config import settings
from app.dependencies import get_current_user
from app.routers import cards, sightings, species, jobs, binders, sets, trades

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

app.include_router(sightings.router, prefix="/api", tags=["sightings"])
app.include_router(species.router, prefix="/api", tags=["species"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(cards.router, prefix="/api", tags=["cards"])
app.include_router(binders.router, prefix="/api", tags=["binders"])
app.include_router(sets.router, prefix="/api", tags=["sets"])
app.include_router(trades.router, prefix="/api", tags=["trades"])

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


@app.get("/api/me")
async def me(user: str = Depends(get_current_user)):
    return {"user": user}


# Serve frontend static assets
static_dir = Path(__file__).parent / "static"
assets_dir = static_dir / "assets"
if static_dir.exists() and assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{path:path}")
    async def serve_spa(path: str):
        file = static_dir / path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(static_dir / "index.html")
