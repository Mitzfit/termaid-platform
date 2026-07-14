"""Debug Module — Backend process/runtime diagnostics.

Introspects the running TermAId backend process itself (this Python
interpreter) — memory, thread count, GC stats, loaded module count. For
diagnosing the *host system*, see /hardware, /sysmonitor, /doctor; this
one is specifically about the server process you're talking to.

Commands (~3):
  /debug info          PID, memory, thread count, uptime-relevant stats
  /debug gc               Garbage collector stats + object counts
  /debug explain             How this module works
"""

import gc
import os
import sys
import threading
import time
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_START_TIME = time.time()


def _rss_bytes() -> int:
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    except ImportError:
        pass
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return counters.WorkingSetSize
    except Exception:
        pass
    return 0


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024 or unit == "GB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}GB"


class DebugModule(Module):
    name = "debug"
    version = "1.0.0"
    description = "Backend process/runtime diagnostics"
    author = "termaid"

    def on_load(self):
        for cmd in ["info", "gc", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_info(self, arg=""):
        """PID, memory, thread count, uptime-relevant stats"""
        rss = _rss_bytes()
        uptime = int(time.time() - _START_TIME)
        h, rem = divmod(uptime, 3600)
        m, s = divmod(rem, 60)
        lines = [
            "[debug] Process info:",
            f"  PID:        {os.getpid()}",
            f"  Python:     {sys.version.split()[0]} ({sys.platform})",
            f"  Threads:    {threading.active_count()}",
            f"  Memory:     {_human(rss) if rss else 'unavailable'}",
            f"  Uptime:     {h}h {m}m {s}s (this module's load time, not the whole backend)",
        ]
        return "\n".join(lines)

    @safe
    def cmd_gc(self, arg=""):
        """Garbage collector stats + object counts"""
        counts = gc.get_count()
        thresholds = gc.get_threshold()
        lines = [
            "[debug] Garbage collector:",
            f"  Tracked objects (gen0/1/2): {counts[0]}/{counts[1]}/{counts[2]}",
            f"  Collection thresholds:      {thresholds[0]}/{thresholds[1]}/{thresholds[2]}",
            f"  Total tracked objects:      {len(gc.get_objects())}",
        ]
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
