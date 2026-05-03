from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.services.region_service import get_available_regions, get_region_species

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
