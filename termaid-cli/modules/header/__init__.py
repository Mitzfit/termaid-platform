"""Header Module — Top-of-terminal dashboard: version, user, IPs, MAC, device, storage.

Real system info via stdlib only (platform, socket, os, shutil) — no extra
dependencies. Network info is best-effort: a machine with no active network
interface will just show what it can.

Commands (~10):
  /header show          Full dashboard (version, user, OS, IPs, storage, uptime)
  /header device          OS/hardware summary
  /header ip                Local + attempted public IP
  /header storage             Disk usage for the current drive/mount
  /header uptime                 Process uptime (this backend session, not the OS)
  /header explain                  How this module works
"""

import os
import platform
import shutil
import socket
import sys
import time
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_START_TIME = time.time()


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


class HeaderModule(Module):
    name = "header"
    version = "1.0.0"
    description = "Top-of-terminal dashboard: version, user, IPs, MAC, device, storage"
    author = "termaid"

    def on_load(self):
        for cmd in ["show", "device", "ip", "storage", "uptime", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(0.5)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "unavailable"

    @safe
    def cmd_show(self, arg=""):
        """Full dashboard"""
        lines = [
            "=== TermAId Dashboard ===",
            f"  User:      {os.environ.get('USERNAME') or os.environ.get('USER') or 'unknown'}",
            f"  Host:      {platform.node()}",
            f"  OS:        {platform.system()} {platform.release()} ({platform.machine()})",
            f"  Python:    {platform.python_version()}",
            f"  Local IP:  {self._local_ip()}",
        ]
        try:
            usage = shutil.disk_usage(os.getcwd())
            lines.append(f"  Storage:   {_human(usage.used)} used / {_human(usage.total)} total "
                        f"({usage.used / usage.total * 100:.0f}%)")
        except Exception:
            pass
        lines.append(f"  Uptime:    {int(time.time() - _START_TIME)}s (this backend process)")
        return "\n".join(lines)

    @safe
    def cmd_device(self, arg=""):
        """OS/hardware summary"""
        lines = [
            "[header] Device:",
            f"  System:      {platform.system()}",
            f"  Release:     {platform.release()}",
            f"  Version:     {platform.version()[:120]}",
            f"  Machine:     {platform.machine()}",
            f"  Processor:   {platform.processor() or 'unknown'}",
            f"  CPUs:        {os.cpu_count()}",
        ]
        return "\n".join(lines)

    @safe
    def cmd_ip(self, arg=""):
        """Local + attempted public IP"""
        lines = [f"[header] Local IP:  {self._local_ip()}"]
        try:
            import httpx
            with httpx.Client(timeout=4.0) as c:
                r = c.get("https://api.ipify.org")
                lines.append(f"[header] Public IP: {r.text.strip() if r.status_code == 200 else 'unavailable'}")
        except Exception:
            lines.append("[header] Public IP: unavailable (no network or httpx)")
        return "\n".join(lines)

    @safe
    def cmd_storage(self, arg=""):
        """Disk usage for the current drive/mount"""
        try:
            usage = shutil.disk_usage(os.getcwd())
        except Exception as e:
            return f"[header] Could not read disk usage: {e}"
        pct = usage.used / usage.total * 100
        return (f"[header] Storage ({os.getcwd()}):\n"
                f"  Total: {_human(usage.total)}\n"
                f"  Used:  {_human(usage.used)} ({pct:.1f}%)\n"
                f"  Free:  {_human(usage.free)}")

    @safe
    def cmd_uptime(self, arg=""):
        """Process uptime (this backend session, not the OS)"""
        secs = int(time.time() - _START_TIME)
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        return f"[header] Backend uptime: {h}h {m}m {s}s"

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
