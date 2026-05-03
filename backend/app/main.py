from fastapi import FastAPI
from app.config import settings

app = FastAPI(title="BirdBinder", version="0.1.0")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
