import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import PoseVariant


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    sighting_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36), ForeignKey("sightings.id", ondelete="CASCADE"), nullable=True
    )
    user_identifier: Mapped[str] = mapped_column(String(255), index=True)
    species_common: Mapped[str] = mapped_column(String(255), index=True)
    species_scientific: Mapped[str | None] = mapped_column(String(255), nullable=True)
    species_code: Mapped[str] = mapped_column(String(6), index=True)
    family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pose_variant: Mapped[str] = mapped_column(
        String(20), default=PoseVariant.other.value
    )
    rarity_tier: Mapped[str] = mapped_column(String(20), default="common")
    set_ids: Mapped[list] = mapped_column(JSON, default=list)
    card_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    card_art_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    id_method: Mapped[str] = mapped_column(String(20), default="ai")
    id_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=1)
    tradeable: Mapped[bool] = mapped_column(Boolean, default=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    sighting: Mapped["Sighting | None"] = relationship(  # noqa: F821
        "Sighting", back_populates="cards", lazy="selectin"
    )
