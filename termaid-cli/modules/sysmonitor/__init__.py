"""SysMonitor Module — System resource monitoring.

Real CPU/memory/disk/process readings via platform-specific commands
(PowerShell counters on Windows, /proc + ps on Linux) — no psutil dependency,
same approach as /learner's hardware scan.

Commands (~9):
  /sysmonitor cpu           Current CPU usage %
  /sysmonitor memory          Memory used/free
  /sysmonitor disk              Disk usage for the current drive
  /sysmonitor processes            Top processes by memory
  /sysmonitor snapshot                CPU + memory + disk in one call
  /sysmonitor explain                   How this module works
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


def _human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}TB"


class SysMonitorModule(Module):
    name = "sysmonitor"
    version = "1.0.0"
    description = "System resource monitoring"
    author = "termaid"

    def on_load(self):
        for cmd in ["cpu", "memory", "disk", "processes", "snapshot", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _run(self, cmd, timeout=10):
        try:
            if sys.platform == "win32":
                return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                      capture_output=True, text=True, timeout=timeout,
                                      encoding="utf-8", errors="replace")
            return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                  timeout=timeout, encoding="utf-8", errors="replace")
        except Exception as e:
            return subprocess.CompletedProcess(cmd, 1, "", str(e))

    @safe
    def cmd_cpu(self, arg=""):
        """Current CPU usage %"""
        if sys.platform == "win32":
            r = self._run("(Get-Counter '\\Processor(_Total)\\% Processor Time' "
                          "-SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue")
            try:
                return f"[sysmonitor] CPU usage: {float(r.stdout.strip()):.1f}%"
            except Exception:
                return f"[sysmonitor] Could not read CPU usage: {r.stderr.strip() or r.stdout.strip()}"
        r = self._run("vmstat 1 2 | tail -1 | awk '{print 100-$15}'")
        try:
            return f"[sysmonitor] CPU usage: {float(r.stdout.strip()):.1f}%"
        except Exception:
            return f"[sysmonitor] Could not read CPU usage (vmstat unavailable?)"

    @safe
    def cmd_memory(self, arg=""):
        """Memory used/free"""
        if sys.platform == "win32":
            r = self._run(
                "$os = Get-WmiObject Win32_OperatingSystem; "
                "[math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory)/1MB,2).ToString() + '|' + "
                "[math]::Round($os.TotalVisibleMemorySize/1MB,2).ToString()"
            )
            try:
                used, total = (float(x) for x in r.stdout.strip().split("|"))
                return f"[sysmonitor] Memory: {used:.1f} GB used / {total:.1f} GB total ({used/total*100:.0f}%)"
            except Exception:
                return f"[sysmonitor] Could not read memory: {r.stderr.strip() or r.stdout.strip()}"
        r = self._run("free -m 2>/dev/null | awk 'NR==2 {print $3\"|\"$2}'")
        try:
            used, total = (float(x) for x in r.stdout.strip().split("|"))
            return f"[sysmonitor] Memory: {used/1024:.1f} GB used / {total/1024:.1f} GB total ({used/total*100:.0f}%)"
        except Exception:
            return "[sysmonitor] Could not read memory (free unavailable?)"

    @safe
    def cmd_disk(self, arg=""):
        """Disk usage for the current drive"""
        try:
            usage = shutil.disk_usage(os.getcwd())
        except Exception as e:
            return f"[sysmonitor] Could not read disk usage: {e}"
        pct = usage.used / usage.total * 100
        return (f"[sysmonitor] Disk ({os.getcwd()}): {_human(usage.used)} used / "
                f"{_human(usage.total)} total ({pct:.0f}%), {_human(usage.free)} free")

    @safe
    def cmd_processes(self, arg=""):
        """Top processes by memory"""
        if sys.platform == "win32":
            r = self._run(
                "Get-Process | Sort-Object WS -Descending | Select-Object -First 10 "
                "Name,Id,@{N='MemMB';E={[math]::Round($_.WS/1MB,1)}} | Format-Table -AutoSize | Out-String -Width 200"
            )
            return f"[sysmonitor] Top processes by memory:\n{r.stdout or r.stderr}"
        r = self._run("ps -eo pid,comm,%mem --sort=-%mem 2>/dev/null | head -11")
        return f"[sysmonitor] Top processes by memory:\n{r.stdout or r.stderr}"

    @safe
    def cmd_snapshot(self, arg=""):
        """CPU + memory + disk in one call"""
        return "\n".join([self.cmd_cpu(""), self.cmd_memory(""), self.cmd_disk("")])

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
