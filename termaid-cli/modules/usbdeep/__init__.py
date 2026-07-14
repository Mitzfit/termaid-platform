"""USBDeep Module — Deep USB device descriptor inspection. DANGEROUS tier (read-only).

Read-only by design: lists connected USB devices with full descriptor
detail (vendor/product IDs, serial numbers, power draw). Deliberately does
NOT include any USB firmware read/write capability — flashing a USB
controller's firmware is a recognized attack technique (BadUSB) and is out
of scope for this module regardless of what "deep" might otherwise imply.
Classified DANGEROUS because full device descriptor enumeration
(serial numbers, exact hardware identifiers) is meaningful reconnaissance
information about connected hardware.

Commands (~2):
  /usbdeep list             List USB devices with full descriptors
  /usbdeep info <device-id>   Full descriptor detail for one device
  /usbdeep explain               How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class USBDeepModule(Module):
    name = "usbdeep"
    version = "1.0.0"
    description = "Deep USB device descriptor inspection (read-only — no firmware access)"
    author = "termaid"

    def on_load(self):
        for cmd in ["list", "info", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _ps_escape(self, s: str) -> str:
        return s.replace("'", "''")

    @safe
    def cmd_list(self, arg=""):
        """List USB devices with full descriptors"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-PnpDevice -Class USB | Select-Object Status,FriendlyName,InstanceId | "
                     "Format-Table -AutoSize"],
                    capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(["lsusb", "-v"], capture_output=True, text=True, timeout=15)
        except Exception as e:
            return f"[usbdeep] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[usbdeep] {out[:6000]}" if out else "[usbdeep] No USB devices found."

    @safe
    def cmd_info(self, arg=""):
        """Full descriptor detail for one device: /usbdeep info <device-id>"""
        device_id = (arg or "").strip()
        if not device_id:
            return "[usbdeep] Usage: /usbdeep info <device-id>"
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-PnpDevice -InstanceId '{self._ps_escape(device_id)}' -ErrorAction SilentlyContinue | "
                     "Select-Object * | Format-List"],
                    capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
                out = r.stdout.strip()
            else:
                r = subprocess.run(["lsusb", "-v", "-d", device_id], capture_output=True,
                                    text=True, timeout=10)
                out = (r.stdout or r.stderr).strip()
        except Exception as e:
            return f"[usbdeep] Failed: {e}"
        return f"[usbdeep] {out}" if out else f"[usbdeep] No device found with id '{device_id}'"

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
