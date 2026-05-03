from __future__ import annotations

import os
import time
from typing import Any

import httpx

from app.services import app_settings

__all__ = [
    "FrequencyCache",
    "FREQUENCY_THRESHOLDS",
    "_cache",
    "fetch_region_frequencies",
    "get_ebird_api_key",
    "get_ebird_rarity_tier",
    "get_live_frequency",
]

# ---------------------------------------------------------------------------
# Rarity tier thresholds based on observation frequency
# ---------------------------------------------------------------------------
FREQUENCY_THRESHOLDS: dict[str, float] = {
    "common": 0.10,
    "uncommon": 0.03,
    "rare": 0.005,
    "epic": 0.001,
    "legendary": 0.0,
}

# ---------------------------------------------------------------------------
# In-memory TTL cache for region frequency data
# ---------------------------------------------------------------------------

Entry = tuple[float, dict[str, float]]  # (timestamp, {species_code: frequency})


class FrequencyCache:
    """In-memory TTL cache keyed by region, storing per-species frequencies."""

    def __init__(self, ttl_seconds: int = 3600) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, Entry] = {}

    def set(self, region: str, species_code: str, frequency: float) -> None:
        """Set (or update) a single species frequency for *region*."""
        now = time.monotonic()
        if region in self._store:
            ts, data = self._store[region]
            # Refresh timestamp only if not already expired
            if now - ts > self._ttl:
                data = {}
            data[species_code] = frequency
            self._store[region] = (now, data)
        else:
            self._store[region] = (now, {species_code: frequency})

    def get(self, region: str, species_code: str) -> float | None:
        """Return frequency for a single species, or *None* if missing/expired."""
        entry = self._store.get(region)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[region]
            return None
        return data.get(species_code)

    def get_all(self, region: str) -> dict[str, float] | None:
        """Return all species frequencies for *region*, or *None* if expired."""
        entry = self._store.get(region)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > self._ttl:
            del self._store[region]
            return None
        return dict(data)

    def clear(self, region: str | None = None) -> None:
        """Clear cache. If *region* is given, clear only that region."""
        if region is None:
            self._store.clear()
        else:
            self._store.pop(region, None)


# Global singleton — 1-hour TTL
_cache = FrequencyCache(ttl_seconds=3600)


# ---------------------------------------------------------------------------
# API-key helpers
# ---------------------------------------------------------------------------

async def get_ebird_api_key(db: Any = None) -> str | None:
    """Return the eBird API key from the environment or app settings."""
    key = os.environ.get("EBIRD_API_KEY")
    if key:
        return key
    if db is not None:
        return await app_settings.get_setting(db, "ebird_api_key")
    return None


# ---------------------------------------------------------------------------
# Rarity-tier conversion
# ---------------------------------------------------------------------------

def get_ebird_rarity_tier(
    region: str,
    species_code: str,
    frequency: float | None = None,
) -> str:
    """Determine rarity tier from observation frequency.

    If *frequency* is ``None`` (data unavailable), defaults to ``"common"``.
    """
    if frequency is None:
        return "common"

    # Tiers are ordered from most to least common; thresholds are minimums.
    for tier_name, min_freq in FREQUENCY_THRESHOLDS.items():
        if frequency >= min_freq:
            return tier_name

    # Should never reach here since legendary threshold is 0.0
    return "legendary"


# ---------------------------------------------------------------------------
# Fetch & live-lookup helpers
# ---------------------------------------------------------------------------

async def fetch_region_frequencies(
    region: str,
    api_key: str,
) -> dict[str, float]:
    """Fetch regional frequency data from the eBird API.

    TODO: Implement the actual API call to
    GET https://api.ebird.org/v2/product/regional-stats/{region}
    with the ``api_key`` as a query parameter / header.
    For now, returns an empty dict as a placeholder.
    """
    # TODO: Uncomment and complete when ready to hit the real endpoint.
    # async with httpx.AsyncClient() as client:
    #     resp = await client.get(
    #         f"https://api.ebird.org/v2/product/regional-stats/{region}",
    #         params={"key": api_key},
    #         headers={"X-eBirdApiToken": api_key},
    #     )
    #     resp.raise_for_status()
    #     # Parse response into {species_code: frequency, ...}
    #     ...
    return {}


async def get_live_frequency(
    region: str,
    species_code: str,
    db: Any = None,
) -> float | None:
    """Return the live observation frequency for a species in a region.

    Checks the in-memory cache first.  On a cache miss, fetches from the
    eBird API (if an API key is available) and populates the cache.
    """
    cached = _cache.get(region, species_code)
    if cached is not None:
        return cached

    api_key = await get_ebird_api_key(db)
    if api_key is None:
        return None

    freq_map = await fetch_region_frequencies(region, api_key)
    if not freq_map:
        return None

    # Populate the full region cache
    now = time.monotonic()
    _cache._store[region] = (now, freq_map)
    return freq_map.get(species_code)
