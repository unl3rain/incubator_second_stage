from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ProfileMute(Base):
    __tablename__ = "profile_mutes"

    mute_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    muted_profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
