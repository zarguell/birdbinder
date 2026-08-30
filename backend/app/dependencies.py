import logging
from fastapi import Depends, HTTPException, Request, status

from app.auth import get_user_from_cf_jwt, validate_api_key
from app.config import settings

logger = logging.getLogger(__name__)


async def get_current_user(request: Request) -> str:
    """Authenticate request via CF_Authorization JWT or Bearer API key.

    If no auth mechanism is configured (no API_KEYS and CF disabled),
    returns a default local user — no auth required.

    Checks the CF_Authorization header first (Cloudflare Access JWT).
    Falls back to Authorization: Bearer *** validated against settings.
    Returns the user identifier string.
    Raises 401 if auth is configured but credentials are missing/invalid.
    """
    # Check Cloudflare Access JWT — try header then cookie
    cf_assertion = request.headers.get("Cf-Access-Jwt-Assertion")
    cf_header = request.headers.get("CF_Authorization")
    cf_cookie = request.cookies.get("CF_Authorization")
    cf_token = cf_assertion or cf_header or cf_cookie

    if cf_token:
        if settings.auth_debug:
            logger.info(
                "Auth attempt — CF sources: jwt_header=%s, cf_header=%s, cf_cookie=%s",
                bool(cf_assertion), bool(cf_header), bool(cf_cookie),
            )
        user = get_user_from_cf_jwt(cf_token)
        if user:
            if settings.auth_debug:
                logger.info("Auth succeeded via CF JWT: %s", user)
            return user
        # Token present but couldn't decode — don't fall through silently
        if settings.cf_access_enabled:
            if settings.auth_debug:
                logger.warning("CF token present but decode returned None, cf_access_enabled=true → 401")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="CF JWT present but could not be decoded",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Check Bearer API key
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        key = auth_header[7:]
        user = validate_api_key(key)
        if user:
            if settings.auth_debug:
                logger.info("Auth succeeded via API key: %s", user)
            return user

    # No auth configured — allow unauthenticated local access
    if not settings.parsed_api_keys and not settings.cf_access_enabled:
        return "local-user"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
