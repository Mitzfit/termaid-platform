"""Repo Module — Multi-repo git status registry.

Distinct from /git (which operates on one "active repo" at a time and can
mutate it — commit, push, reset): this only tracks a name -> path mapping
of repos you care about and reports read-only status (branch, dirty
count) across all of them in one view. Never runs a mutating git command.

Commands (~4):
  /repo add <name> <path>      Register a repo
  /repo list                     Show status across every registered repo
  /repo remove <name> confirm      Unregister a repo
  /repo explain                      How this module works
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class RepoModule(Module):
    name = "repo"
    version = "1.0.0"
    description = "Multi-repo git status registry"
    author = "termaid"

    def on_load(self):
        for cmd in ["add", "list", "remove", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "repos.json"
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

    def _status(self, path: str):
        try:
            r = subprocess.run(["git", "-C", path, "status", "--short", "--branch"],
                                capture_output=True, text=True, timeout=10,
                                encoding="utf-8", errors="replace")
            if r.returncode != 0:
                return None
            lines = r.stdout.splitlines()
            branch = lines[0].replace("## ", "") if lines else "?"
            dirty = len(lines) - 1
            return {"branch": branch, "dirty": dirty}
        except Exception:
            return None

    @safe
    def cmd_add(self, arg=""):
        """Register a repo: /repo add <name> <path>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[repo] Usage: /repo add <name> <path>"
        name, path = parts[0], parts[1].strip()
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            return f"[repo] Not a directory: {p}"
        self._data[name] = str(p)
        self._save()
        return f"[repo] Registered '{name}' -> {p}"

    @safe
    def cmd_list(self, arg=""):
        """Show status across every registered repo"""
        if not self._data:
            return "[repo] No repos registered yet. /repo add <name> <path>"
        lines = [f"[repo] {len(self._data)} repo(s):"]
        for name, path in sorted(self._data.items()):
            status = self._status(path)
            if status is None:
                lines.append(f"  {name:15s} {path}  (not a git repo, or git unavailable)")
            else:
                clean = "clean" if status["dirty"] == 0 else f"{status['dirty']} change(s)"
                lines.append(f"  {name:15s} {status['branch']:20s} {clean:15s} {path}")
        return "\n".join(lines)

    @safe
    def cmd_remove(self, arg=""):
        """Unregister a repo (confirms): /repo remove <name> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            name = parts[0] if parts else "<name>"
            return f"[repo] Re-run as: /repo remove {name} confirm"
        name = parts[0]
        if name not in self._data:
            return f"[repo] No repo named '{name}'"
        del self._data[name]
        self._save()
        return f"[repo] Removed '{name}'"

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
