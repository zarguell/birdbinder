from fastapi import Depends, HTTPException, Request, status

from app.auth import get_user_from_cf_jwt, validate_api_key
from app.config import settings


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
    # Cf-Access-Jwt-Assertion: HTTP header injected by CF Tunnel to origin
    # CF_Authorization: cookie set on browser by CF Access (forwarded to origin as cookie)
    cf_token = (
        request.headers.get("Cf-Access-Jwt-Assertion")
        or request.headers.get("CF_Authorization")
        or request.cookies.get("CF_Authorization")
    )
    if cf_token:
        user = get_user_from_cf_jwt(cf_token)
        if user:
            return user

    # Check Bearer API key
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        key = auth_header[7:]
        user = validate_api_key(key)
        if user:
            return user

    # No auth configured — allow unauthenticated local access
    if not settings.parsed_api_keys and not settings.cf_access_enabled:
        return "local-user"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
