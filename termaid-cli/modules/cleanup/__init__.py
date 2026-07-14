"""Cleanup Module — Safe removal of Python bytecode caches.

Deliberately narrow in scope: only targets `__pycache__` directories and
stray `*.pyc`/`*.pyo` files under a given root. These are always safely
regeneratable (Python recreates them on next import) — this module does
NOT touch build artifacts, node_modules, venvs, or anything else that
might be expensive or unsafe to lose. `scan` is a dry run; `run` requires
literal confirmation before deleting anything.

Commands (~3):
  /cleanup scan [path]         Dry run: list what would be removed + size
  /cleanup run [path] confirm    Actually remove __pycache__/*.pyc/*.pyo
  /cleanup explain                 How this module works
"""

import shutil
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


class CleanupModule(Module):
    name = "cleanup"
    version = "1.0.0"
    description = "Safe removal of Python bytecode caches (__pycache__, *.pyc/*.pyo)"
    author = "termaid"

    def on_load(self):
        for cmd in ["scan", "run", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _targets(self, root: Path):
        dirs, files, total = [], [], 0
        for p in root.rglob("__pycache__"):
            if p.is_dir():
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                dirs.append((p, size))
                total += size
        for pattern in ("*.pyc", "*.pyo"):
            for f in root.rglob(pattern):
                if "__pycache__" in f.parts:
                    continue  # already counted above
                if f.is_file():
                    size = f.stat().st_size
                    files.append((f, size))
                    total += size
        return dirs, files, total

    @safe
    def cmd_scan(self, arg=""):
        """Dry run: list what would be removed + size: /cleanup scan [path]"""
        root = Path((arg or ".").strip()).expanduser().resolve()
        if not root.is_dir():
            return f"[cleanup] Not a directory: {root}"
        dirs, files, total = self._targets(root)
        if not dirs and not files:
            return f"[cleanup] Nothing to clean under {root}."
        lines = [f"[cleanup] Under {root}:", f"  {len(dirs)} __pycache__ dir(s), {len(files)} stray .pyc/.pyo file(s)",
                f"  Total reclaimable: {_human(total)}", "",
                "  Re-run as: /cleanup run " + str(root) + " confirm"]
        return "\n".join(lines)

    @safe
    def cmd_run(self, arg=""):
        """Actually remove __pycache__/*.pyc/*.pyo (confirms): /cleanup run [path] confirm"""
        parts = (arg or "").split()
        if not parts or parts[-1].lower() != "confirm":
            return "[cleanup] This deletes files. Re-run as: /cleanup run [path] confirm"
        path_str = " ".join(parts[:-1]).strip() or "."
        root = Path(path_str).expanduser().resolve()
        if not root.is_dir():
            return f"[cleanup] Not a directory: {root}"
        dirs, files, total = self._targets(root)
        removed_dirs = removed_files = 0
        for p, _ in dirs:
            try:
                shutil.rmtree(p)
                removed_dirs += 1
            except Exception:
                pass
        for f, _ in files:
            try:
                f.unlink()
                removed_files += 1
            except Exception:
                pass
        return (f"[cleanup] Removed {removed_dirs} __pycache__ dir(s) and {removed_files} "
                f"stray file(s) under {root} ({_human(total)} reclaimed)")

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
