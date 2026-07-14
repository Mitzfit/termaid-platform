"""Quick Module — Favorites system for frequently-used commands.

Simpler than /aliases: no renaming, just a starred list you add to and pull
from, in most-recently-added order.

Commands (9):
  /quick add <command>       Star a command string
  /quick remove <n>           Remove by list position
  /quick list                 Show starred commands
  /quick top [n]               Show the n most recent (default 5)
  /quick clear                 Remove all (confirms)
  /quick export                Export to JSON
  /quick import <path>         Import from JSON
  /quick count                 How many starred
  /quick explain                How this module works
"""

import json
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class QuickModule(Module):
    name = "quick"
    version = "1.0.0"
    description = "Favorites system for frequently-used commands"
    author = "termaid"

    def on_load(self):
        for cmd in ["add", "remove", "list", "top", "clear",
                    "export", "import", "count", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "quick"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "favorites.json"

    def _load(self) -> list:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                pass
        return []

    def _save(self, items: list) -> None:
        self._file.write_text(json.dumps(items, indent=2))

    @safe
    def cmd_add(self, arg=""):
        """Star a command string"""
        command = (arg or "").strip()
        if not command:
            return "[quick] Usage: /quick add <command>"
        items = self._load()
        items.append({"command": command, "added": time.strftime("%Y-%m-%d %H:%M:%S")})
        self._save(items)
        return f"[quick] Starred: {command}"

    @safe
    def cmd_remove(self, arg=""):
        """Remove by list position (1-based, see /quick list)"""
        try:
            idx = int((arg or "").strip())
        except Exception:
            return "[quick] Usage: /quick remove <position>"
        items = self._load()
        if not (1 <= idx <= len(items)):
            return f"[quick] No item at position {idx}. Use /quick list to see positions."
        removed = items.pop(idx - 1)
        self._save(items)
        return f"[quick] Removed: {removed['command']}"

    @safe
    def cmd_list(self, arg=""):
        """Show starred commands"""
        items = self._load()
        if not items:
            return "[quick] No starred commands yet. /quick add <command>"
        lines = [f"[quick] {len(items)} starred command(s):"]
        for i, item in enumerate(items, 1):
            lines.append(f"  {i}. {item['command']}  ({item.get('added', '?')})")
        return "\n".join(lines)

    @safe
    def cmd_top(self, arg=""):
        """Show the n most recent (default 5)"""
        try:
            n = int((arg or "5").strip())
        except Exception:
            n = 5
        items = self._load()[-n:]
        if not items:
            return "[quick] No starred commands yet."
        lines = [f"[quick] {len(items)} most recent:"]
        for item in reversed(items):
            lines.append(f"  {item['command']}")
        return "\n".join(lines)

    @safe
    def cmd_clear(self, arg=""):
        """Remove all (confirms)"""
        if (arg or "").strip().lower() != "confirm":
            return "[quick] This removes ALL starred commands. Re-run as: /quick clear confirm"
        n = len(self._load())
        self._save([])
        return f"[quick] Cleared {n} item(s)."

    @safe
    def cmd_export(self, arg=""):
        """Export to JSON"""
        path = (arg or "").strip() or str(self._dir / f"quick-{int(time.time())}.json")
        Path(path).expanduser().write_text(json.dumps(self._load(), indent=2))
        return f"[quick] Exported to {path}"

    @safe
    def cmd_import(self, arg=""):
        """Import from JSON"""
        path = (arg or "").strip()
        if not path:
            return "[quick] Usage: /quick import <path>"
        try:
            incoming = json.loads(Path(path).expanduser().read_text())
        except Exception as e:
            return f"[quick] Cannot read: {e}"
        if not isinstance(incoming, list):
            return "[quick] File must contain a JSON list of {command, added} entries"
        items = self._load()
        items.extend(incoming)
        self._save(items)
        return f"[quick] Imported {len(incoming)} item(s)"

    @safe
    def cmd_count(self, arg=""):
        """How many starred"""
        return f"[quick] {len(self._load())} command(s) starred"

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
