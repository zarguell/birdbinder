from fastapi import APIRouter
from app.config import settings

router = APIRouter(tags=["version"])


@router.get("/version")
async def get_version():
    return {"commit": settings.git_sha}
