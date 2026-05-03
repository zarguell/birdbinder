from pydantic import BaseModel


class SpeciesRead(BaseModel):
    species_code: str
    common_name: str
    scientific_name: str
    family: str | None = None
    family_code: str | None = None
    taxon_order: int | None = None
    order: str | None = None


class SpeciesSearchResult(BaseModel):
    items: list[SpeciesRead]
    total: int
    limit: int
    offset: int
