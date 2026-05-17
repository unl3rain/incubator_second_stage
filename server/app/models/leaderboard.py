from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CityStat(Base):
    __tablename__ = "city_stats"

    city: Mapped[str] = mapped_column(String(100), primary_key=True)
    wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    games: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
