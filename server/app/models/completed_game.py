from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CompletedGame(Base):
    __tablename__ = "completed_games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="pvp")
    ranked: Mapped[bool] = mapped_column(nullable=False, default=False)
    season_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    winner: Mapped[str | None] = mapped_column(String(10), nullable=True)
    winner_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_elo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_color: Mapped[str | None] = mapped_column(String(10), nullable=True)
    time_control_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    white_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    white_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    red_nickname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    red_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    total_moves: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    move_history: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)