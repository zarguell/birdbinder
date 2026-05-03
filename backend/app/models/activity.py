import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_identifier: Mapped[str] = mapped_column(String(255), index=True)
    activity_type: Mapped[str] = mapped_column(String(20), index=True)  # sighting, card, set_completion
    reference_id: Mapped[str] = mapped_column(String(36), index=True)  # sighting/card/set UUID
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    likes: Mapped[list["Like"]] = relationship(
        "Like", back_populates="activity", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="activity", cascade="all, delete-orphan",
        order_by="Comment.created_at",
    )
