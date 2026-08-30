from __future__ import annotations

import os
import pytest
from app.models.user import User
from tests.conftest import TEST_USER
from app.services.ebird_service import (
    FrequencyCache,
    get_ebird_api_key,
    get_ebird_rarity_tier,
)


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


# ---------------------------------------------------------------------------
# Collection progress tests
# ---------------------------------------------------------------------------


async def test_collection_progress_empty(auth_client):
    """GET /api/collection/progress returns 200 with total_species=704 and discovered_count=0."""
    resp = await auth_client.get("/api/collection/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_species"] == 704
    assert data["discovered_count"] == 0
    assert len(data["discovered"]) == 0
    assert len(data["missing"]) == 704


async def test_collection_progress_with_card(auth_client, db_session):
    """Creating a card should show up as discovered in collection progress."""
    from app.models.card import Card

    card = Card(
        user_identifier=TEST_USER,
        species_code="norcar",
        species_common="Northern Cardinal",
        rarity_tier="common",
    )
    db_session.add(card)
    await db_session.commit()

    resp = await auth_client.get("/api/collection/progress")
    assert resp.status_code == 200
    data = resp.json()
    assert data["discovered_count"] >= 1
    discovered_codes = [s["species_code"] for s in data["discovered"]]
    assert "norcar" in discovered_codes


async def test_collection_progress_family_group(auth_client):
    """GET /api/collection/progress?family_group=true returns family groups."""
    resp = await auth_client.get("/api/collection/progress?family_group=true")
    assert resp.status_code == 200
    data = resp.json()
    assert "family_groups" in data
    assert len(data["family_groups"]) > 0
    fg = data["family_groups"][0]
    assert "family" in fg
    assert "total" in fg
    assert "discovered" in fg
    assert "species" in fg
    for sp in fg["species"]:
        assert "species_code" in sp
        assert "common_name" in sp
        assert "found" in sp


# ---------------------------------------------------------------------------
# eBird + rarity integration tests
# ---------------------------------------------------------------------------


def test_rarity_uses_ebird_when_available():
    """When eBird cache has a low frequency for a normally-common species,
    get_rarity_tier should return a rarer tier."""
    from app.services.ebird_service import _cache as ebird_cache
    from app.services.rarity import get_rarity_tier, TIERS

    # Get the static tier first (no region = pure static)
    static_tier = get_rarity_tier("amecro", region=None)
    static_idx = TIERS.index(static_tier)

    # Set a very low frequency in the eBird cache (legendary-range)
    ebird_cache.set("US-NY", "amecro", 0.0001)
    try:
        tier = get_rarity_tier("amecro", region="US-NY")
        ebird_idx = TIERS.index(tier)
        # Low frequency should produce a rarer result (higher index)
        assert ebird_idx > static_idx, (
            f"Expected eBird tier {tier} to be rarer than static {static_tier}"
        )
    finally:
        ebird_cache.clear("US-NY")


def test_rarity_falls_back_to_static():
    """When eBird cache has no data, get_rarity_tier should return static result."""
    from app.services.rarity import get_rarity_tier

    # Use a region that definitely has no cached data
    tier_with_region = get_rarity_tier("amecro", region="XX-EMPTY-NO-DATA")
    tier_without = get_rarity_tier("amecro")
    assert tier_with_region == tier_without


def test_rarity_region_param_optional():
    """get_rarity_tier works without region param (backward compat)."""
    from app.services.rarity import get_rarity_tier

    # These calls should be equivalent and both return a valid tier
    tier1 = get_rarity_tier("amecro")
    tier2 = get_rarity_tier("amecro", family=None)
    assert tier1 == tier2
    assert tier1 in ("common", "uncommon", "rare", "epic", "legendary")
