from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Friendship(Base):
    __tablename__ = "friendships"

    friendship_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    requester_profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    addressee_profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending, accepted
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
