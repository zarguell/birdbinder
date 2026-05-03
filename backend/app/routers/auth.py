from fastapi import APIRouter, Depends, Request

from app.config import settings
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/auth/me")
async def auth_me(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Return the authenticated user identity and auth source for debugging."""
    cf_assertion = request.headers.get("Cf-Access-Jwt-Assertion")
    cf_header = request.headers.get("CF_Authorization")
    cf_cookie = request.cookies.get("CF_Authorization")
    bearer = request.headers.get("Authorization", "")

    # Determine auth_source based on what actually produced the user
    # (mirrors priority in get_current_user)
    if user != "local-user":
        cf_token = cf_assertion or cf_header or cf_cookie
        if cf_token and "@" in user:
            # CF auth succeeded (email was extracted from JWT)
            source = "cf-jwt-header" if cf_assertion else "cf-header" if cf_header else "cf-cookie"
        elif bearer.startswith("Bearer "):
            source = "api-key"
        else:
            source = "unknown"
    else:
        source = "local"

    return {
        "user_identifier": user,
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
