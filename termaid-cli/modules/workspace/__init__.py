"""Workspace Module — Named project path registry.

Tracks a name -> path mapping so you can refer to projects by a short name
instead of typing full paths repeatedly, and mirrors /git's "active repo"
pattern: /workspace use sets the active workspace, which other module
usage can be pointed at manually (this module doesn't chdir the process —
that's shared global state across every connected user, same reasoning
as /git repo).

Commands (~6):
  /workspace add <name> <path>       Register a workspace
  /workspace list                      Show all registered workspaces
  /workspace use <name>                  Set the active workspace
  /workspace current                       Show the active workspace
  /workspace remove <name> confirm           Unregister a workspace
  /workspace explain                           How this module works
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


class WorkspaceModule(Module):
    name = "workspace"
    version = "1.0.0"
    description = "Named project path registry"
    author = "termaid"

    def on_load(self):
        for cmd in ["add", "list", "use", "current", "remove", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "workspaces.json"
        self._data = self._load()
        self._active = self._data.get("_active")

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        out = dict(self._data)
        out["_active"] = self._active
        self._path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    def _workspaces(self) -> dict:
        return {k: v for k, v in self._data.items() if k != "_active"}

    @safe
    def cmd_add(self, arg=""):
        """Register a workspace: /workspace add <name> <path>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[workspace] Usage: /workspace add <name> <path>"
        name, path = parts[0], parts[1].strip()
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            return f"[workspace] Not a directory: {p}"
        self._data[name] = str(p)
        self._save()
        return f"[workspace] Registered '{name}' -> {p}"

    @safe
    def cmd_list(self, arg=""):
        """Show all registered workspaces"""
        ws = self._workspaces()
        if not ws:
            return "[workspace] No workspaces yet. /workspace add <name> <path>"
        lines = [f"[workspace] {len(ws)} workspace(s):"]
        for n, p in sorted(ws.items()):
            marker = " *" if n == self._active else "  "
            lines.append(f"{marker}{n:20s} {p}")
        return "\n".join(lines)

    @safe
    def cmd_use(self, arg=""):
        """Set the active workspace: /workspace use <name>"""
        name = (arg or "").strip()
        if not name:
            return "[workspace] Usage: /workspace use <name>"
        if name not in self._workspaces():
            return f"[workspace] No workspace named '{name}'. See /workspace list"
        self._active = name
        self._save()
        return f"[workspace] Active workspace: {name} ({self._data[name]})"

    @safe
    def cmd_current(self, arg=""):
        """Show the active workspace"""
        if not self._active or self._active not in self._workspaces():
            return "[workspace] No active workspace. /workspace use <name>"
        return f"[workspace] Active: {self._active} ({self._data[self._active]})"

    @safe
    def cmd_remove(self, arg=""):
        """Unregister a workspace (confirms): /workspace remove <name> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            name = parts[0] if parts else "<name>"
            return f"[workspace] This only unregisters the name, not the directory. Re-run as: /workspace remove {name} confirm"
        name = parts[0]
        if name not in self._workspaces():
            return f"[workspace] No workspace named '{name}'"
        del self._data[name]
        if self._active == name:
            self._active = None
        self._save()
        return f"[workspace] Removed '{name}'"

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
