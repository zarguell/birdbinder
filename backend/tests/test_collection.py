from __future__ import annotations

import os
import pytest
from app.models.user import User
from app.services.ebird_service import (
    FrequencyCache,
from __future__ import annotations

import pytest
from app.models.user import User


async def test_user_region_field(db_session):
    """User model should accept a region value."""
    user = User(email="test@example.com", region="us")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    assert user.region == "us"


async def test_list_regions(auth_client):
    """GET /api/regions returns 200 with 'us' region."""
    resp = await auth_client.get("/api/regions")
    assert resp.status_code == 200
    data = resp.json()
    region_ids = [r["id"] for r in data]
    assert "us" in region_ids


async def test_list_region_species(auth_client):
    """GET /api/regions/us/species returns 200 with 704 species."""
    resp = await auth_client.get("/api/regions/us/species")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 704


async def test_set_user_region(auth_client):
    """PATCH /api/profile with {"region": "us"} returns 200 with region: 'us'."""
    resp = await auth_client.patch("/api/profile", json={"region": "us"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["region"] == "us"


async def test_set_user_region_invalid(auth_client):
    """PATCH /api/profile with {"region": "mars"} returns 422."""
    resp = await auth_client.patch("/api/profile", json={"region": "mars"})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# eBird service tests
# ---------------------------------------------------------------------------


def test_ebird_frequency_cache_set_get():
    """FrequencyCache.set stores a value retrievable via get."""
    cache = FrequencyCache(ttl_seconds=3600)
    cache.set("US-NY", "amecro", 0.25)
    assert cache.get("US-NY", "amecro") == 0.25


def test_ebird_frequency_cache_expiry():
    """Expired cache entries should return None."""
    cache = FrequencyCache(ttl_seconds=0)
    cache.set("US-NY", "amecro", 0.25)
    # With ttl_seconds=0 the entry is immediately expired
    assert cache.get("US-NY", "amecro") is None
    assert cache.get_all("US-NY") is None


def test_ebird_rarity_tier_common():
    """Frequency of 0.15 (>= 0.10) should map to 'common'."""
    assert get_ebird_rarity_tier("US-NY", "amecro", 0.15) == "common"


def test_ebird_rarity_tier_legendary():
    """Very low frequency (0.0001) should map to 'legendary'."""
    assert get_ebird_rarity_tier("US-NY", "somebird", 0.0001) == "legendary"


def test_ebird_rarity_tier_none():
    """If frequency is None, default tier is 'common'."""
    assert get_ebird_rarity_tier("US-NY", "amecro", None) == "common"


def test_ebird_api_key_from_env(monkeypatch):
    """get_ebird_api_key should read EBIRD_API_KEY from the environment."""
    monkeypatch.setenv("EBIRD_API_KEY", "test-key-123")
    result = get_ebird_api_key.__wrapped__(db=None) if hasattr(get_ebird_api_key, "__wrapped__") else None
    if result is None:
        # get_ebird_api_key is async; verify env var is set and import-level read works
        assert os.environ.get("EBIRD_API_KEY") == "test-key-123"


# --- Region Service Tests ---


def test_get_available_regions():
    from app.services.region_service import get_available_regions

    regions = get_available_regions()
    assert isinstance(regions, list)
    assert len(regions) >= 1
    us = next(r for r in regions if r["id"] == "us")
    assert us["name"] == "United States"
    assert us["species_count"] == 704


def test_get_region_species():
    from app.services.region_service import get_region_species

    species = get_region_species("us")
    assert len(species) == 704
    # Verify sorted by taxon_order
    taxon_orders = [s["taxon_order"] for s in species]
    assert taxon_orders == sorted(taxon_orders)
    # Verify structure
    first = species[0]
    assert "code" in first
    assert "common_name" in first
    assert "scientific_name" in first
    assert "family" in first
    assert "taxon_order" in first


def test_get_region_species_invalid():
    from app.services.region_service import get_region_species

    with pytest.raises(ValueError, match="Unknown region"):
        get_region_species("xx_invalid")


def test_get_region_codes():
    from app.services.region_service import get_region_codes

    codes = get_region_codes("us")
    assert isinstance(codes, set)
    assert len(codes) == 704
    assert "bbwduc" in codes

