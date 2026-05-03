from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_current_user
from app.schemas.species import SpeciesRead, SpeciesSearchResult
from app.services.species import search_species, get_species_by_code, list_families

router = APIRouter()


@router.get("/species/search", response_model=SpeciesSearchResult)
async def search(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    family: str | None = Query(default=None),
    user: str = Depends(get_current_user),
):
    items, total = search_species(q, limit=limit, offset=offset, family=family)
    return SpeciesSearchResult(items=items, total=total, limit=limit, offset=offset)


@router.get("/species/families")
async def get_families(user: str = Depends(get_current_user)):
    return list_families()


@router.get("/species/{code}", response_model=SpeciesRead)
async def get_species(
    code: str,
    user: str = Depends(get_current_user),
):
    species = get_species_by_code(code)
    if species is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Species not found"
        )
    return species
