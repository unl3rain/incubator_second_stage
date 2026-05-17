from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ChatReport(Base):
    __tablename__ = "chat_reports"

    report_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reporter_profile_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
