"""DiskSpace Module — Disk space analysis: largest files, breakdown by extension.

Read-only reporting only — this suggests what's taking up space, it never
deletes anything. Pair with /filetools or your own file manager for cleanup.

Commands (~9):
  /diskspace largest <path> [n]      n largest files under path (default 20)
  /diskspace by-extension <path>       Total size grouped by file extension
  /diskspace summary <path>              File/dir counts + total size
  /diskspace explain                       How this module works
"""

import os
from collections import defaultdict
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_MAX_SCANNED = 200_000


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


class DiskSpaceModule(Module):
    name = "diskspace"
    version = "1.0.0"
    description = "Disk space analysis: largest files, duplicates, cleanup"
    author = "termaid"

    def on_load(self):
        for cmd in ["largest", "by-extension", "summary", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    def _walk_files(self, root: Path):
        scanned = 0
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                scanned += 1
                if scanned > _MAX_SCANNED:
                    return
                p = Path(dirpath) / fn
                try:
                    yield p, p.stat().st_size
                except OSError:
                    continue

    @safe
    def cmd_largest(self, arg=""):
        """n largest files under path (default 20)"""
        parts = (arg or "").split()
        if not parts:
            return "[diskspace] Usage: /diskspace largest <path> [n]"
        root = Path(parts[0]).expanduser()
        try:
            n = int(parts[1]) if len(parts) > 1 else 20
        except Exception:
            n = 20
        if not root.is_dir():
            return f"[diskspace] Not a directory: {root}"
        files = list(self._walk_files(root))
        files.sort(key=lambda x: -x[1])
        top = files[:n]
        if not top:
            return f"[diskspace] No files found under {root}"
        lines = [f"[diskspace] {len(top)} largest file(s) under {root}:"]
        for p, size in top:
            lines.append(f"  {_human(size):>10s}  {p}")
        return "\n".join(lines)

    @safe
    def cmd_by_extension(self, arg=""):
        """Total size grouped by file extension"""
        root = (arg or "").strip()
        if not root:
            return "[diskspace] Usage: /diskspace by-extension <path>"
        root = Path(root).expanduser()
        if not root.is_dir():
            return f"[diskspace] Not a directory: {root}"
        totals = defaultdict(lambda: [0, 0])  # ext -> [count, bytes]
        for p, size in self._walk_files(root):
            ext = p.suffix.lower() or "(no extension)"
            totals[ext][0] += 1
            totals[ext][1] += size
        if not totals:
            return f"[diskspace] No files found under {root}"
        ranked = sorted(totals.items(), key=lambda kv: -kv[1][1])
        lines = [f"[diskspace] By extension under {root}:"]
        for ext, (count, size) in ranked[:30]:
            lines.append(f"  {ext:<15s} {count:>6d} file(s)  {_human(size):>10s}")
        return "\n".join(lines)

    @safe
    def cmd_summary(self, arg=""):
        """File/dir counts + total size"""
        root = (arg or "").strip()
        if not root:
            return "[diskspace] Usage: /diskspace summary <path>"
        root = Path(root).expanduser()
        if not root.is_dir():
            return f"[diskspace] Not a directory: {root}"
        n_files = 0
        n_dirs = 0
        total = 0
        for dirpath, dirnames, filenames in os.walk(root):
            n_dirs += len(dirnames)
            for fn in filenames:
                n_files += 1
                try:
                    total += (Path(dirpath) / fn).stat().st_size
                except OSError:
                    continue
                if n_files > _MAX_SCANNED:
                    break
        return (f"[diskspace] {root}:\n"
                f"  Files: {n_files:,}\n"
                f"  Dirs:  {n_dirs:,}\n"
                f"  Total: {_human(total)}")

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
