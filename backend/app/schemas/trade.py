from pydantic import BaseModel
from datetime import datetime


class TradeCreate(BaseModel):
    offered_to: str  # recipient user identifier
    offered_card_ids: list[str]
    requested_card_ids: list[str]


class TradeRead(BaseModel):
    id: str
    offered_by: str
    offered_to: str
    offered_card_ids: list
    requested_card_ids: list
    status: str
    created_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class TradeList(BaseModel):
    items: list[TradeRead]
    total: int
    limit: int
    offset: int
