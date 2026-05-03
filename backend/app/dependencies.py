from fastapi import Depends, HTTPException, Request, status

from app.auth import get_user_from_cf_jwt, validate_api_key


async def get_current_user(request: Request) -> str:
    """Authenticate request via CF_Authorization JWT or Bearer API key.

    Checks the CF_Authorization header first (Cloudflare Access JWT).
    Falls back to Authorization: Bearer <key> validated against settings.
    Returns the user identifier string.
    Raises 401 if neither method succeeds.
    """
    # Check CF_Authorization header first
    cf_token = request.headers.get("CF_Authorization")
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

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
