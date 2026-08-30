from pydantic import BaseModel

from app.types import PaginatedList


class SpeciesRead(BaseModel):
    species_code: str
    common_name: str
    scientific_name: str
    family: str | None = None
    family_code: str | None = None
    taxon_order: int | None = None
    order: str | None = None


SpeciesSearchResult = PaginatedList[SpeciesRead]
