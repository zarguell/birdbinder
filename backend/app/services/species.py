import json
from pathlib import Path

# Load at module level
_BIRDS_DATA: list[dict] | None = None
_BIRDS_BY_CODE: dict[str, dict] | None = None


def _load_data():
    global _BIRDS_DATA, _BIRDS_BY_CODE
    if _BIRDS_DATA is None:
        data_path = Path(__file__).parent.parent / "data" / "birds.json"
        with open(data_path) as f:
            _BIRDS_DATA = json.load(f)
        _BIRDS_BY_CODE = {b["species_code"]: b for b in _BIRDS_DATA}


def search_species(
    query: str, limit: int = 20, offset: int = 0, family: str | None = None
) -> tuple[list[dict], int]:
    """Case-insensitive search on common and scientific names, with optional family filter."""
    _load_data()
    q = query.lower()
    matches = [
        b
        for b in _BIRDS_DATA
        if q in b["common_name"].lower() or q in b["scientific_name"].lower()
    ]
    if family:
        matches = [b for b in matches if b.get("family") == family]
    # Sort by taxon_order for consistent results
    matches.sort(key=lambda b: b.get("taxon_order", 99999))
    total = len(matches)
    return matches[offset : offset + limit], total


def list_families() -> list[dict]:
    """Return all unique families with species count."""
    _load_data()
    family_counts: dict[str, dict] = {}
    for b in _BIRDS_DATA:
        fam = b.get("family", "Unknown")
        if fam not in family_counts:
            family_counts[fam] = {
                "name": fam,
                "code": b.get("family_code", ""),
                "species_count": 0,
            }
        family_counts[fam]["species_count"] += 1
    return sorted(family_counts.values(), key=lambda x: x["name"])


def get_species_by_code(code: str) -> dict | None:
    """Get species by 6-letter eBird code."""
    _load_data()
    return _BIRDS_BY_CODE.get(code.lower())
