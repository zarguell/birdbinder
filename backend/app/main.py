from fastapi import FastAPI, Depends
from app.config import settings
from app.dependencies import get_current_user
from app.routers import sightings

app = FastAPI(title="BirdBinder", version="0.1.0")

app.include_router(sightings.router, prefix="/api", tags=["sightings"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/me")
async def me(user: str = Depends(get_current_user)):
    return {"user": user}
