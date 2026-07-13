# Agent 01 — Database & Data Structures (complete kit)

Attach this single file to the Database agent window (or add to project knowledge). It contains the brief, baseline, start prompt, and all owned source code.

---

# Agent 01 — Database & Data Structures

**Role:** Data engineer. **Owns the foundation every other window reads.**
**Baseline health:** 5.8 / 10 (set 2026-06-13).

## Owns
- `backend/models.py` — ORM tables (User, CommandHistory, RefreshSession)
- `backend/database.py` — async SQLAlchemy engine + session (SQLite↔Postgres)
- `backend/migrations/` — Alembic env, template, `0001_initial`
- `backend/alembic.ini`
- `modules/_shared/db.py` — the CLI's SQLite helper (shipped here as `_shared_db.py`)

## Depends on / feeds
- Feeds: Backend Core (schemas), AI, Knowledge (they read the schema).
- A schema change here ripples → flag under Cross-Window Impact every time.

## This agent's standing job (per WINDOW_DIRECTIVES)
Document → Break down → Harden → Health report, every session. Obey RULES.md.


---

# Health Report — Database  (BASELINE, v2.3.0, 2026-06-13)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 7 | Models clean; migration `0001` mirrors models. |
| Security | 7 | Passwords stored as hash; ORM (no raw SQL); token store present. |
| Performance | 7 | Indexes on username, user_id, created_at, token_id. |
| Architecture / maintainability | 7 | Clean async declarative SQLAlchemy. |
| Test coverage | 2 | No DB-specific tests; only indirect via CI test_api. |
| Documentation | 4 | File headers thin; no per-field/why docs yet. |
| Cross-window cohesion | 6 | Drives schemas.py + types.ts but unenforced. |
| **Overall** | **5.8** | Solid schema, under-documented and under-tested. |

## Top 3 risks
1. No DB-specific tests — schema regressions slip through.
2. Thin documentation — Directive 1 needed.
3. Schema changes ripple to backend/frontend with no guard.

## Highest-value next action
Directive 1 (document to CODE_STYLE, attributed to Misfit) + add model/migration
tests → target Documentation 4→8, Test coverage 2→6 this session.


---

## START PROMPT (paste into the new agent window)

```
This is the DATABASE & DATA STRUCTURES agent.

Your role: data engineer. You own the schema/ORM/migrations — the foundation
every other window reads. Work ONLY on your files; never touch another window's.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md, LESSONS.md, and this agent's BASELINE_HEALTH.md.

Then run the kickoff brainstorm (BRAINSTORM_TEMPLATE.md), then follow the four
directives in order: 1) Document every file (what/does/why, attributed to Misfit),
2) Break down (BREAKDOWN.md), 3) Harden, 4) Health report. End with a full
hand-back (HANDOFF_TEMPLATE.md) + updated files + INDEX.md + appended HISTORY.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```

---

## OWNED SOURCE CODE

### `backend/models.py`

```python
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

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def _utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    last_login: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    history: Mapped[list["CommandHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class CommandHistory(Base):
    __tablename__ = "command_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    command: Mapped[str] = mapped_column(String(512))
    module: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)

    user: Mapped["User"] = relationship(back_populates="history")


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

```

### `backend/database.py`

```python
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

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """FastAPI dependency: yields a session, always closes it."""
    async with SessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create tables on startup (use Alembic for real migrations later)."""
    from . import models  # noqa: F401  ensure models are imported/registered
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

```

### `backend/alembic.ini`

```ini
# Alembic config. Run from the backend/ directory:
#   alembic upgrade head           # apply migrations
#   alembic revision --autogenerate -m "add table"   # create a new one
[alembic]
script_location = migrations
prepend_sys_path = .
# DB URL is read dynamically from settings in migrations/env.py,
# so this is only a fallback and is intentionally left blank.
sqlalchemy.url =

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARNING
handlers = console
qualname =

[logger_sqlalchemy]
level = WARNING
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S

```

### `backend/migrations/env.py`

