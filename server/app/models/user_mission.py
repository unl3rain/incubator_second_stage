from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class UserMission(Base):
    __tablename__ = "user_missions"

    mission_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False)
    mission_type: Mapped[str] = mapped_column(String(50), nullable=False)  # daily, weekly, seasonal
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    target_value: Mapped[int] = mapped_column(Integer, nullable=False)
    current_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reward_xp: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    completed: Mapped[bool] = mapped_column(nullable=False, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    mission_metadata: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
