from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    message_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    game_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sender_profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sender_nickname: Mapped[str] = mapped_column(String(100), nullable=False)
    text: Mapped[str] = mapped_column(String(500), nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default="text")  # text, emoji
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
