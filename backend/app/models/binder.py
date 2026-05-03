import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Binder(Base):
    __tablename__ = "binders"

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user_identifier: Mapped[str] = mapped_column(String(255), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    cover_card_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    cards: Mapped[list["BinderCard"]] = relationship(
        "BinderCard", back_populates="binder", cascade="all, delete-orphan", lazy="selectin"
    )


class BinderCard(Base):
    __tablename__ = "binder_cards"
    __table_args__ = (
        UniqueConstraint("binder_id", "card_id", name="uq_binder_card"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    binder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("binders.id", ondelete="CASCADE"), index=True
    )
    card_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("cards.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    binder: Mapped["Binder"] = relationship("Binder", back_populates="cards")
