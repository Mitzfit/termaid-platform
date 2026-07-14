"""DBKeys Module — Read-only SQLite structure browser.

Opens every database strictly read-only (`file:<path>?mode=ro` URI, plus
`PRAGMA query_only = ON` as a second, independent guard) — the OS-level
read-only file handle means even a crafted query cannot write, regardless
of what SQL is sent. Only inspects structure (tables, columns, row
counts); see /sql for running actual SELECT queries against the data.

Commands (~3):
  /dbkeys tables <db_path>            List tables + row counts
  /dbkeys schema <db_path> <table>       Show a table's columns
  /dbkeys explain                            How this module works
"""

import sqlite3
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _connect_ro(path: Path):
    uri = f"file:{path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.execute("PRAGMA query_only = ON")
    return conn


class DBKeysModule(Module):
    name = "dbkeys"
    version = "1.0.0"
    description = "Read-only SQLite structure browser"
    author = "termaid"

    def on_load(self):
        for cmd in ["tables", "schema", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_tables(self, arg=""):
        """List tables + row counts: /dbkeys tables <db_path>"""
        db_path = (arg or "").strip()
        if not db_path:
            return "[dbkeys] Usage: /dbkeys tables <db_path>"
        p = Path(db_path).expanduser()
        if not p.is_file():
            return f"[dbkeys] Not found: {p}"
        try:
            conn = _connect_ro(p)
        except Exception as e:
            return f"[dbkeys] Could not open {p}: {e}"
        try:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cur.fetchall()]
            if not tables:
                return f"[dbkeys] {p}: no tables found."
            lines = [f"[dbkeys] {p} — {len(tables)} table(s):"]
            for t in tables:
                try:
                    count = conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                except Exception:
                    count = "?"
                lines.append(f"  {t:25s} {count} row(s)")
            return "\n".join(lines)
        finally:
            conn.close()

    @safe
    def cmd_schema(self, arg=""):
        """Show a table's columns: /dbkeys schema <db_path> <table>"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[dbkeys] Usage: /dbkeys schema <db_path> <table>"
        db_path, table = parts[0], parts[1]
        p = Path(db_path).expanduser()
        if not p.is_file():
            return f"[dbkeys] Not found: {p}"
        try:
            conn = _connect_ro(p)
        except Exception as e:
            return f"[dbkeys] Could not open {p}: {e}"
        try:
            cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            if cur.fetchone() is None:
                return f"[dbkeys] No table named '{table}' in {p}"
            cols = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
            lines = [f"[dbkeys] {table}:"]
            for cid, name, coltype, notnull, default, pk in cols:
                flags = []
                if pk:
                    flags.append("PK")
                if notnull:
                    flags.append("NOT NULL")
                flag_s = f"  ({', '.join(flags)})" if flags else ""
                lines.append(f"  {name:20s} {coltype or '?':10s}{flag_s}")
            return "\n".join(lines)
        finally:
            conn.close()

    @safe
    def cmd_explain(self, arg=""):
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{self.name}] {self.description}", "", "Commands:"]
            for c in cmds:
                lines.append(f"  /{self.name} {c}")
            return "\n".join(lines)
