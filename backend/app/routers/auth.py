import logging
from fastapi import APIRouter, Depends, Request, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings
from app import storage

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_or_create_user(
    user_identifier: str,
    db: AsyncSession,
) -> User:
    """Find user by email, or create on first login."""
    result = await db.execute(
        select(User).where(User.email == user_identifier)
    )
    user = result.scalar_one_or_none()
    if not user:
        user = User(email=user_identifier)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        logger.info("Created new user profile: %s", user_identifier)
    return user


@router.get("/auth/me")
async def auth_me(
    request: Request,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return authenticated user identity, profile, and auth source."""
    cf_assertion = request.headers.get("Cf-Access-Jwt-Assertion")
    cf_header = request.headers.get("CF_Authorization")
    cf_cookie = request.cookies.get("CF_Authorization")
    bearer = request.headers.get("Authorization", "")

    # Determine auth_source
    if user != "local-user":
        cf_token = cf_assertion or cf_header or cf_cookie
        if cf_token and "@" in user:
            source = "cf-jwt-header" if cf_assertion else "cf-header" if cf_header else "cf-cookie"
        elif bearer.startswith("Bearer "):
            source = "api-key"
        else:
            source = "unknown"
    else:
        source = "local"

    # Get or create user profile (skip for local-user)
    profile = None
    if user != "local-user":
        try:
            profile_user = await get_or_create_user(user, db)
            profile = {
                "display_name": profile_user.display_name,
                "avatar_path": profile_user.avatar_path,
            }
        except Exception:
            logger.warning("Failed to load user profile for %s", user, exc_info=True)

    return {
        "user_identifier": user,
        "display_name": profile["display_name"] if profile else None,
        "avatar_path": profile["avatar_path"] if profile else None,
        "auth_source": source,
        "has_cf_jwt_header": cf_assertion is not None,
        "has_cf_cookie": cf_cookie is not None,
        "has_cf_raw_header": cf_header is not None,
        "has_bearer_header": bearer.startswith("Bearer "),
    }


@router.get("/auth/settings")
async def auth_settings(
    _user: str = Depends(get_current_user),
):
    """Return app configuration for debugging — no secrets included."""
    return {
        "auth_mode": (
            "cloudflare"
            if settings.cf_access_enabled
            else "api_key" if settings.parsed_api_keys
            else "local"
        ),
        "cf_access_enabled": settings.cf_access_enabled,
        "cf_team_domain": settings.cf_team_domain or "(not set)",
        "api_keys_configured": len(settings.parsed_api_keys),
        "ai_base_url": settings.ai_base_url or "(default: OpenAI)",
        "ai_model": settings.ai_model,
        "ai_image_model": settings.ai_image_model or "(same as ai_model)",
        "ai_enabled": bool(settings.ai_api_key),
        "card_style": settings.card_style_name,
        "storage_path": settings.storage_path,
        "database_url": settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url,
    }


@router.get("/profile")
async def get_profile(
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user profile details."""
    if user == "local-user":
        return {
            "email": "local-user",
            "display_name": None,
            "avatar_path": None,
            "created_at": None,
        }

    profile_user = await get_or_create_user(user, db)
    return {
        "email": profile_user.email,
        "display_name": profile_user.display_name,
        "avatar_path": profile_user.avatar_path,
        "created_at": profile_user.created_at.isoformat() if profile_user.created_at else None,
    }


@router.patch("/profile")
async def update_profile(
    request: Request,
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update display name and/or avatar for the current user."""
    if user == "local-user":
        return {"detail": "Cannot update profile for local user"}

    body = await request.json()
    profile_user = await get_or_create_user(user, db)

    if "display_name" in body:
        display_name = body["display_name"]
        if display_name is not None:
            display_name = str(display_name).strip() or None
        profile_user.display_name = display_name

    await db.commit()
    return {
        "email": profile_user.email,
        "display_name": profile_user.display_name,
        "avatar_path": profile_user.avatar_path,
    }


@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a profile avatar image (jpg, png, webp — max 2MB)."""
    if user == "local-user":
        return {"detail": "Cannot update profile for local user"}

    import uuid as _uuid
    from fastapi import HTTPException, status

    # Validate file type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only jpeg, png, and webp images are allowed",
        )

    # Read and check size (2MB max)
    content = await file.read()
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image must be under 2MB",
        )

    # Save
    ext_map = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}
    ext = ext_map.get(file.content_type, "jpg")
    avatar_dir = storage.get_storage_path() / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{_uuid.uuid4()}.{ext}"
    (avatar_dir / filename).write_bytes(content)

    profile_user = await get_or_create_user(user, db)
    profile_user.avatar_path = f"avatars/{filename}"
    await db.commit()

    return {
        "email": profile_user.email,
        "display_name": profile_user.display_name,
        "avatar_path": profile_user.avatar_path,
    }
