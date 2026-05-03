from pydantic import BaseModel
from datetime import datetime, date


class CardSetCreate(BaseModel):
    name: str
    description: str | None = None
    region: str | None = None
    season: str | None = None
    release_date: date | None = None
    expiry_date: date | None = None
    rules: dict | None = None
    card_targets: list[str] | None = None  # list of species codes


class CardSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    region: str | None = None
    season: str | None = None
    release_date: date | None = None
    expiry_date: date | None = None
    rules: dict | None = None
    card_targets: list[str] | None = None


class CardSetRead(BaseModel):
    id: str
    creator_identifier: str
    name: str
    description: str | None
    region: str | None
    season: str | None
    release_date: date | None
    expiry_date: date | None
    rules: dict | None
    card_targets: list
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class CardSetList(BaseModel):
    items: list[CardSetRead]
    total: int
    limit: int
    offset: int


class SetProgress(BaseModel):
    set_id: str
    set_name: str
    total_targets: int
    collected: int
    missing: list[str]
    progress_percent: float
