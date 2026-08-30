"""Rarity tier assignment from taxonomy data.

Assigns deterministic rarity tiers based on family-level heuristics.
Since we don't have real observation frequency data, we use:
1. A curated list of known-rare families
2. Species count per family (smaller families tend to be rarer)
3. Deterministic hash-based shifting within tier neighborhoods
"""

import json
from pathlib import Path

__all__ = ["TIER_WEIGHTS", "get_rarity_tier", "TIERS"]

# Ordered from most to least common
TIERS = ["common", "uncommon", "rare", "epic", "legendary"]

# Tier weights for random selection (not used for deterministic assignment,
# but useful as reference for card pack odds, etc.)
TIER_WEIGHTS = {
    "common": 50,
    "uncommon": 25,
    "rare": 15,
    "epic": 7,
    "legendary": 3,
}

# Families known to be generally rarer — curated override
RARE_FAMILIES: dict[str, str] = {
    # Accipitridae - Hawks, Eagles
    "Hawks, Eagles, and Kites": "rare",
    "Owls": "uncommon",
    # Rails, Gallinules, Coots
    "Rails, Gallinules, and Coots": "uncommon",
    # Shorebirds
    "Sandpipers and Allies": "uncommon",
    # Alcids
    "Auks, Murres, and Puffins": "rare",
    # Tropicbirds
    "Tropicbirds": "epic",
    # Frigatebirds
    "Frigatebirds": "epic",
    # Albatrosses
    "Albatrosses": "legendary",
}

# Module-level caches (populated on first call)
_family_rarity_map: dict[str, str] | None = None
_species_family_map: dict[str, str] | None = None
_rarity_cache: dict[str, str] = {}


def _load_family_rarity_map() -> dict[str, str]:
    """Load bird data and build family -> base rarity mapping.

    Combines curated RARE_FAMILIES with heuristics based on species count
    per family.
    """
    global _family_rarity_map

    if _family_rarity_map is not None:
        return _family_rarity_map

    data_path = Path(__file__).parent.parent / "data" / "birds.json"
    with open(data_path) as f:
        birds = json.load(f)

    # Count species per family
    family_counts: dict[str, int] = {}
    for bird in birds:
        fam = bird.get("family", "")
        if fam:
            family_counts[fam] = family_counts.get(fam, 0) + 1

    # Start with curated overrides, then fill in the rest
    family_rarity = dict(RARE_FAMILIES)
    for fam, count in family_counts.items():
        if fam not in family_rarity:
            if count <= 5:
                family_rarity[fam] = "uncommon"
            else:
                family_rarity[fam] = "common"

    _family_rarity_map = family_rarity
    return family_rarity


def _load_species_family_map() -> dict[str, str]:
    """Build species_code -> family lookup map."""
    global _species_family_map

    if _species_family_map is not None:
        return _species_family_map

    data_path = Path(__file__).parent.parent / "data" / "birds.json"
    with open(data_path) as f:
        birds = json.load(f)

    _species_family_map = {
        b["species_code"]: b["family"]
        for b in birds
        if b.get("species_code") and b.get("family")
    }
    return _species_family_map


def get_rarity_tier(
    species_code: str | None,
    family: str | None = None,
    region: str | None = None,
) -> str:
    """Get rarity tier for a species.

    If *region* is provided and eBird live frequency data is available,
    the tier is determined from observation frequency.  Otherwise the
    static family-based heuristic is used as a fallback.

    Args:
        species_code: 6-letter eBird species code.
        family: Optional family name override. If not provided, the family
                is looked up from the birds data using species_code.
        region: Optional eBird region code (e.g. "US-NY").  When supplied,
                live eBird frequency data takes priority over static logic.

    Returns:
        One of: "common", "uncommon", "rare", "epic", "legendary"
    """
    if not species_code:
        return "common"

    # Check eBird live data first if region is provided
    if region and species_code:
        try:
            from app.services.ebird_service import _cache as ebird_cache, get_ebird_rarity_tier
            freq = ebird_cache.get(region, species_code)
            if freq is not None:
                return get_ebird_rarity_tier(region, species_code, frequency=freq)
        except Exception:
            pass

    # Load maps lazily
    family_map = _load_family_rarity_map()
    code_to_family = _load_species_family_map()

    # Resolve family: explicit arg > lookup from species_code > unknown
    resolved_family = family or code_to_family.get(species_code)

    # Cache key includes resolved family so different overrides don't collide
    cache_key = (species_code, resolved_family)
    if cache_key in _rarity_cache:
        return _rarity_cache[cache_key]

    # Get base rarity for the family
    base_rarity = "common"
    if resolved_family and resolved_family in family_map:
        base_rarity = family_map[resolved_family]

    # Deterministic shift based on hash of species_code
    base_idx = TIERS.index(base_rarity) if base_rarity in TIERS else 0

    # Use hash to determine a shift of -1, 0, or +1 tier
    hash_val = hash(species_code)
    shift = (hash_val % 3) - 1  # -1, 0, or +1
    new_idx = max(0, min(len(TIERS) - 1, base_idx + shift))

    tier = TIERS[new_idx]
    _rarity_cache[cache_key] = tier
    return tier
