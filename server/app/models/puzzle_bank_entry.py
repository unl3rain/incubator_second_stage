from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class PuzzleBankEntry(Base):
    __tablename__ = "puzzle_bank_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    hint: Mapped[str] = mapped_column(String(300), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False, default="easy")
    source: Mapped[str] = mapped_column(String(100), nullable=False, default="internal-generated")
    source_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    attribution: Mapped[str | None] = mapped_column(String(300), nullable=True)
    board: Mapped[list[list[dict | None]]] = mapped_column(JSON, nullable=False)
    turn: Mapped[str] = mapped_column(String(10), nullable=False)
    solution: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)