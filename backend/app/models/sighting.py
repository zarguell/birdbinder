import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Sighting(Base):
    __tablename__ = "sightings"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_identifier: Mapped[str] = mapped_column(String(255), index=True)
    photo_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    exif_datetime: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exif_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    exif_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    exif_camera_model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_display_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    manual_species_override: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", index=True
    )
    species_code: Mapped[str | None] = mapped_column(String(6), nullable=True, index=True)
    species_common: Mapped[str | None] = mapped_column(String(255), nullable=True)
    species_scientific: Mapped[str | None] = mapped_column(String(255), nullable=True)
    family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pose_variant: Mapped[str | None] = mapped_column(String(20), nullable=True, default="other")
    id_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    id_method: Mapped[str | None] = mapped_column(String(20), nullable=True, default="manual")

    cards: Mapped[list["Card"]] = relationship(  # noqa: F821
        "Card", back_populates="sighting", lazy="selectin",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["Job"]] = relationship(  # noqa: F821
        "Job", back_populates="sighting", lazy="selectin",
        cascade="all, delete-orphan",
    )
