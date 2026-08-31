from app.services import taxonomy


def search_species(
    query: str, limit: int = 20, offset: int = 0, family: str | None = None
) -> tuple[list[dict], int]:
    """Case-insensitive search on common and scientific names, with optional family filter."""
    birds = taxonomy.get_birds()
    q = query.lower()
    matches = [
        b
        for b in birds
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
    family_counts: dict[str, dict] = {}
    for b in taxonomy.get_birds():
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
    return taxonomy.get_birds_by_code().get(code.lower())
