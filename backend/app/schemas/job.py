from datetime import datetime

from pydantic import BaseModel


class JobRead(BaseModel):
    id: str
    type: str
    sighting_id: str | None
    status: str
    result: dict | None
    error: str | None
    created_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
