from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PlayerProfile(Base):
    __tablename__ = "player_profiles"

    profile_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    nickname: Mapped[str] = mapped_column(String(100), nullable=False, default="Guest")
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    games: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pvp_games: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ai_games: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    elo_rating: Mapped[int] = mapped_column(Integer, nullable=False, default=1200)
    ranked_games: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ranked_wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ranked_losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ranked_placement_remaining: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    last_ranked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_decay_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    season_key: Mapped[str] = mapped_column(String(20), nullable=False, default="2026-S1")
    pro_active: Mapped[bool] = mapped_column(nullable=False, default=False)
    pro_plan: Mapped[str | None] = mapped_column(String(30), nullable=True)
    pro_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    owned_board_skins: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    owned_piece_skins: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    equipped_board_skin: Mapped[str] = mapped_column(String(30), nullable=False, default="classic")
    equipped_piece_skin: Mapped[str] = mapped_column(String(30), nullable=False, default="marble")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)