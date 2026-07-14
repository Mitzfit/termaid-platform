"""DeviceScan Module — Deep device diagnostics: drivers + problem codes. DANGEROUS tier (read-only).

Complements /device (which lists + can enable/disable): this only reports —
driver versions, problem/error codes, and conflicts. Classified DANGEROUS
because a full driver/hardware inventory is meaningful reconnaissance
information, same reasoning as /security. No write operations at all.

Commands (~2):
  /devicescan scan          List devices with problem codes (driver issues, conflicts)
  /devicescan drivers <device-id>  Driver details for one device
  /devicescan explain              How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class DeviceScanModule(Module):
    name = "devicescan"
    version = "1.0.0"
    description = "Deep device diagnostics: drivers + problem codes"
    author = "termaid"

    def on_load(self):
        for cmd in ["scan", "drivers", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _ps_escape(self, s: str) -> str:
        return s.replace("'", "''")

    @safe
    def cmd_scan(self, arg=""):
        """List devices with problem codes (driver issues, conflicts)"""
        if sys.platform != "win32":
            try:
                r = subprocess.run(["lspci", "-k"], capture_output=True, text=True, timeout=15)
                return f"[devicescan] {r.stdout.strip() or '(no output)'}"
            except Exception as e:
                return f"[devicescan] Failed: {e}"
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-PnpDevice | Where-Object { $_.Status -eq 'Error' -or $_.Status -eq 'Degraded' } | "
                 "Select-Object Status,Class,FriendlyName,InstanceId | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[devicescan] Failed: {e}"
        out = r.stdout.strip()
        return f"[devicescan] {out}" if out else "[devicescan] No devices with problem codes found."

    @safe
    def cmd_drivers(self, arg=""):
        """Driver details for one device: /devicescan drivers <device-id>"""
        device_id = (arg or "").strip()
        if not device_id:
            return "[devicescan] Usage: /devicescan drivers <device-id>"
        if sys.platform != "win32":
            return "[devicescan] Per-device driver detail is Windows-specific in this module."
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-PnpDeviceProperty -InstanceId '{self._ps_escape(device_id)}' "
                 "-KeyName 'DEVPKEY_Device_DriverVersion','DEVPKEY_Device_DriverDate' "
                 "-ErrorAction SilentlyContinue | Select-Object KeyName,Data | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[devicescan] Failed: {e}"
        out = r.stdout.strip()
        return f"[devicescan] {out}" if out else f"[devicescan] No driver info found for '{device_id}'"

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
