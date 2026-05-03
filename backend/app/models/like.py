import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Like(Base):
    __tablename__ = "activity_likes"
    __table_args__ = (
        UniqueConstraint("activity_id", "user_identifier", name="uq_activity_user_like"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    activity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    user_identifier: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    activity: Mapped["Activity"] = relationship("Activity", back_populates="likes")
