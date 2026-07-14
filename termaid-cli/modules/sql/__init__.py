"""SQL Module — Read-only ad-hoc queries against a local SQLite database.

Safety is enforced at two independent layers, not just a string check:
1. The connection is opened via `file:<path>?mode=ro` URI — SQLite refuses
   any write at the OS file-handle level, so even a crafted multi-statement
   or PRAGMA-based bypass attempt can't write.
2. `PRAGMA query_only = ON` is set on top of that as a second guard.
A lightweight prefix check also rejects obviously-non-SELECT statements
early with a clear error, but the two guards above are what actually make
this safe — not the string check.

Commands (~2):
  /sql query <db_path> <SELECT ...>     Run a read-only query, first 50 rows
  /sql explain                            How this module works
"""

import sqlite3
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_ALLOWED_PREFIXES = ("select", "with", "explain", "pragma table_info", "pragma database_list")
_MAX_ROWS = 50


class SqlModule(Module):
    name = "sql"
    version = "1.0.0"
    description = "Read-only ad-hoc queries against a local SQLite database"
    author = "termaid"

    def on_load(self):
        for cmd in ["query", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_query(self, arg=""):
        """Run a read-only query, first 50 rows: /sql query <db_path> <SELECT ...>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[sql] Usage: /sql query <db_path> <SELECT ...>"
        db_path, query = parts[0], parts[1].strip()
        p = Path(db_path).expanduser()
        if not p.is_file():
            return f"[sql] Not found: {p}"

        normalized = query.strip().lower()
        if not any(normalized.startswith(pfx) for pfx in _ALLOWED_PREFIXES):
            return "[sql] Only SELECT / WITH / EXPLAIN / PRAGMA table_info queries are allowed."
        if ";" in query.rstrip(";"):
            return "[sql] Only a single statement is allowed (no ';' except a trailing one)."

        try:
            uri = f"file:{p.as_posix()}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=5)
            conn.execute("PRAGMA query_only = ON")
        except Exception as e:
            return f"[sql] Could not open {p}: {e}"

        try:
            cur = conn.execute(query)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(_MAX_ROWS)
        except Exception as e:
            return f"[sql] Query failed: {e}"
        finally:
            conn.close()

        if not rows:
            return "[sql] Query returned no rows."
        lines = ["[sql] " + " | ".join(cols)]
        for row in rows:
            lines.append(" | ".join(str(v) for v in row))
        if len(rows) == _MAX_ROWS:
            lines.append(f"... (capped at {_MAX_ROWS} rows)")
        return "\n".join(lines)

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
