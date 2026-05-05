import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import JobType, JobStatus


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    type: Mapped[str] = mapped_column(
        String(20), index=True
    )
    sighting_id: Mapped[uuid.UUID | None] = mapped_column(
        String(36), ForeignKey("sightings.id", ondelete="CASCADE"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default=JobStatus.pending.value, index=True
    )
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    raw_response: Mapped[str | None] = mapped_column(String(5000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    sighting: Mapped["Sighting | None"] = relationship(  # noqa: F821
        "Sighting", back_populates="jobs",
    )
