"""Dashboard Module — Aggregated operational snapshot across other modules.

Distinct from /header (static device/network info): this pulls a live
operational picture — CPU/memory load, disk headroom, and git working-tree
state if a repo is active — into one view with simple threshold-based
alerts. Reuses stdlib-only checks (no dependency on other modules being
loaded) so it works even if git/docker aren't installed.

Commands (~4):
  /dashboard show           Full operational snapshot
  /dashboard alerts           Only the things worth flagging (thresholds)
  /dashboard watch               Note on why there's no live-refresh mode
  /dashboard explain                How this module works
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

_DISK_WARN_PCT = 85
_DISK_CRIT_PCT = 95


class DashboardModule(Module):
    name = "dashboard"
    version = "1.0.0"
    description = "Aggregated operational snapshot across other modules"
    author = "termaid"

    def on_load(self):
        for cmd in ["show", "alerts", "watch", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _disk(self):
        try:
            usage = shutil.disk_usage(os.getcwd())
            pct = usage.used / usage.total * 100
            return {"pct": pct, "free_gb": usage.free / (1024 ** 3), "total_gb": usage.total / (1024 ** 3)}
        except Exception:
            return {}

    def _cpu_mem(self):
        result = {}
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_Processor).LoadPercentage"],
                    capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
                cpu = r.stdout.strip().splitlines()
                if cpu:
                    result["cpu_pct"] = float(cpu[0])
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "$o=Get-CimInstance Win32_OperatingSystem; "
                     "[math]::Round((($o.TotalVisibleMemorySize-$o.FreePhysicalMemory)/$o.TotalVisibleMemorySize)*100,1)"],
                    capture_output=True, text=True, timeout=5, encoding="utf-8", errors="replace")
                mem = r.stdout.strip()
                if mem:
                    result["mem_pct"] = float(mem)
        except Exception:
            pass
        return result

    def _git_status(self):
        try:
            r = subprocess.run(["git", "status", "--short", "--branch"], capture_output=True,
                                text=True, timeout=5, cwd=os.getcwd(), encoding="utf-8", errors="replace")
            if r.returncode != 0:
                return {}
            lines = r.stdout.splitlines()
            branch = lines[0].replace("## ", "") if lines else "?"
            dirty = len(lines) - 1
            return {"branch": branch, "dirty": dirty}
        except Exception:
            return {}

    @safe
    def cmd_show(self, arg=""):
        """Full operational snapshot"""
        lines = ["=== Dashboard ===\n"]
        disk = self._disk()
        if disk:
            lines.append(f"  Disk:   {disk['pct']:.0f}% used, {disk['free_gb']:.1f}GB free "
                        f"of {disk['total_gb']:.1f}GB")
        cm = self._cpu_mem()
        if "cpu_pct" in cm:
            lines.append(f"  CPU:    {cm['cpu_pct']:.0f}%")
        if "mem_pct" in cm:
            lines.append(f"  Memory: {cm['mem_pct']:.0f}%")
        git = self._git_status()
        if git:
            clean = "clean" if git["dirty"] == 0 else f"{git['dirty']} change(s)"
            lines.append(f"  Git:    {git['branch']} ({clean})")
        if len(lines) == 1:
            lines.append("  No metrics available on this platform.")
        return "\n".join(lines)

    @safe
    def cmd_alerts(self, arg=""):
        """Only the things worth flagging (thresholds)"""
        alerts = []
        disk = self._disk()
        if disk:
            if disk["pct"] >= _DISK_CRIT_PCT:
                alerts.append(f"  CRITICAL  Disk {disk['pct']:.0f}% used, only {disk['free_gb']:.1f}GB free")
            elif disk["pct"] >= _DISK_WARN_PCT:
                alerts.append(f"  WARNING   Disk {disk['pct']:.0f}% used, {disk['free_gb']:.1f}GB free")
        cm = self._cpu_mem()
        if cm.get("mem_pct", 0) >= 90:
            alerts.append(f"  WARNING   Memory at {cm['mem_pct']:.0f}%")
        git = self._git_status()
        if git.get("dirty", 0) > 20:
            alerts.append(f"  NOTE      {git['dirty']} uncommitted changes on {git['branch']}")
        if not alerts:
            return "[dashboard] No alerts — everything looks nominal."
        return "[dashboard] Alerts:\n" + "\n".join(alerts)

    @safe
    def cmd_watch(self, arg=""):
        """Note on why there's no live-refresh mode"""
        return ("[dashboard] This is a request/response API, not a persistent stream — "
                "there's no server-push 'watch' mode. Poll /dashboard show or /dashboard alerts "
                "from the client on whatever interval you need.")

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
