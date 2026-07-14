"""FSScan Module — Duplicate and large-file scanner.

Read-only: reports what it finds, never deletes. Duplicate detection
groups files by size first (cheap) and only hashes files that share a
size with at least one other file (avoids hashing everything in large
trees). Large-file scan is a simple threshold walk.

Commands (~3):
  /fsscan duplicates <path>            Find duplicate files by content hash
  /fsscan large <path> [min_mb]           Find files above a size threshold (default 100MB)
  /fsscan explain                             How this module works
"""

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
    version = "1.0.0"
    description = "Duplicate and large-file scanner"
    author = "termaid"

    def on_load(self):
        for cmd in ["duplicates", "large", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_duplicates(self, arg=""):
        """Find duplicate files by content hash: /fsscan duplicates <path>"""
        root = Path((arg or ".").strip()).expanduser().resolve()
        if not root.is_dir():
            return f"[fsscan] Not a directory: {root}"

        by_size = defaultdict(list)
        for f in root.rglob("*"):
            if f.is_file():
                try:
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
            if f.is_file():
                try:
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
