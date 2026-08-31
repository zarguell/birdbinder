import logging
import time

import httpx
import jwt

from app.config import settings

logger = logging.getLogger(__name__)

# Cache for CF Access public keys: {kid: (pem_string, fetched_at)}
_cf_keys_cache: dict[str, tuple[str, float]] = {}
_CF_CERTS_TTL = 300  # 5 minutes


def _fetch_cf_public_keys() -> dict[str, str]:
    """Fetch RS256 public keys from Cloudflare Access certs endpoint.

    Returns dict of {kid: PEM-formatted public key}.
    Keys are cached for 5 minutes.
    """
    if not settings.cf_team_domain:
        logger.error("CF_VERIFY_JWT enabled but CF_TEAM_DOMAIN is not set")
        return {}

    now = time.monotonic()
    # Return cached keys if fresh
    if _cf_keys_cache:
        oldest = min(ts for _, ts in _cf_keys_cache.values())
        if now - oldest < _CF_CERTS_TTL:
            if settings.auth_debug:
                logger.info("Using cached CF public keys (%d keys)", len(_cf_keys_cache))
            return {kid: pem for kid, (pem, _) in _cf_keys_cache.items()}

    # Fetch from CF
    certs_url = f"https://{settings.cf_team_domain}.cloudflareaccess.com/cdn-cgi/access/certs"
    try:
        resp = httpx.get(certs_url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning("Failed to fetch CF Access certs from %s: %s", certs_url, e)
        # Return stale cache if available
        if _cf_keys_cache:
            logger.warning("Using stale cached CF public keys")
            return {kid: pem for kid, (pem, _) in _cf_keys_cache.items()}
        return {}

    keys: dict[str, str] = {}
    for key_data in data.get("keys", []):
        kid = key_data.get("kid")
        if not kid:
            continue
        # Convert JWK to PEM
        try:
            import base64 as _b64

            def _b64url_decode(value: str) -> bytes:
                return _b64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

            # Build PEM from RSA components
            n = _b64url_decode(key_data["n"])
            e = _b64url_decode(key_data["e"])
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
            from cryptography.hazmat.primitives import serialization
            pub_numbers = RSAPublicNumbers(
                e=int.from_bytes(e, "big"),
                n=int.from_bytes(n, "big"),
            )
            pub_key = pub_numbers.public_key()
            pem = pub_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            ).decode()
            keys[kid] = pem
        except Exception as e:
            logger.warning("Failed to parse CF public key kid=%s: %s", kid, e)

    if keys:
        ts = time.monotonic()
        _cf_keys_cache.clear()
        for kid, pem in keys.items():
            _cf_keys_cache[kid] = (pem, ts)
        if settings.auth_debug:
            logger.info("Fetched %d CF public keys from %s", len(keys), certs_url)

    return keys


def _get_cf_issuer() -> str:
    """Build the expected issuer URL from the team domain."""
    return f"https://{settings.cf_team_domain}.cloudflareaccess.com"


def get_user_from_cf_jwt(token: str) -> str | None:
    """Decode and optionally verify a Cloudflare Access JWT.

    Modes:
    - CF_VERIFY_JWT=false (default): Decode without verification.
      CF already validated the token before forwarding it — only safe when
      the app is ONLY reachable through Cloudflare Access.
    - CF_VERIFY_JWT=true: Full RS256 signature verification using
      CF's public keys, plus iss/aud claim checks. Fails closed: if the
      signature is invalid or no public key is available, the token is
      rejected (returns None).
    """
    if settings.cf_verify_jwt:
        return _verify_cf_jwt(token)
    return _decode_cf_jwt_unverified(token)


def _verify_cf_jwt(token: str) -> str | None:
    """Verify CF Access JWT signature + claims. Fails closed on any error."""
    keys = _fetch_cf_public_keys()

    # Get the key ID from the JWT header
    try:
        unverified = jwt.get_unverified_header(token)
        kid = unverified.get("kid")
    except jwt.InvalidTokenError:
        kid = None

    if not kid or kid not in keys:
        logger.error(
            "CF JWT rejected: no public key for kid=%s (have %d keys cached)",
            kid, len(keys),
        )
        return None

    pem = keys[kid]
    expected_iss = _get_cf_issuer()
    decode_options = {"verify_signature": True}
    if not settings.cf_aud_tag:
        decode_options["verify_aud"] = False

    try:
        payload = jwt.decode(
            token,
            pem,
            algorithms=["RS256"],
            options=decode_options,
            issuer=expected_iss,
            audience=settings.cf_aud_tag,
        )
        email = payload.get("email")
        if settings.auth_debug:
            logger.info("CF JWT verified (kid=%s): email=%s", kid, email)
        return email
    except jwt.InvalidTokenError as e:
        logger.error("CF JWT signature verification failed (kid=%s): %s", kid, e)
        return None


def _decode_cf_jwt_unverified(token: str) -> str | None:
    """Decode CF Access JWT without signature verification."""
    try:
        payload = jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        email = payload.get("email")
        if settings.auth_debug:
            logger.info("CF JWT decoded (unverified): email=%s", email)
            logger.info("JWT claims: %s", {k: v for k, v in payload.items() if k != "email"})
        return email
    except jwt.InvalidTokenError as e:
        if settings.auth_debug:
            logger.warning("CF JWT decode failed: %s", e)
        return None


def validate_api_key(key: str) -> str | None:
    """Validate Bearer API key. Returns user_identifier or None."""
    if key in settings.parsed_api_keys:
        return f"api-key:{key[:8]}"
    return None
