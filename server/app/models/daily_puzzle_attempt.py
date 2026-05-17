from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class DailyPuzzleAttempt(Base):
    __tablename__ = "daily_puzzle_attempts"
    __table_args__ = (UniqueConstraint("profile_id", "puzzle_date", name="uq_profile_puzzle_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(32), ForeignKey("player_profiles.profile_id"), nullable=False, index=True)
    puzzle_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    solved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    solved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)