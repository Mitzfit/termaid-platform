"""Log Module — Log file tail, filter, and AI analysis.

Reads a log file from disk. No live "follow" mode — a request/response API
has no good way to stream an indefinitely-growing file (that would need the
WebSocket surface, not a module command); re-run /log tail to get the latest.

Commands (~9):
  /log tail <path> [n]           Last n lines (default 50)
  /log filter <path> <pattern>     Lines containing a literal substring
  /log stats <path>                  Line count, size, last-modified
  /log analyze <path>                  AI analysis of the tail (needs AI_PROVIDER)
  /log explain                           How this module works
"""

import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_MAX_READ_BYTES = 5_000_000  # 5MB cap so a huge log can't stall a request


class LogModule(Module):
    name = "log"
    version = "1.0.0"
    description = "Log file tail, follow, filter, and AI analysis"
    author = "termaid"

    def on_load(self):
        for cmd in ["tail", "filter", "stats", "analyze", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _read_tail_bytes(self, p: Path) -> bytes:
        size = p.stat().st_size
        with p.open("rb") as f:
            if size > _MAX_READ_BYTES:
                f.seek(size - _MAX_READ_BYTES)
            return f.read()

    @safe
    def cmd_tail(self, arg=""):
        """Last n lines (default 50): /log tail <path> [n]"""
        parts = (arg or "").split()
        if not parts:
            return "[log] Usage: /log tail <path> [n]"
        path = parts[0]
        try:
            n = int(parts[1]) if len(parts) > 1 else 50
        except Exception:
            n = 50
        p = Path(path).expanduser()
        if not p.exists():
            return f"[log] Not found: {p}"
        try:
            data = self._read_tail_bytes(p).decode("utf-8", errors="replace")
        except Exception as e:
            return f"[log] Read failed: {e}"
        lines = data.splitlines()[-n:]
        return "\n".join(lines) if lines else "[log] (empty)"

    @safe
    def cmd_filter(self, arg=""):
        """Lines containing a literal substring: /log filter <path> <pattern>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[log] Usage: /log filter <path> <pattern>"
        path, pattern = parts
        p = Path(path).expanduser()
        if not p.exists():
            return f"[log] Not found: {p}"
        try:
            data = self._read_tail_bytes(p).decode("utf-8", errors="replace")
        except Exception as e:
            return f"[log] Read failed: {e}"
        matches = [l for l in data.splitlines() if pattern in l]
        if not matches:
            return f"[log] No lines matching '{pattern}'"
        return f"[log] {len(matches)} matching line(s):\n" + "\n".join(matches[-200:])

    @safe
    def cmd_stats(self, arg=""):
        """Line count, size, last-modified"""
        path = (arg or "").strip()
        if not path:
            return "[log] Usage: /log stats <path>"
        p = Path(path).expanduser()
        if not p.exists():
            return f"[log] Not found: {p}"
        st = p.stat()
        try:
            n_lines = sum(1 for _ in p.open("rb"))
        except Exception:
            n_lines = "unknown"
        modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
        return (f"[log] {p}:\n"
                f"  Size:     {st.st_size:,} bytes\n"
                f"  Lines:    {n_lines}\n"
                f"  Modified: {modified}")

    @safe
    def cmd_analyze(self, arg=""):
        """AI analysis of the tail (needs AI_PROVIDER)"""
        path = (arg or "").strip()
        if not path:
            return "[log] Usage: /log analyze <path>"
        if not self.ai:
            return "[log] No AI provider configured."
        p = Path(path).expanduser()
        if not p.exists():
            return f"[log] Not found: {p}"
        try:
            data = self._read_tail_bytes(p).decode("utf-8", errors="replace")
        except Exception as e:
            return f"[log] Read failed: {e}"
        tail = "\n".join(data.splitlines()[-300:])
        try:
            return self.ask_ai(
                tail,
                system=("Analyze this log excerpt. Summarize what's happening, flag any "
                        "errors/warnings and their likely cause, in a few sentences."),
            )
        except Exception as e:
            return f"[log] AI error: {e}"

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
