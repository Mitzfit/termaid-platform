"""Find Module — Fast filesystem search (name/size/extension/recency).

A real recursive file-search tool (like a scoped `find`), not a command
lookup — see /catalog and /smart for searching TermAId's own commands. This
shells out to nothing; it's a pure os.walk-based scan, capped so a huge tree
can't stall a request.

Commands (~8):
  /find name <root> <pattern>        Files whose name contains <pattern> (case-insensitive)
  /find ext <root> <ext>               Files with a given extension, e.g. .py
  /find size <root> <min-mb>             Files at least <min-mb> megabytes
  /find recent <root> [days]               Files modified in the last N days (default 1)
  /find explain                              How this module works
"""

import fnmatch
import os
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_MAX_RESULTS = 200
_MAX_SCANNED = 200_000  # hard cap on files visited, so a huge tree can't hang a request


class FindModule(Module):
    name = "find"
    version = "1.0.0"
    description = "Fast cross-module command search and drill-down help"
    author = "termaid"

    def on_load(self):
        for cmd in ["name", "ext", "size", "recent", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _walk(self, root: Path):
        scanned = 0
        for dirpath, _dirnames, filenames in os.walk(root):
            for fn in filenames:
                scanned += 1
                if scanned > _MAX_SCANNED:
                    return
                yield Path(dirpath) / fn

    @safe
    def cmd_name(self, arg=""):
        """Files whose name contains <pattern>: /find name <root> <pattern>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[find] Usage: /find name <root> <pattern>"
        root, pattern = Path(parts[0]).expanduser(), parts[1].lower()
        if not root.is_dir():
            return f"[find] Not a directory: {root}"
        hits = []
        for f in self._walk(root):
            if pattern in f.name.lower():
                hits.append(str(f))
                if len(hits) >= _MAX_RESULTS:
                    break
        if not hits:
            return f"[find] No files matching '{pattern}' under {root}"
        return f"[find] {len(hits)} match(es) (capped at {_MAX_RESULTS}):\n" + "\n".join(hits)

    @safe
    def cmd_ext(self, arg=""):
        """Files with a given extension: /find ext <root> <.ext>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[find] Usage: /find ext <root> <.extension>"
        root, ext = Path(parts[0]).expanduser(), parts[1]
        if not ext.startswith("."):
            ext = "." + ext
        if not root.is_dir():
            return f"[find] Not a directory: {root}"
        hits = []
        for f in self._walk(root):
            if f.suffix.lower() == ext.lower():
                hits.append(str(f))
                if len(hits) >= _MAX_RESULTS:
                    break
        if not hits:
            return f"[find] No '{ext}' files under {root}"
        return f"[find] {len(hits)} '{ext}' file(s) (capped at {_MAX_RESULTS}):\n" + "\n".join(hits)

    @safe
    def cmd_size(self, arg=""):
        """Files at least <min-mb> megabytes: /find size <root> <min-mb>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[find] Usage: /find size <root> <min-megabytes>"
        root = Path(parts[0]).expanduser()
        try:
            min_bytes = float(parts[1]) * 1024 * 1024
        except Exception:
            return "[find] min-mb must be a number"
        if not root.is_dir():
            return f"[find] Not a directory: {root}"
        hits = []
        for f in self._walk(root):
            try:
                if f.stat().st_size >= min_bytes:
                    hits.append((f.stat().st_size, str(f)))
                    if len(hits) >= _MAX_RESULTS:
                        break
            except OSError:
                continue
        if not hits:
            return f"[find] No files >= {parts[1]}MB under {root}"
        hits.sort(reverse=True)
        lines = [f"[find] {len(hits)} file(s) >= {parts[1]}MB:"]
        for size, path in hits:
            lines.append(f"  {size/1024/1024:>8.1f}MB  {path}")
        return "\n".join(lines)

    @safe
    def cmd_recent(self, arg=""):
        """Files modified in the last N days (default 1): /find recent <root> [days]"""
        parts = (arg or "").split()
        if not parts:
            return "[find] Usage: /find recent <root> [days]"
        root = Path(parts[0]).expanduser()
        try:
            days = float(parts[1]) if len(parts) > 1 else 1.0
        except Exception:
            days = 1.0
        if not root.is_dir():
            return f"[find] Not a directory: {root}"
        cutoff = time.time() - days * 86400
        hits = []
        for f in self._walk(root):
            try:
                mtime = f.stat().st_mtime
                if mtime >= cutoff:
                    hits.append((mtime, str(f)))
                    if len(hits) >= _MAX_RESULTS:
                        break
            except OSError:
                continue
        if not hits:
            return f"[find] No files modified in the last {days:g} day(s) under {root}"
        hits.sort(reverse=True)
        lines = [f"[find] {len(hits)} file(s) modified in the last {days:g} day(s):"]
        for mtime, path in hits:
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(mtime))
            lines.append(f"  [{when}] {path}")
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
