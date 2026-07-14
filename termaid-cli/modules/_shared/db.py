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
