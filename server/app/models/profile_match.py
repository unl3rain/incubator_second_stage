from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProfileMatch(Base):
    __tablename__ = "profile_matches"
    __table_args__ = (UniqueConstraint("profile_id", "completed_game_id", name="uq_profile_completed_game"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(String(32), ForeignKey("player_profiles.profile_id"), nullable=False, index=True)
    completed_game_id: Mapped[int] = mapped_column(Integer, ForeignKey("completed_games.id"), nullable=False, index=True)
    role_color: Mapped[str] = mapped_column(String(10), nullable=False)
    did_win: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)