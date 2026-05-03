from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class SpeciesCache(Base):
    __tablename__ = "species_cache"

    species_code: Mapped[str] = mapped_column(String(6), primary_key=True)
    common_name: Mapped[str] = mapped_column(String(255), index=True)
    scientific_name: Mapped[str] = mapped_column(String(255))
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    taxon_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    family: Mapped[str | None] = mapped_column(String(255), nullable=True)
    family_common: Mapped[str | None] = mapped_column(String(255), nullable=True)
