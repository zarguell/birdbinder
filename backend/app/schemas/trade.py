from pydantic import BaseModel
from datetime import datetime

from app.types import PaginatedList


class TradeCreate(BaseModel):
    offered_to: str  # recipient user identifier
    offered_card_ids: list[str]
    requested_card_ids: list[str]


class TradeCardInfo(BaseModel):
    """Minimal card summary so trade UIs can show species names, not UUIDs."""

    id: str
    species_common: str
    species_code: str
    rarity_tier: str | None = None
    card_art_url: str | None = None

    model_config = {"from_attributes": True}


class TradeRead(BaseModel):
    id: str
    offered_by: str
    offered_to: str
    offered_card_ids: list
    requested_card_ids: list
    offered_cards: list[TradeCardInfo] = []
    requested_cards: list[TradeCardInfo] = []
    status: str
    created_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


TradeList = PaginatedList[TradeRead]
