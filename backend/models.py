"""
models.py — ORM tables for the web layer.

These live alongside your existing SQLite tables (the `auth` module's
users/sessions). For the web app we keep a clean, web-native schema:
accounts, refresh sessions, and a full command-history audit log (handy
for a "recent commands" panel and for analytics on which of your 1948
commands actually get used).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)
    last_login: Mapped[dt.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True)

    history: Mapped[list["CommandHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class CommandHistory(Base):
    __tablename__ = "command_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"), index=True)
    command: Mapped[str] = mapped_column(String(512))
    module: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="history")


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(
        "users.id", ondelete="CASCADE"), index=True)
    token_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow)
