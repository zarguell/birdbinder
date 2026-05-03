from pydantic import BaseModel
from datetime import datetime


class BinderCardRead(BaseModel):
    id: str
    card_id: str
    position: int
    model_config = {"from_attributes": True}


class BinderCreate(BaseModel):
    name: str
    description: str | None = None
    cover_card_id: str | None = None


class BinderUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_card_id: str | None = None


class BinderRead(BaseModel):
    id: str
    user_identifier: str
    name: str
    description: str | None
    cover_card_id: str | None
    card_count: int = 0
    created_at: datetime | None
    updated_at: datetime | None
    cards: list[BinderCardRead] = []
    model_config = {"from_attributes": True}


class BinderList(BaseModel):
    items: list[BinderRead]
    total: int
    limit: int
    offset: int


class AddCardToBinder(BaseModel):
    card_id: str
    position: int | None = None