```python
"""Alembic environment — async, reads URL + metadata from the app."""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import pool

# Import app metadata + settings (prepend_sys_path=. makes 'backend' importable
# when alembic is run from the project root; adjust if your layout differs).
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.database import Base          # noqa: E402
from backend import models                 # noqa: E402,F401  (register tables)
from backend.settings import settings      # noqa: E402

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    return settings.database_url


def run_migrations_offline() -> None:
    context.configure(
        url=_url(), target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata,
                      compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(_url(), poolclass=pool.NullPool)
    async with engine.connect() as conn:
        await conn.run_sync(_do_run)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())

```

### `backend/migrations/script.py.mako`

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}

```

### `backend/migrations/versions/0001_initial.py`

```python
"""initial schema: users, command_history, refresh_sessions

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-12

This mirrors backend/models.py. After this lands, prefer
`alembic revision --autogenerate` for future schema changes instead of
the dev-only init_models() auto-create.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "command_history",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command", sa.String(512), nullable=False),
        sa.Column("module", sa.String(64), nullable=True),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("ok", sa.Boolean, server_default=sa.true()),
        sa.Column("duration_ms", sa.Float, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_history_user", "command_history", ["user_id"])
    op.create_index("ix_history_created", "command_history", ["created_at"])

    op.create_table(
        "refresh_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer,
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_id", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_refresh_token", "refresh_sessions", ["token_id"])


def downgrade() -> None:
    op.drop_table("refresh_sessions")
    op.drop_table("command_history")
    op.drop_table("users")

```

### `modules/_shared/db.py`

```python
"""SQLite helpers (v3.18+) — guaranteed-close connections.

Bare sqlite3.connect() patterns leak connections on exception. Python's
GC eventually closes them, but during the lifetime of an unclosed
connection: locks held, write-ahead logs unflushed, file descriptors
consumed. With many TermAId commands running in one session, this adds
up.

`sqlite_conn` is a context manager that ALWAYS closes the connection
(via finally), even on exception. Row factory and isolation level can
be overridden.

Usage:
    from _shared.db import sqlite_conn

    with sqlite_conn("data.db") as conn:
        rows = conn.execute("SELECT * FROM t").fetchall()
        # commit happens automatically if you used the context manager's transaction
    # connection closed here, even if an exception was raised

Or with explicit transaction:
    with sqlite_conn("data.db") as conn:
        with conn:  # transaction context: commits on success, rollbacks on error
            conn.execute("INSERT INTO t VALUES (?)", (x,))
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional, Sequence, Union

PathLike = Union[str, Path]


@contextmanager
def sqlite_conn(path: PathLike, row_factory: Optional[Any] = sqlite3.Row,
                timeout: float = 30.0, **connect_kwargs: Any
                ) -> Iterator[sqlite3.Connection]:
    """Open a SQLite connection that's guaranteed to close.

    path: filesystem path to the database
    row_factory: defaults to sqlite3.Row (dict-like access)
    timeout: how long to wait for a lock (seconds); SQLite default is 5
    **connect_kwargs: passed through to sqlite3.connect

    The connection is closed in a finally block — any exception raised
    inside the `with` body propagates AFTER the connection is closed.
    """
    conn = sqlite3.connect(str(path), timeout=timeout, **connect_kwargs)
    if row_factory is not None:
        conn.row_factory = row_factory
    try:
        yield conn
    finally:
        try:
            conn.close()
        except Exception:
            pass


def query_one(path: PathLike, sql: str,
              params: Sequence[Any] = ()) -> Optional[sqlite3.Row]:
    """One-shot query that returns the first row, then closes."""
    with sqlite_conn(path) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchone()


def query_all(path: PathLike, sql: str,
              params: Sequence[Any] = ()) -> list:
    """One-shot query that returns all rows, then closes."""
    with sqlite_conn(path) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def execute(path: PathLike, sql: str, params: Sequence[Any] = ()) -> int:
    """One-shot DML/DDL. Commits and closes. Returns rowcount."""
    with sqlite_conn(path) as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount

```


---
## HISTORY (append each session)

- 2026-06-13 · main · Kit created (baseline 5.8). Awaiting first session.
