import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.app_setting import AppSetting

logger = logging.getLogger(__name__)

CONFIGURABLE_KEYS = {
    "ai_model": {"label": "AI Vision Model", "description": "Model used for bird identification", "type": "string"},
    "ai_image_model": {"label": "AI Image Model", "description": "Model for card art generation (falls back to vision model)", "type": "string"},
    "card_style_name": {"label": "Card Art Style", "description": "Style name for card illustrations", "type": "string"},
    "birdbinder_id_prompt": {"label": "Identification Prompt", "description": "Custom system prompt for bird identification", "type": "text"},
}


async def get_setting(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    return setting.value if setting else None


async def set_setting(db: AsyncSession, key: str, value: str) -> AppSetting:
    if key not in CONFIGURABLE_KEYS:
        raise ValueError(f"Key '{key}' is not configurable from the UI")
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = value
    else:
        setting = AppSetting(key=key, value=value)
        db.add(setting)
    await db.commit()
    await db.refresh(setting)
    return setting


async def get_all_settings(db: AsyncSession) -> dict:
    result = await db.execute(select(AppSetting))
    settings = result.scalars().all()
    return {s.key: s.value for s in settings}
