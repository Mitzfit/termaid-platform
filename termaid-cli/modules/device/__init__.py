"""Device Module — Connected device inventory + enable/disable. DANGEROUS tier.

Windows: wraps `Get-PnpDevice`/`Disable-PnpDevice`/`Enable-PnpDevice`.
Listing is read-only; disabling a device (e.g. accidentally disabling your
own keyboard or the disk controller your OS boots from) can leave a system
hard to use until re-enabled, hence the confirm gate on both write ops.

Commands (~4):
  /device list                       List connected devices
  /device info <device-id>             Full details for one device
  /device disable <device-id> confirm    Disable a device
  /device enable <device-id> confirm       Re-enable a device
  /device explain                            How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class DeviceModule(Module):
    name = "device"
    version = "1.0.0"
    description = "Connected device inventory + enable/disable"
    author = "termaid"

    def on_load(self):
        for cmd in ["list", "info", "disable", "enable", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _ps_escape(self, s: str) -> str:
        """Escape for embedding in a single-quoted PowerShell string literal —
        doubling ' is the only escape single-quoted strings recognize, and it's
        what closes off the injection class fixed in /vm (see that module's history)."""
        return s.replace("'", "''")

    @safe
    def cmd_list(self, arg=""):
        """List connected devices"""
        if sys.platform != "win32":
            try:
                r = subprocess.run(["lsusb"], capture_output=True, text=True, timeout=10)
                return f"[device] {r.stdout.strip() or '(no output)'}"
            except Exception as e:
                return f"[device] Failed: {e}"
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-PnpDevice | Where-Object {$_.Status -ne 'Unknown'} | "
                 "Select-Object Status,Class,FriendlyName,InstanceId | Format-Table -AutoSize"],
                capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[device] Failed: {e}"
        return f"[device] {r.stdout.strip() or r.stderr.strip()}"

    @safe
    def cmd_info(self, arg=""):
        """Full details for one device: /device info <device-id>"""
        device_id = (arg or "").strip()
        if not device_id:
            return "[device] Usage: /device info <device-id>"
        if sys.platform != "win32":
            return "[device] Detailed per-device info is Windows-specific in this module — try 'lsusb -v' for USB devices directly."
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Get-PnpDevice -InstanceId '{self._ps_escape(device_id)}' -ErrorAction SilentlyContinue | "
                 "Select-Object * | Format-List"],
                capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[device] Failed: {e}"
        out = r.stdout.strip()
        return f"[device] {out}" if out else f"[device] No device found with id '{device_id}'"

    @safe
    def cmd_disable(self, arg=""):
        """Disable a device (confirms): /device disable <device-id> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[-1].lower() != "confirm":
            return "[device] This can make hardware (even your keyboard/disk) unusable until re-enabled. Re-run as: /device disable <device-id> confirm"
        if sys.platform != "win32":
            return "[device] Enable/disable is Windows-specific in this module."
        device_id = " ".join(parts[:-1])
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Disable-PnpDevice -InstanceId '{self._ps_escape(device_id)}' -Confirm:$false -ErrorAction Stop"],
                capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[device] Failed: {e}"
        if r.returncode != 0:
            return f"[device] {(r.stderr or r.stdout).strip()}"
        return f"[device] Disabled {device_id}"

    @safe
    def cmd_enable(self, arg=""):
        """Re-enable a device (confirms): /device enable <device-id> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[-1].lower() != "confirm":
            return "[device] Re-run as: /device enable <device-id> confirm"
        if sys.platform != "win32":
            return "[device] Enable/disable is Windows-specific in this module."
        device_id = " ".join(parts[:-1])
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f"Enable-PnpDevice -InstanceId '{self._ps_escape(device_id)}' -Confirm:$false -ErrorAction Stop"],
                capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[device] Failed: {e}"
        if r.returncode != 0:
            return f"[device] {(r.stderr or r.stdout).strip()}"
        return f"[device] Enabled {device_id}"

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
