"""Tools Module — PATH executable indexer.

Scans every directory on PATH and indexes what's executable there —
useful for "is X on my PATH and where" or "what's a tool starting with
Y" without shelling out to `which`/`where` per-guess. Read-only.

Commands (~2):
  /tools search <pattern>       Find PATH executables matching a substring
  /tools paths                    List PATH directories + executable counts
  /tools explain                     How this module works
"""

import os
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_EXE_EXTS = {".exe", ".bat", ".cmd", ".com"} if sys.platform == "win32" else set()


def _is_executable(p: Path) -> bool:
    if sys.platform == "win32":
        return p.suffix.lower() in _EXE_EXTS
    return os.access(p, os.X_OK)


class ToolsModule(Module):
    name = "tools"
    version = "1.0.0"
    description = "PATH executable indexer"
    author = "termaid"

    def on_load(self):
        for cmd in ["search", "paths", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _path_dirs(self):
        return [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]

    @safe
    def cmd_search(self, arg=""):
        """Find PATH executables matching a substring: /tools search <pattern>"""
        pattern = (arg or "").strip().lower()
        if not pattern:
            return "[tools] Usage: /tools search <pattern>"
        matches = {}
        for d in self._path_dirs():
            dp = Path(d)
            if not dp.is_dir():
                continue
            try:
                for f in dp.iterdir():
                    if f.is_file() and pattern in f.name.lower() and _is_executable(f):
                        matches.setdefault(f.name, f)
            except OSError:
                continue
        if not matches:
            return f"[tools] No PATH executables matching '{pattern}'."
        lines = [f"[tools] {len(matches)} match(es):"]
        for name, path in sorted(matches.items()):
            lines.append(f"  {name:25s} {path}")
        return "\n".join(lines)

    @safe
    def cmd_paths(self, arg=""):
        """List PATH directories + executable counts"""
        dirs = self._path_dirs()
        lines = [f"[tools] {len(dirs)} PATH director(y/ies):"]
        for d in dirs:
            dp = Path(d)
            if not dp.is_dir():
                lines.append(f"  (missing)   {d}")
                continue
            try:
                count = sum(1 for f in dp.iterdir() if f.is_file() and _is_executable(f))
            except OSError:
                count = "?"
            lines.append(f"  {count!s:>6} exe(s)  {d}")
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
