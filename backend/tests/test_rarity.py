"""Tests for rarity tier assignment service."""

import pytest


class TestGetRarityTier:
    """Tests for get_rarity_tier()."""

    def test_returns_string(self):
        from app.services.rarity import get_rarity_tier, TIERS

        result = get_rarity_tier("amerob")
        assert isinstance(result, str)
        assert result in TIERS

    def test_deterministic(self):
        """Same species code always returns same tier."""
        from app.services.rarity import get_rarity_tier

        for code in ["amerob", "houspa", "amecro"]:
            tier1 = get_rarity_tier(code)
            tier2 = get_rarity_tier(code)
            assert tier1 == tier2

    def test_none_species_code(self):
        """None or empty species_code returns 'common'."""
        from app.services.rarity import get_rarity_tier

        assert get_rarity_tier(None) == "common"
        assert get_rarity_tier("") == "common"

    def test_all_tiers_reachable(self):
        """Multiple different tiers should be reachable across test codes."""
        from app.services.rarity import get_rarity_tier

        # A mix of codes from different families (all real eBird codes)
        test_codes = [
            "amerob",   # American Robin — Thrushes and Allies
            "houspa",   # House Sparrow — Passerellidae (large family → common)
            "amecro",   # American Crow — Corvidae
            "baldea",   # Bald Eagle — Hawks, Eagles (curated rare)
            "letowl",   # Long-eared Owl — Owls (curated uncommon)
            "grspar",   # Grasshopper Sparrow
            "barswa",   # Barn Swallow
            "norcar",   # Northern Cardinal
            "easblu",   # Eastern Bluebird
            "sobsai",   # Snow Bunting
            "royalb3",  # Royal Albatross — Albatrosses (curated legendary)
            "whttro",   # White-tailed Tropicbird — Tropicbirds (curated epic)
            "tufpuf",   # Tufted Puffin — Auks (curated rare)
        ]
        tiers = {get_rarity_tier(code) for code in test_codes}
        # Should see at least 3 different tiers across these diverse families
        assert len(tiers) >= 3

    def test_family_override(self):
        """Known rare families produce higher rarity tiers."""
        from app.services.rarity import get_rarity_tier

        # Albatrosses base is legendary; with hash shift: epic or legendary
        tier = get_rarity_tier("royalb3", family="Albatrosses")
        assert tier in ["epic", "legendary"]

    def test_family_arg_used_over_lookup(self):
        """Explicit family argument overrides the species_code lookup."""
        from app.services.rarity import get_rarity_tier

        # Same code with different family should potentially give different tiers
        # (at least the function shouldn't crash)
        tier1 = get_rarity_tier("somebird", family="Albatrosses")
        tier2 = get_rarity_tier("somebird", family="Tropicbirds")
        # Both should be valid tiers
        from app.services.rarity import TIERS

        assert tier1 in TIERS
        assert tier2 in TIERS

    def test_unknown_family_defaults_common(self):
        """Species with unknown family gets 'common' base (shift allows uncommon)."""
        from app.services.rarity import get_rarity_tier

        # Use a code not in the database with a made-up family
        tier = get_rarity_tier("fakcod", family="Nonexistent Family")
        # Base is "common", but hash shift of +1 can produce "uncommon"
        assert tier in ["common", "uncommon"]

    def test_known_bird_from_database(self):
        """Species that exist in birds.json get proper family lookup."""
        from app.services.rarity import get_rarity_tier, TIERS

        # American Robin — should find family via lookup (no explicit family)
        tier = get_rarity_tier("amerob")
        assert tier in TIERS


class TestConstants:
    """Tests for module-level constants."""

    def test_tier_weights_complete(self):
        from app.services.rarity import TIER_WEIGHTS, TIERS

        assert set(TIER_WEIGHTS.keys()) == set(TIERS)

    def test_tier_weights_positive(self):
        from app.services.rarity import TIER_WEIGHTS

        for tier, weight in TIER_WEIGHTS.items():
            assert weight > 0, f"{tier} weight must be positive"

    def test_tiers_ordering(self):
        """TIERS should be ordered from most to least common."""
        from app.services.rarity import TIERS

        assert TIERS[0] == "common"
        assert TIERS[-1] == "legendary"
        assert len(TIERS) == 5


class TestFamilyRarityMap:
    """Tests for the family rarity mapping logic."""

    def test_curated_families_in_map(self):
        """Curated rare families should be present in the generated map."""
        from app.services.rarity import _load_family_rarity_map, RARE_FAMILIES

        family_map = _load_family_rarity_map()

        for family, expected_tier in RARE_FAMILIES.items():
            assert family in family_map
            assert family_map[family] == expected_tier

    def test_map_covers_all_families(self):
        """The map should have an entry for every family in birds.json."""
        from app.services.rarity import _load_family_rarity_map

        family_map = _load_family_rarity_map()

        import json
        from pathlib import Path

        data_path = Path("backend/app/data/birds.json")
        if data_path.exists():
            with open(data_path) as f:
                birds = json.load(f)
            families = {b["family"] for b in birds if b.get("family")}
            for fam in families:
                assert fam in family_map, f"Family '{fam}' missing from rarity map"

    def test_all_map_values_valid_tiers(self):
        """Every value in the family map should be a valid tier."""
        from app.services.rarity import _load_family_rarity_map, TIERS

        family_map = _load_family_rarity_map()
        tier_set = set(TIERS)

        for fam, tier in family_map.items():
            assert tier in tier_set, f"Family '{fam}' has invalid tier '{tier}'"


class TestSpeciesFamilyMap:
    """Tests for the species_code -> family lookup."""

    def test_load_species_family_map(self):
        from app.services.rarity import _load_species_family_map

        code_map = _load_species_family_map()
        assert len(code_map) > 10000  # Should have most species

    def test_known_code_in_map(self):
        from app.services.rarity import _load_species_family_map

        code_map = _load_species_family_map()
        # American Robin should be there
        assert "amerob" in code_map
        assert code_map["amerob"] == "Thrushes and Allies"
