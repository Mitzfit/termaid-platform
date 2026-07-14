"""Perftune Module — Read-only performance advisory.

Looks at a handful of cheap signals (disk headroom, memory pressure, CPU
core count vs. reported load) and returns generic, conservative
suggestions. Never changes any setting itself — this is advice, not
automation. Pair with /dashboard for the live numbers this reasons over.

Commands (~2):
  /perftune suggest         Suggestions based on current system signals
  /perftune explain            How this module works
"""

import os
import shutil
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class PerftuneModule(Module):
    name = "perftune"
    version = "1.0.0"
    description = "Read-only performance advisory"
    author = "termaid"

    def on_load(self):
        for cmd in ["suggest", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _mem_pct(self):
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "$o=Get-CimInstance Win32_OperatingSystem; "
                     "[math]::Round((($o.TotalVisibleMemorySize-$o.FreePhysicalMemory)/$o.TotalVisibleMemorySize)*100,1)"],
                    capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
                return float(r.stdout.strip())
        except Exception:
            pass
        return None

    @safe
    def cmd_suggest(self, arg=""):
        """Suggestions based on current system signals"""
        suggestions = []

        try:
            usage = shutil.disk_usage(os.getcwd())
            pct = usage.used / usage.total * 100
            free_gb = usage.free / (1024 ** 3)
            if pct >= 95:
                suggestions.append(f"Disk is {pct:.0f}% full ({free_gb:.1f}GB free) — this can slow "
                                    "everything down (swap/temp files need headroom). Free up space "
                                    "or run /cleanup scan and /fsscan large to find what's using it.")
            elif pct >= 85:
                suggestions.append(f"Disk is {pct:.0f}% full — worth keeping an eye on before it "
                                    "becomes a problem.")
        except Exception:
            pass

        mem_pct = self._mem_pct()
        if mem_pct is not None:
            if mem_pct >= 90:
                suggestions.append(f"Memory is at {mem_pct:.0f}% — close unused applications, or "
                                    "check /sysmonitor processes for the top consumers.")
            elif mem_pct >= 75:
                suggestions.append(f"Memory is at {mem_pct:.0f}% — not critical, but if things feel "
                                    "sluggish this is a likely first suspect.")

        cpu_count = os.cpu_count() or 1
        if cpu_count <= 2:
            suggestions.append(f"Only {cpu_count} logical CPU(s) detected — CPU-bound workloads "
                                "(builds, video encoding) will bottleneck here regardless of other tuning.")

        if not suggestions:
            return "[perftune] No obvious issues from the signals available. Nothing to suggest right now."
        return "[perftune] Suggestions:\n" + "\n".join(f"  - {s}" for s in suggestions)

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
