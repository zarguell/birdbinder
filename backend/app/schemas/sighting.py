from pydantic import BaseModel
from datetime import datetime


class SightingCreate(BaseModel):
    notes: str | None = None
    location_display_name: str | None = None


class SightingOverride(BaseModel):
    species_code: str | None = None
    pose_variant: str | None = None


class SightingRead(BaseModel):
    id: str
    user_identifier: str
    photo_path: str | None
    thumbnail_path: str | None
    submitted_at: datetime
    exif_datetime: datetime | None
    exif_lat: float | None
    exif_lon: float | None
    exif_camera_model: str | None
    location_display_name: str | None
    notes: str | None
    manual_species_override: bool
    status: str
    species_code: str | None = None
    species_common: str | None = None
    species_scientific: str | None = None
    family: str | None = None
    pose_variant: str | None = None
    id_confidence: float | None = None
    id_method: str | None = None

    model_config = {"from_attributes": True}


class SightingList(BaseModel):
    items: list[SightingRead]
    total: int
    limit: int
    offset: int
