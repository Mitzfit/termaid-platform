"""Boot Module — Consolidated boot configuration dashboard. DANGEROUS tier (read-only).

Read-only summary pulling from the same sources /uefi and /bootmgr use —
classified DANGEROUS alongside them since boot configuration details are
exactly what you'd want to know before making any of the changes those
two modules can make. Doesn't duplicate their write commands.

Commands (~2):
  /boot status         Boot mode, secure boot state, default entry, timeout
  /boot explain           How this module works
"""

import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class BootModule(Module):
    name = "boot"
    version = "1.0.0"
    description = "Consolidated boot configuration dashboard"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_status(self, arg=""):
        """Boot mode, secure boot state, default entry, timeout"""
        lines = ["[boot] Boot configuration:"]
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", "$env:firmware_type"],
                    capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
                lines.append(f"  Firmware type: {r.stdout.strip() or 'unknown'}")

                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Confirm-SecureBootUEFI -ErrorAction SilentlyContinue)"],
                    capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
                sb = r.stdout.strip()
                lines.append(f"  Secure Boot:   {'enabled' if sb == 'True' else 'disabled/unsupported' if sb == 'False' else 'unknown'}")

                r = subprocess.run(["bcdedit", "/enum", "{current}"], capture_output=True,
                                    text=True, timeout=8)
                for line in r.stdout.splitlines():
                    if line.strip().lower().startswith("description"):
                        lines.append(f"  Current OS:    {line.split(None, 1)[-1]}")
                        break
            else:
                if Path("/sys/firmware/efi").exists():
                    lines.append("  Firmware type: UEFI")
                else:
                    lines.append("  Firmware type: Legacy BIOS")
                sb_path = Path(
                    "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c")
                lines.append(f"  Secure Boot:   {'present (check value manually — needs root to read)' if sb_path.exists() else 'not applicable (BIOS) or unavailable'}")
        except Exception as e:
            lines.append(f"  (partial — {e})")
        lines.append("  See /uefi list and /bootmgr show for full detail.")
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
