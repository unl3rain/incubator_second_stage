from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class AuthUser(Base):
    __tablename__ = "auth_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, unique=True, index=True)
    social_provider: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    social_provider_user_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    social_display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    profile_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(256), nullable=True)
    password_salt: Mapped[str | None] = mapped_column(String(128), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    verification_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reset_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reset_code_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
