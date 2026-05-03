from pydantic import BaseModel


class IdentificationResult(BaseModel):
    common_name: str
    scientific_name: str
    family: str | None
    confidence: float
    distinguishing_traits: list[str]
    pose_variant: str


class IdentificationRequest(BaseModel):
    sighting_id: str
