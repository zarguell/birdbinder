from fastapi import FastAPI, Depends
from app.config import settings
from app.dependencies import get_current_user
from app.routers import cards, sightings, species, jobs, binders, sets, trades

app = FastAPI(title="BirdBinder", version="0.1.0")

app.include_router(sightings.router, prefix="/api", tags=["sightings"])
app.include_router(species.router, prefix="/api", tags=["species"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(cards.router, prefix="/api", tags=["cards"])
app.include_router(binders.router, prefix="/api", tags=["binders"])
app.include_router(sets.router, prefix="/api", tags=["sets"])
app.include_router(trades.router, prefix="/api", tags=["trades"])


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/me")
async def me(user: str = Depends(get_current_user)):
    return {"user": user}
