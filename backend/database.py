"""
database.py — Async SQLAlchemy engine + session factory.

Defaults to SQLite (matches your current app, zero setup) but flip a single
env var (DATABASE_URL) to point at Postgres for production. Nothing else
changes.

    SQLite (dev):   sqlite+aiosqlite:///./termaid_web.db
    Postgres (prod): postgresql+asyncpg://user:pass@localhost/termaid
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .settings import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields a session, always closes it."""
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create tables on startup (use Alembic for real migrations later)."""
    from . import models  # noqa: F401  ensure models are imported/registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
