from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserAchievement(Base):
    __tablename__ = "user_achievements"

    achievement_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False)
    badge_type: Mapped[str] = mapped_column(String(50), nullable=False)  # streak, accuracy, rank, promotion
    badge_name: Mapped[str] = mapped_column(String(100), nullable=False)
    badge_icon: Mapped[str] = mapped_column(String(50), nullable=False)  # emoji or icon name
    description: Mapped[str] = mapped_column(String(200), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # bronze, silver, gold, platinum
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    displayed: Mapped[bool] = mapped_column(nullable=False, default=True)
