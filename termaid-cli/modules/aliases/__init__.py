"""Aliases Module — User-defined command shortcuts.

Stores name -> full-command mappings for quick recall. This module does not
itself re-dispatch through the engine (a module has no handle back to the
command dispatcher), so /aliases run just shows you the stored command to
copy/run — actual expand-and-execute is a REPL/frontend-layer concern.

Commands (11):
  /aliases add <name> <command>      Define a shortcut
  /aliases remove <name>             Delete a shortcut
  /aliases list                      List all shortcuts
  /aliases show <name>               Show what a shortcut expands to
  /aliases rename <old> <new>        Rename a shortcut
  /aliases search <text>             Search names + expansions
  /aliases count                     How many defined
  /aliases clear                     Remove all (confirms)
  /aliases export                    Export to JSON
  /aliases import <path>             Import from JSON
  /aliases explain                   How this module works
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


class AliasesModule(Module):
    name = "aliases"
    version = "1.0.0"
    description = "User-defined command shortcuts"
    author = "termaid"

    def on_load(self):
        for cmd in ["add", "remove", "list", "show", "rename", "search",
                    "count", "clear", "export", "import", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "aliases"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "aliases.json"

    def _load(self) -> dict:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                pass
        return {}

    def _save(self, data: dict) -> None:
        self._file.write_text(json.dumps(data, indent=2))

    @safe
    def cmd_add(self, arg=""):
        """Define a shortcut: /aliases add <name> <command>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[aliases] Usage: /aliases add <name> <command>"
        name, command = parts
        data = self._load()
        existed = name in data
        data[name] = command
        self._save(data)
        return f"[aliases] {'Updated' if existed else 'Added'} '{name}' -> {command!r}"

    @safe
    def cmd_remove(self, arg=""):
        """Delete a shortcut"""
        name = (arg or "").strip()
        if not name:
            return "[aliases] Usage: /aliases remove <name>"
        data = self._load()
        if name not in data:
            return f"[aliases] No shortcut named '{name}'"
        del data[name]
        self._save(data)
        return f"[aliases] Removed '{name}'"

    @safe
    def cmd_list(self, arg=""):
        """List all shortcuts"""
        data = self._load()
        if not data:
            return "[aliases] No shortcuts yet. /aliases add <name> <command>"
        lines = [f"[aliases] {len(data)} shortcut(s):"]
        for name, command in sorted(data.items()):
            lines.append(f"  {name:<15s} -> {command}")
        return "\n".join(lines)

    @safe
    def cmd_show(self, arg=""):
        """Show what a shortcut expands to"""
        name = (arg or "").strip()
        if not name:
            return "[aliases] Usage: /aliases show <name>"
        data = self._load()
        if name not in data:
            return f"[aliases] No shortcut named '{name}'"
        return f"[aliases] {name} -> {data[name]}"

    @safe
    def cmd_rename(self, arg=""):
        """Rename a shortcut: /aliases rename <old> <new>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[aliases] Usage: /aliases rename <old> <new>"
        old, new = parts
        data = self._load()
        if old not in data:
            return f"[aliases] No shortcut named '{old}'"
        data[new] = data.pop(old)
        self._save(data)
        return f"[aliases] Renamed '{old}' -> '{new}'"

    @safe
    def cmd_search(self, arg=""):
        """Search names + expansions"""
        q = (arg or "").strip().lower()
        if not q:
            return "[aliases] Usage: /aliases search <text>"
        data = self._load()
        hits = {n: c for n, c in data.items() if q in n.lower() or q in c.lower()}
        if not hits:
            return f"[aliases] No matches for '{q}'"
        lines = [f"[aliases] {len(hits)} match(es):"]
        for name, command in sorted(hits.items()):
            lines.append(f"  {name:<15s} -> {command}")
        return "\n".join(lines)

    @safe
    def cmd_count(self, arg=""):
        """How many defined"""
        return f"[aliases] {len(self._load())} shortcut(s) defined"

    @safe
    def cmd_clear(self, arg=""):
        """Remove all (confirms)"""
        if (arg or "").strip().lower() != "confirm":
            return "[aliases] This removes ALL shortcuts. Re-run as: /aliases clear confirm"
        n = len(self._load())
        self._save({})
        return f"[aliases] Cleared {n} shortcut(s)."

    @safe
    def cmd_export(self, arg=""):
        """Export to JSON"""
        import time
        path = (arg or "").strip() or str(self._dir / f"aliases-{int(time.time())}.json")
        Path(path).expanduser().write_text(json.dumps(self._load(), indent=2))
        return f"[aliases] Exported to {path}"

    @safe
    def cmd_import(self, arg=""):
        """Import from JSON"""
        path = (arg or "").strip()
        if not path:
            return "[aliases] Usage: /aliases import <path>"
        try:
            incoming = json.loads(Path(path).expanduser().read_text())
        except Exception as e:
            return f"[aliases] Cannot read: {e}"
        if not isinstance(incoming, dict):
            return "[aliases] File must contain a JSON object of name -> command"
        data = self._load()
        data.update(incoming)
        self._save(data)
        return f"[aliases] Imported {len(incoming)} shortcut(s)"

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
