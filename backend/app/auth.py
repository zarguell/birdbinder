import logging
from jose import jwt, JWTError

from app.config import settings

logger = logging.getLogger(__name__)


def get_user_from_cf_jwt(token: str) -> str | None:
    """Decode Cloudflare Access JWT — no signature verification needed."""
    try:
        payload = jwt.decode(token, key="", options={"verify_signature": False, "verify_aud": False})
        email = payload.get("email")
        if settings.auth_debug:
            logger.info("CF JWT decoded successfully: email=%s", email)
            logger.info("JWT claims: %s", {k: v for k, v in payload.items() if k != "email"})
        return email
    except JWTError as e:
        if settings.auth_debug:
            logger.warning("CF JWT decode failed: %s", e)
        return None


def validate_api_key(key: str) -> str | None:
    """Validate Bearer API key. Returns user_identifier or None."""
    if key in settings.parsed_api_keys:
        return f"api-key:{key[:8]}"
    return None
