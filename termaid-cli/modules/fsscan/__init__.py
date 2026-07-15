"""FSScan Module — Duplicate, large-file, and filesystem hygiene scanner.

Read-only: reports what it finds, never deletes or changes permissions
(pair with /cleanup or /fsscan's own findings to decide what to act on
elsewhere). Duplicate detection groups files by size first (cheap) and
only hashes files that share a size with at least one other file (avoids
hashing everything in large trees).

Commands (~7):
  /fsscan duplicates <path>            Find duplicate files by content hash
  /fsscan large <path> [min_mb]           Find files above a size threshold (default 100MB)
  /fsscan empty-dirs <path>                  Find empty directories
  /fsscan old-files <path> [days]              Find files not modified in N days (default 365)
  /fsscan by-type <path>                         Disk usage breakdown by file extension
  /fsscan world-writable <path>                    Files/dirs writable by anyone (Linux/macOS only)
  /fsscan explain                                     How this module works
"""

import stat
import sys
import time
import hashlib
from collections import defaultdict
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


def _hash_file(p: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class FSScanModule(Module):
    name = "fsscan"
    version = "1.1.0"
    description = "Duplicate, large-file, and filesystem hygiene scanner"
    author = "termaid"

    def on_load(self):
        for cmd in ["duplicates", "large", "empty-dirs", "old-files", "by-type",
                    "world-writable", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_duplicates(self, arg=""):
        """Find duplicate files by content hash: /fsscan duplicates <path>"""
        root = Path((arg or ".").strip()).expanduser().resolve()
        if not root.is_dir():
            return f"[fsscan] Not a directory: {root}"

        by_size = defaultdict(list)
        for f in root.rglob("*"):
            try:
                if not f.is_file():
                    continue
                by_size[f.stat().st_size].append(f)
            except OSError:
                continue

        by_hash = defaultdict(list)
        for size, files in by_size.items():
            if len(files) < 2 or size == 0:
                continue
            for f in files:
                try:
                    by_hash[(size, _hash_file(f))].append(f)
                except OSError:
                    continue

        groups = [(key, files) for key, files in by_hash.items() if len(files) > 1]
        if not groups:
            return f"[fsscan] No duplicate files found under {root}."

        wasted = sum(key[0] * (len(files) - 1) for key, files in groups)
        lines = [f"[fsscan] {len(groups)} duplicate group(s) under {root} "
                f"({_human(wasted)} reclaimable):"]
        for (size, digest), files in sorted(groups, key=lambda g: -g[0][0])[:20]:
            lines.append(f"\n  {_human(size)} each, {len(files)} copies ({digest[:12]}...):")
            for f in files:
                lines.append(f"    {f}")
        if len(groups) > 20:
            lines.append(f"\n  ... and {len(groups) - 20} more group(s)")
        return "\n".join(lines)

    @safe
    def cmd_large(self, arg=""):
        """Find files above a size threshold (default 100MB): /fsscan large <path> [min_mb]"""
        parts = (arg or ".").split()
        path = parts[0] if parts else "."
        try:
            min_mb = float(parts[1]) if len(parts) > 1 else 100.0
        except ValueError:
            return f"[fsscan] Invalid min_mb: {parts[1]}"
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            return f"[fsscan] Not a directory: {root}"

        threshold = min_mb * 1024 * 1024
        found = []
        for f in root.rglob("*"):
            try:
                if not f.is_file():
                    continue
                size = f.stat().st_size
            except OSError:
                continue
            if size >= threshold:
                found.append((size, f))
        if not found:
            return f"[fsscan] No files >= {min_mb}MB under {root}."
        found.sort(reverse=True)
        lines = [f"[fsscan] {len(found)} file(s) >= {min_mb}MB under {root}:"]
        for size, f in found[:50]:
            lines.append(f"  {_human(size):>10s}  {f}")
        if len(found) > 50:
            lines.append(f"  ... and {len(found) - 50} more")
        return "\n".join(lines)

    @safe
    def cmd_empty_dirs(self, arg=""):
        """Find empty directories: /fsscan empty-dirs <path>"""
        root = Path((arg or ".").strip()).expanduser().resolve()
        if not root.is_dir():
            return f"[fsscan] Not a directory: {root}"
        empties = []
        for d in root.rglob("*"):
            try:
                if not d.is_dir():
                    continue
                if not any(d.iterdir()):
                    empties.append(d)
            except OSError:
                continue
        if not empties:
            return f"[fsscan] No empty directories under {root}."
        lines = [f"[fsscan] {len(empties)} empty director(y/ies) under {root}:"]
        for d in sorted(empties)[:100]:
            lines.append(f"  {d}")
        if len(empties) > 100:
            lines.append(f"  ... and {len(empties) - 100} more")
        return "\n".join(lines)

    @safe
    def cmd_old_files(self, arg=""):
        """Find files not modified in N days (default 365): /fsscan old-files <path> [days]"""
        parts = (arg or ".").split()
        path = parts[0] if parts else "."
        try:
            days = float(parts[1]) if len(parts) > 1 else 365.0
        except ValueError:
            return f"[fsscan] Invalid days: {parts[1]}"
        root = Path(path).expanduser().resolve()
        if not root.is_dir():
            return f"[fsscan] Not a directory: {root}"

        cutoff = time.time() - days * 86400
        found = []
        for f in root.rglob("*"):
            try:
                if not f.is_file():
                    continue
                mtime = f.stat().st_mtime
            except OSError:
                continue
            if mtime < cutoff:
                found.append((mtime, f))
        if not found:
            return f"[fsscan] No files older than {days:.0f} days under {root}."
        found.sort()
        lines = [f"[fsscan] {len(found)} file(s) untouched for {days:.0f}+ days under {root}:"]
        for mtime, f in found[:50]:
            age_days = (time.time() - mtime) / 86400
            lines.append(f"  {age_days:6.0f}d  {f}")
        if len(found) > 50:
            lines.append(f"  ... and {len(found) - 50} more")
        return "\n".join(lines)

    @safe
    def cmd_by_type(self, arg=""):
        """Disk usage breakdown by file extension: /fsscan by-type <path>"""
        root = Path((arg or ".").strip()).expanduser().resolve()
        if not root.is_dir():
            return f"[fsscan] Not a directory: {root}"
        totals = defaultdict(lambda: [0, 0])  # ext -> [count, bytes]
        for f in root.rglob("*"):
            try:
                if not f.is_file():
                    continue
                size = f.stat().st_size
            except OSError:
                continue
            ext = f.suffix.lower() or "(no extension)"
            totals[ext][0] += 1
            totals[ext][1] += size
        if not totals:
            return f"[fsscan] No files found under {root}."
        ranked = sorted(totals.items(), key=lambda kv: -kv[1][1])
        lines = [f"[fsscan] Disk usage by type under {root}:"]
        for ext, (count, size) in ranked[:30]:
            lines.append(f"  {ext:16s} {count:6d} file(s)  {_human(size):>10s}")
        return "\n".join(lines)

    @safe
    def cmd_world_writable(self, arg=""):
        """Files/dirs writable by anyone (Linux/macOS only): /fsscan world-writable <path>"""
        if sys.platform == "win32":
            return "[fsscan] Windows ACLs don't map to a single 'world-writable' bit — use /perms show on specific paths instead."
        root = Path((arg or ".").strip()).expanduser().resolve()
        if not root.is_dir():
            return f"[fsscan] Not a directory: {root}"
        found = []
        for p in root.rglob("*"):
            try:
                mode = p.stat().st_mode
            except OSError:
                continue
            if mode & stat.S_IWOTH:
                found.append(p)
        if not found:
            return f"[fsscan] No world-writable files/directories found under {root}."
        lines = [f"[fsscan] {len(found)} world-writable path(s) under {root}:"]
        for p in found[:100]:
            lines.append(f"  {'d' if p.is_dir() else '-'}  {p}")
        if len(found) > 100:
            lines.append(f"  ... and {len(found) - 100} more")
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
