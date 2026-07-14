"""Firmware Module — BIOS/UEFI firmware info + update management. DANGEROUS tier.

Viewing firmware info is read-only. Applying a firmware update (via
`fwupdmgr` on Linux — Windows firmware updates go through OEM tools this
module doesn't wrap, since there's no universal Windows equivalent) can
brick hardware if interrupted or applied to the wrong device, hence the
confirm gate on `apply`.

Commands (~3):
  /firmware info               BIOS/UEFI vendor, version, release date
  /firmware check-updates        List available firmware updates (Linux: fwupdmgr)
  /firmware apply <device-id> confirm  Apply a pending firmware update
  /firmware explain                       How this module works
"""

import shutil
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class FirmwareModule(Module):
    name = "firmware"
    version = "1.0.0"
    description = "BIOS/UEFI firmware info + update management"
    author = "termaid"

    def on_load(self):
        for cmd in ["info", "check-updates", "apply", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_info(self, arg=""):
        """BIOS/UEFI vendor, version, release date"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion,ReleaseDate | "
                     "Format-List"],
                    capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
                return f"[firmware] {r.stdout.strip()}"
            else:
                out = []
                for p, label in (("/sys/class/dmi/id/bios_vendor", "Vendor"),
                                  ("/sys/class/dmi/id/bios_version", "Version"),
                                  ("/sys/class/dmi/id/bios_date", "Date")):
                    try:
                        from pathlib import Path
                        val = Path(p).read_text(errors="replace").strip()
                        out.append(f"{label}: {val}")
                    except Exception:
                        pass
                return "[firmware] " + (", ".join(out) if out else "unavailable (try running with more privileges)")
        except Exception as e:
            return f"[firmware] Failed: {e}"

    @safe
    def cmd_check_updates(self, arg=""):
        """List available firmware updates (Linux: fwupdmgr)"""
        if sys.platform == "win32":
            return "[firmware] No universal Windows firmware-update tool — check your OEM's utility (Dell Command Update, Lenovo Vantage, etc.)."
        if not shutil.which("fwupdmgr"):
            return "[firmware] fwupdmgr not installed. Install it with your package manager (fwupd)."
        try:
            r = subprocess.run(["fwupdmgr", "get-updates"], capture_output=True, text=True, timeout=30)
        except Exception as e:
            return f"[firmware] Failed: {e}"
        return f"[firmware] {(r.stdout or r.stderr).strip()}"

    @safe
    def cmd_apply(self, arg=""):
        """Apply a pending firmware update (confirms): /firmware apply <device-id> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[firmware] Usage: /firmware apply <device-id> confirm"
        device_id = parts[0]
        if sys.platform == "win32":
            return "[firmware] No universal Windows firmware-update tool — check your OEM's utility."
        if not shutil.which("fwupdmgr"):
            return "[firmware] fwupdmgr not installed."
        try:
            r = subprocess.run(["fwupdmgr", "update", device_id], capture_output=True,
                                text=True, timeout=300)
        except subprocess.TimeoutExpired:
            return "[firmware] Update timed out after 300s — do not power off the device."
        except Exception as e:
            return f"[firmware] Failed: {e}"
        return f"[firmware] {(r.stdout or r.stderr).strip()}"

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
