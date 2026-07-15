"""Tools Module — PATH executable indexer, version checks, and shadowing detection.

Scans every directory on PATH and indexes what's executable there —
useful for "is X on my PATH and where," "what's a tool starting with Y,"
"which of my three python.exe's actually wins," and "what versions do I
have installed" without shelling out to `which`/`where` per-guess.
Read-only except `add-to-path`, which only ever changes this backend
process's own environment (never anything system-wide or persistent) —
it's gone the moment the process restarts.

Commands (~6):
  /tools search <pattern>       Find PATH executables matching a substring
  /tools paths                    List PATH directories + executable counts
  /tools versions <name>            Every copy of a tool on PATH + its version
  /tools duplicates                   Executables that appear more than once on PATH (shadowing)
  /tools missing                        Check a curated list of commonly-wanted tools
  /tools add-to-path <dir>                Add a directory to THIS PROCESS's PATH (not persistent)
  /tools explain                             How this module works
"""

import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_EXE_EXTS = {".exe", ".bat", ".cmd", ".com"} if sys.platform == "win32" else set()

_COMMONLY_WANTED = ["git", "docker", "node", "npm", "python3", "curl", "wget",
                    "ssh", "make", "cargo", "go", "java", "rustc", "code"]


def _is_executable(p: Path) -> bool:
    if sys.platform == "win32":
        return p.suffix.lower() in _EXE_EXTS
    return os.access(p, os.X_OK)


class ToolsModule(Module):
    name = "tools"
    version = "1.1.0"
    description = "PATH executable indexer, version checks, and shadowing detection"
    author = "termaid"

    def on_load(self):
        for cmd in ["search", "paths", "versions", "duplicates", "missing", "add-to-path", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    def _path_dirs(self):
        return [d for d in os.environ.get("PATH", "").split(os.pathsep) if d]

    def _version(self, path: Path) -> str:
        try:
            r = subprocess.run([str(path), "--version"], capture_output=True, text=True,
                                timeout=5, encoding="utf-8", errors="replace")
            first_line = (r.stdout or r.stderr or "").strip().splitlines()
            return first_line[0][:70] if first_line else "(no version output)"
        except Exception:
            return "(couldn't run)"

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
    def cmd_versions(self, arg=""):
        """Every copy of a tool on PATH + its version: /tools versions <name>"""
        name = (arg or "").strip().lower()
        if not name:
            return "[tools] Usage: /tools versions <name>"
        found = []
        for d in self._path_dirs():
            dp = Path(d)
            if not dp.is_dir():
                continue
            try:
                for f in dp.iterdir():
                    if f.is_file() and _is_executable(f):
                        stem = f.stem.lower()
                        if stem == name or f.name.lower() == name:
                            found.append(f)
            except OSError:
                continue
        if not found:
            return f"[tools] No copies of '{name}' found on PATH."
        winner = shutil.which(name)
        lines = [f"[tools] {len(found)} copy(ies) of '{name}' on PATH:"]
        for f in found:
            marker = " <- wins (first on PATH)" if winner and str(f) == winner else ""
            lines.append(f"  {f}{marker}")
            lines.append(f"    {self._version(f)}")
        return "\n".join(lines)

    @safe
    def cmd_duplicates(self, arg=""):
        """Executables that appear more than once on PATH (shadowing)"""
        by_name = defaultdict(list)
        for d in self._path_dirs():
            dp = Path(d)
            if not dp.is_dir():
                continue
            try:
                for f in dp.iterdir():
                    if f.is_file() and _is_executable(f):
                        key = f.stem.lower() if sys.platform == "win32" else f.name.lower()
                        by_name[key].append(f)
            except OSError:
                continue
        dupes = {name: paths for name, paths in by_name.items() if len(paths) > 1}
        if not dupes:
            return "[tools] No PATH shadowing detected — every executable name appears once."
        lines = [f"[tools] {len(dupes)} shadowed name(s):"]
        for name, paths in sorted(dupes.items()):
            winner = shutil.which(name)
            lines.append(f"\n  {name} ({len(paths)} copies):")
            for p in paths:
                marker = " <- wins" if winner and str(p) == winner else ""
                lines.append(f"    {p}{marker}")
        return "\n".join(lines)

    @safe
    def cmd_missing(self, arg=""):
        """Check a curated list of commonly-wanted tools"""
        missing = [t for t in _COMMONLY_WANTED if not shutil.which(t)]
        present = [t for t in _COMMONLY_WANTED if shutil.which(t)]
        lines = [f"[tools] {len(present)}/{len(_COMMONLY_WANTED)} commonly-wanted tools present."]
        if missing:
            lines.append("Missing: " + ", ".join(missing) + "  (see /doctor fix <name> for install hints)")
        else:
            lines.append("Nothing missing from the curated list.")
        return "\n".join(lines)

    @safe
    def cmd_add_to_path(self, arg=""):
        """Add a directory to THIS PROCESS's PATH, not persistent: /tools add-to-path <dir>"""
        path_s = (arg or "").strip()
        if not path_s:
            return "[tools] Usage: /tools add-to-path <dir>"
        p = Path(path_s).expanduser()
        if not p.is_dir():
            return f"[tools] Not a directory: {p}"
        current = os.environ.get("PATH", "")
        if str(p) in current.split(os.pathsep):
            return f"[tools] {p} is already on PATH."
        os.environ["PATH"] = str(p) + os.pathsep + current
        return (f"[tools] Added {p} to PATH for this backend process only — it resets on restart. "
                f"Edit your shell profile or system environment variables for a permanent change.")

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
