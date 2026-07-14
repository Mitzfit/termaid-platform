"""Config Module — Persistent app-level key/value configuration store.

Distinct from /env (which reads the OS process environment): this is
TermAId's own settings store, for values other modules or the frontend
might want to persist across restarts (e.g. default output format,
preferred units, feature toggles). Plain JSON on disk, no encryption —
don't store secrets here (see /apikeys once built for that).

Commands (~6):
  /config get <key>              Show one value
  /config set <key> <value>        Set a value (creates if missing)
  /config unset <key>                Remove a key
  /config list                         Show all key/value pairs
  /config reset                          Clear the entire store (confirms)
  /config explain                          How this module works
"""

import json
import os
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class ConfigModule(Module):
    name = "config"
    version = "1.0.0"
    description = "Persistent app-level key/value configuration store"
    author = "termaid"

    def on_load(self):
        for cmd in ["get", "set", "unset", "list", "reset", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "config.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    @safe
    def cmd_get(self, arg=""):
        """Show one value: /config get <key>"""
        key = (arg or "").strip()
        if not key:
            return "[config] Usage: /config get <key>"
        if key not in self._data:
            return f"[config] '{key}' is not set"
        return f"[config] {key} = {self._data[key]!r}"

    @safe
    def cmd_set(self, arg=""):
        """Set a value: /config set <key> <value>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[config] Usage: /config set <key> <value>"
        key, value = parts[0], parts[1]
        self._data[key] = value
        self._save()
        return f"[config] {key} = {value!r}"

    @safe
    def cmd_unset(self, arg=""):
        """Remove a key: /config unset <key>"""
        key = (arg or "").strip()
        if not key:
            return "[config] Usage: /config unset <key>"
        if key not in self._data:
            return f"[config] '{key}' is not set"
        del self._data[key]
        self._save()
        return f"[config] Removed '{key}'"

    @safe
    def cmd_list(self, arg=""):
        """Show all key/value pairs"""
        if not self._data:
            return "[config] No settings yet. /config set <key> <value>"
        lines = [f"[config] {len(self._data)} setting(s):"]
        for k, v in sorted(self._data.items()):
            lines.append(f"  {k:20s} = {v!r}")
        return "\n".join(lines)

    @safe
    def cmd_reset(self, arg=""):
        """Clear the entire store (confirms — this is permanent)"""
        if (arg or "").strip().lower() != "confirm":
            return "[config] This clears ALL settings. Re-run as: /config reset confirm"
        n = len(self._data)
        self._data = {}
        self._save()
        return f"[config] Cleared {n} setting(s)"

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
