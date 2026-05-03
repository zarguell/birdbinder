from __future__ import annotations

from collections import defaultdict
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.dependencies import get_current_user
from app.models.card import Card
from app.models.user import User
from app.services.region_service import (
    get_available_regions,
    get_region_codes,
    get_region_species,
)

router = APIRouter()


@router.get("/regions")
async def list_regions(user: str = Depends(get_current_user)):
    """Return all available regions."""
    return get_available_regions()


@router.get("/regions/{region_id}/species")
async def list_region_species(
    region_id: str,
    user: str = Depends(get_current_user),
):
    """Return species list for a given region."""
    try:
        species = get_region_species(region_id)
    except ValueError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=str(e))
    return species


@router.get("/collection/progress")
async def get_collection_progress(
    family_group: bool = Query(default=False),
    user: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return collection progress for the authenticated user."""
    # 1. Get user's region (default "us")
    db_result = await db.execute(select(User).where(User.email == user))
    user_obj = db_result.scalar_one_or_none()
    region = user_obj.region if user_obj and user_obj.region else "us"

    # 2. Get region codes and species metadata
    region_codes = get_region_codes(region)
    all_species = get_region_species(region)

    # 3. Query distinct species codes the user has cards for in this region
    stmt = (
        select(Card.species_code)
        .where(
            Card.user_identifier == user,
            Card.species_code.in_(region_codes),
        )
        .distinct()
    )
    rows = (await db.execute(stmt)).scalars().all()
    discovered_codes = set(rows)

    # 4. Build discovered / missing lists using species metadata
    discovered = []
    missing = []
    for s in all_species:
        entry = {
            "species_code": s["code"],
            "common_name": s["common_name"],
            "scientific_name": s["scientific_name"],
            "family": s["family"],
            "taxon_order": s["taxon_order"],
        }
        if s["code"] in discovered_codes:
            discovered.append(entry)
        else:
            missing.append(entry)

    total_species = len(all_species)
    discovered_count = len(discovered)
    progress_percent = round((discovered_count / total_species) * 100, 1) if total_species else 0

    result: dict = {
        "region": region,
        "total_species": total_species,
        "discovered_count": discovered_count,
        "progress_percent": progress_percent,
        "discovered": discovered,
        "missing": missing,
    }

    # 5. Optionally group by family
    if family_group:
        family_map: dict[str, list[dict]] = defaultdict(list)
        for s in all_species:
            found = s["code"] in discovered_codes
            family_map[s["family"]].append({
                "species_code": s["code"],
                "common_name": s["common_name"],
                "scientific_name": s["scientific_name"],
                "found": found,
            })
        family_groups = []
        for family, species in family_map.items():
            family_groups.append({
                "family": family,
                "total": len(species),
                "discovered": sum(1 for sp in species if sp["found"]),
                "species": species,
            })
        family_groups.sort(key=lambda g: g["family"])
        result["family_groups"] = family_groups

    return result
