from __future__ import annotations

from pydantic import BaseModel
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.sighting import SightingRead


class CardRead(BaseModel):
    id: str
    sighting_id: str | None
    user_identifier: str
    species_common: str
    species_scientific: str | None
    species_code: str
    family: str | None
    pose_variant: str
    rarity_tier: str
    set_ids: list
    card_number: int | None
    card_art_url: str | None
    id_method: str
    id_confidence: float | None
    duplicate_count: int
    tradeable: bool
    generated_at: datetime | None
    sighting: SightingRead | None = None

    model_config = {"from_attributes": True}


class CardList(BaseModel):
    items: list[CardRead]
    total: int
    limit: int
    offset: int
