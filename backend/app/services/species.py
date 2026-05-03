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
    query: str, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """Case-insensitive search on common and scientific names."""
    _load_data()
    q = query.lower()
    matches = [
        b
        for b in _BIRDS_DATA
        if q in b["common_name"].lower() or q in b["scientific_name"].lower()
    ]
    total = len(matches)
    return matches[offset : offset + limit], total


def get_species_by_code(code: str) -> dict | None:
    """Get species by 6-letter eBird code."""
    _load_data()
    return _BIRDS_BY_CODE.get(code.lower())
