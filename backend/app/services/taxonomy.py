"""Single cached loader for the static taxonomy dataset (birds.json).

All consumers — species search, region service, rarity assignment, and the
identification task — must read through this module instead of opening the
file themselves, so the 2.7 MB dataset is parsed once per process.
"""

import json
from pathlib import Path

_DATA_PATH = Path(__file__).parent.parent / "data" / "birds.json"

_birds: list[dict] | None = None
_by_code: dict[str, dict] | None = None
_by_name: dict[str, dict] | None = None


def get_birds() -> list[dict]:
    """Return the full taxonomy list (cached on first call)."""
    global _birds
    if _birds is None:
        with open(_DATA_PATH) as f:
            _birds = json.load(f)
    return _birds


def get_birds_by_code() -> dict[str, dict]:
    """Return {species_code: bird} lookup (cached on first call)."""
    global _by_code
    if _by_code is None:
        _by_code = {b["species_code"]: b for b in get_birds()}
    return _by_code


def find_species(common_name: str = "", scientific_name: str = "") -> dict | None:
    """Look up a species by common or scientific name (exact match)."""
    global _by_name
    if _by_name is None:
        _by_name = {}
        for b in get_birds():
            _by_name[b["common_name"].lower()] = b
            _by_name[b["scientific_name"].lower()] = b
    return _by_name.get(common_name.lower()) or _by_name.get(scientific_name.lower())
