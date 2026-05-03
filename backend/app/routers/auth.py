import logging
from fastapi import APIRouter, Depends, Request, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings
from app import storage
from app.services.region_service import get_region_codes

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


@router.get("/auth/debug")
async def auth_debug(request: Request):
    """Unauthenticated debug endpoint — shows raw auth state.

    Always accessible regardless of auth config. Use AUTH_DEBUG=true to
    enable verbose server-side logging; this endpoint always returns
    diagnostic info.
    """
    from jose import jwt, JWTError

    cf_assertion = request.headers.get("Cf-Access-Jwt-Assertion")
    cf_header = request.headers.get("CF_Authorization")
    cf_cookie = request.cookies.get("CF_Authorization")
    bearer = request.headers.get("Authorization", "")

    # Try decoding each CF source
    decode_results = {}
    for label, token in [
        ("cf_jwt_header", cf_assertion),
        ("cf_header", cf_header),
        ("cf_cookie", cf_cookie),
    ]:
        if token:
            try:
                payload = jwt.decode(token, key="", options={"verify_signature": False, "verify_aud": False})
                decode_results[label] = {
                    "found": True,
                    "decoded": True,
                    "email": payload.get("email"),
                    "aud": payload.get("aud"),
                    "iss": payload.get("iss"),
                    "exp": payload.get("exp"),
                    "nbf": payload.get("nbf"),
                    "iat": payload.get("iat"),
                    "common_name": payload.get("common_name"),
                    "claim_count": len(payload),
                    "token_preview": token[:80] + "..." if len(token) > 80 else token,
                }
            except JWTError as e:
                decode_results[label] = {
                    "found": True,
                    "decoded": False,
                    "error": str(e),
                    "token_preview": token[:80] + "..." if len(token) > 80 else token,
                }
        else:
            decode_results[label] = {"found": False}

    # Bearer check
    bearer_info = None
    if bearer.startswith("Bearer "):
        key = bearer[7:]
        user = __import__("app.auth", fromlist=["validate_api_key"]).validate_api_key(key)
        bearer_info = {
            "found": True,
            "valid": user is not None,
            "user": user,
            "key_preview": key[:8] + "..." if len(key) > 8 else key,
        }

    return {
        "sources": decode_results,
        "bearer": bearer_info,
        "cookies": list(request.cookies.keys()),
        "all_headers": dict(request.headers),
        "config": {
            "cf_access_enabled": settings.cf_access_enabled,
            "cf_team_domain": settings.cf_team_domain,
            "cf_aud_tag": settings.cf_aud_tag,
            "cf_verify_jwt": settings.cf_verify_jwt,
            "api_keys_count": len(settings.parsed_api_keys),
            "auth_debug": settings.auth_debug,
        },
    }


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
        "region": profile_user.region,
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

    if "region" in body:
        region = body["region"]
        if region is not None:
            try:
                get_region_codes(region)
            except ValueError:
                from fastapi import HTTPException

                raise HTTPException(status_code=422, detail=f"Invalid region: {region}")
        profile_user.region = region

    await db.commit()
    return {
        "email": profile_user.email,
        "display_name": profile_user.display_name,
        "avatar_path": profile_user.avatar_path,
        "region": profile_user.region,
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
