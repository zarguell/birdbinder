from __future__ import annotations

import json
from pathlib import Path

from app.services import taxonomy

# Module-level cache
_REGIONS_DATA: dict | None = None


def _load_regions() -> dict:
    global _REGIONS_DATA
    if _REGIONS_DATA is None:
        data_path = Path(__file__).parent.parent / "data" / "regions.json"
        with open(data_path) as f:
            _REGIONS_DATA = json.load(f)
    return _REGIONS_DATA


def get_available_regions() -> list[dict]:
    """Return the list of available regions from regions.json."""
    data = _load_regions()
    return data["regions"]


def get_region_species(region_id: str) -> list[dict]:
    """Return enriched species list for a region, sorted by taxon_order.

    Each species dict contains: code, common_name, scientific_name, family, taxon_order.
    Raises ValueError for unknown region_id.
    """
    regions = _load_regions()["regions"]
    region = None
    for r in regions:
        if r["id"] == region_id:
            region = r
            break
    if region is None:
        raise ValueError(f"Unknown region: {region_id}")

    birds_by_code = taxonomy.get_birds_by_code()
    species_list = []
    for code in region["species_codes"]:
        bird = birds_by_code.get(code)
        if bird:
            species_list.append({
                "code": bird["species_code"],
                "common_name": bird["common_name"],
                "scientific_name": bird["scientific_name"],
                "family": bird["family"],
                "taxon_order": bird["taxon_order"],
            })
    species_list.sort(key=lambda s: s["taxon_order"])
    return species_list


def get_region_codes(region_id: str) -> set[str]:
    """Return set of species codes for a region.

    Raises ValueError for unknown region_id.
    """
    regions = _load_regions()["regions"]
    region = None
    for r in regions:
        if r["id"] == region_id:
            region = r
            break
    if region is None:
        raise ValueError(f"Unknown region: {region_id}")

    return set(region["species_codes"])
