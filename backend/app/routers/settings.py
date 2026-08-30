import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_db
from app.dependencies import get_current_user
from app.services.app_settings import get_all_settings, set_setting, CONFIGURABLE_KEYS
from app.config import settings as app_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/ai")
async def get_ai_settings(
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    db_settings = await get_all_settings(db)
    result = {}
    for key, meta in CONFIGURABLE_KEYS.items():
        value = db_settings.get(key, getattr(app_settings, key, None))
        result[key] = {
            "value": value,
            "label": meta["label"],
            "description": meta["description"],
            "type": meta["type"],
            "source": "database" if key in db_settings else "environment",
        }
    return result


@router.patch("/ai")
async def update_ai_settings(
    body: dict,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    for key in body:
        if key not in CONFIGURABLE_KEYS:
            raise HTTPException(422, f"Key '{key}' is not configurable. Allowed: {', '.join(CONFIGURABLE_KEYS)}")
        if not isinstance(body[key], str):
            raise HTTPException(422, f"Value for '{key}' must be a string")
    updated = {}
    for key, value in body.items():
        await set_setting(db, key, value)
        updated[key] = value
    return updated
