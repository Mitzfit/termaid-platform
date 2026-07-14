"""Hardware Module — Deep hardware inventory (read-only, no DB persistence).

Reuses the same WMI/proc detection approach as /learner's hardware scan, but
as a standalone read-only inventory tool with no SQLite storage — for a
persisted, cross-session profile, use /learner instead.

Commands (~10):
  /hardware cpu           CPU model, cores, threads
  /hardware gpu             GPU model + driver
  /hardware memory             Total installed RAM
  /hardware disks                Disk models + sizes
  /hardware summary                 All of the above in one call
  /hardware explain                   How this module works
"""

import json
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class HardwareModule(Module):
    name = "hardware"
    version = "1.0.0"
    description = "Deep hardware inventory, sensors, and driver update checks"
    author = "termaid"

    def on_load(self):
        for cmd in ["cpu", "gpu", "memory", "disks", "summary", "explain"]:
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
        """CPU model, cores, threads"""
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_Processor | Select-Object Name,NumberOfCores,"
                "NumberOfLogicalProcessors,MaxClockSpeed | ConvertTo-Json"
            )
            try:
                data = json.loads(r.stdout)
                if isinstance(data, list):
                    data = data[0]
                return (f"[hardware] CPU: {data.get('Name','?').strip()}\n"
                        f"  Cores:   {data.get('NumberOfCores','?')}\n"
                        f"  Threads: {data.get('NumberOfLogicalProcessors','?')}\n"
                        f"  Max MHz: {data.get('MaxClockSpeed','?')}")
            except Exception:
                return f"[hardware] Could not read CPU info: {r.stderr.strip() or r.stdout.strip()}"
        r = self._run("cat /proc/cpuinfo 2>/dev/null | grep -m1 'model name' | cut -d: -f2")
        return f"[hardware] CPU: {r.stdout.strip() or 'unknown'}"

    @safe
    def cmd_gpu(self, arg=""):
        """GPU model + driver"""
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_VideoController | Select-Object Name,DriverVersion | ConvertTo-Json"
            )
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                lines = ["[hardware] GPU(s):"]
                for d in data:
                    lines.append(f"  {d.get('Name','?')} (driver {d.get('DriverVersion','?')})")
                return "\n".join(lines)
            except Exception:
                return f"[hardware] Could not read GPU info: {r.stderr.strip() or r.stdout.strip()}"
        r = self._run("lspci 2>/dev/null | grep -i 'vga\\|3d'")
        return f"[hardware] GPU(s):\n{r.stdout.strip() or 'none detected'}"

    @safe
    def cmd_memory(self, arg=""):
        """Total installed RAM"""
        if sys.platform == "win32":
            r = self._run("(Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory")
            try:
                gb = int(r.stdout.strip()) / (1024 ** 3)
                return f"[hardware] RAM: {gb:.1f} GB installed"
            except Exception:
                return f"[hardware] Could not read RAM: {r.stderr.strip() or r.stdout.strip()}"
        r = self._run("grep MemTotal /proc/meminfo 2>/dev/null")
        try:
            kb = int(r.stdout.split()[1])
            return f"[hardware] RAM: {kb/1024/1024:.1f} GB installed"
        except Exception:
            return "[hardware] Could not read RAM"

    @safe
    def cmd_disks(self, arg=""):
        """Disk models + sizes"""
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_DiskDrive | Select-Object Model,Size,MediaType | ConvertTo-Json"
            )
            try:
                data = json.loads(r.stdout)
                if isinstance(data, dict):
                    data = [data]
                lines = ["[hardware] Disk(s):"]
                for d in data:
                    size_gb = (d.get("Size") or 0) / (1024 ** 3)
                    lines.append(f"  {d.get('Model','?')}  {size_gb:.0f} GB  ({d.get('MediaType','?')})")
                return "\n".join(lines)
            except Exception:
                return f"[hardware] Could not read disk info: {r.stderr.strip() or r.stdout.strip()}"
        r = self._run("lsblk -d -o NAME,SIZE,MODEL 2>/dev/null")
        return f"[hardware] Disk(s):\n{r.stdout.strip() or 'unknown'}"

    @safe
    def cmd_summary(self, arg=""):
        """All of the above in one call"""
        return "\n\n".join([self.cmd_cpu(""), self.cmd_gpu(""), self.cmd_memory(""), self.cmd_disks("")])

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
