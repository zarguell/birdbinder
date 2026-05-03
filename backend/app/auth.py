from jose import jwt, JWTError

from app.config import settings


def get_user_from_cf_jwt(token: str) -> str | None:
    """Decode Cloudflare Access JWT — no signature verification needed."""
    try:
        payload = jwt.decode(token, key="", options={"verify_signature": False})
        return payload.get("email")
    except JWTError:
        return None


def validate_api_key(key: str) -> str | None:
    """Validate Bearer API key. Returns user_identifier or None."""
    if key in settings.parsed_api_keys:
        return f"api-key:{key[:8]}"
    return None
