"""UEFI Module — UEFI boot variable management. DANGEROUS tier.

Windows: reads via `bcdedit /enum firmware`; Linux: wraps `efibootmgr`.
Adding/removing boot entries touches firmware NVRAM directly — a botched
entry can leave a system needing a recovery boot to fix, hence the
confirm gate on both write operations. Viewing is unrestricted.

Commands (~3):
  /uefi list                        List UEFI boot entries
  /uefi add-entry <label> <path> confirm    Add a boot entry (Linux: efibootmgr; Windows: bcdedit)
  /uefi remove-entry <id> confirm             Remove a boot entry
  /uefi explain                                 How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class UefiModule(Module):
    name = "uefi"
    version = "1.0.0"
    description = "UEFI boot variable management"
    author = "termaid"

    def on_load(self):
        for cmd in ["list", "add-entry", "remove-entry", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_list(self, arg=""):
        """List UEFI boot entries"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(["bcdedit", "/enum", "firmware"], capture_output=True,
                                    text=True, timeout=10)
            else:
                r = subprocess.run(["efibootmgr", "-v"], capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            return "[uefi] Boot manager tool not found on this system (or this isn't a UEFI system)."
        except Exception as e:
            return f"[uefi] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[uefi] {out}" if out else "[uefi] No output."

    @safe
    def cmd_add_entry(self, arg=""):
        """Add a boot entry (confirms): /uefi add-entry <label> <path> confirm"""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[uefi] Usage: /uefi add-entry <label> <path> confirm"
        label, path = parts[0], parts[1]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["bcdedit", "/create", "/d", label, "/application", "bootsector"],
                                    capture_output=True, text=True, timeout=10)
            else:
                # path here is expected as "disk:partition:loader", e.g. "/dev/sda:1:\\EFI\\test\\test.efi"
                disk_part = path.split(":")
                if len(disk_part) != 3:
                    return "[uefi] Linux path must be '<disk>:<partition>:<loader path>', e.g. /dev/sda:1:\\EFI\\x\\x.efi"
                disk, part_num, loader = disk_part
                r = subprocess.run(["efibootmgr", "-c", "-d", disk, "-p", part_num, "-L", label, "-l", loader],
                                    capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            return "[uefi] Boot manager tool not found on this system."
        except Exception as e:
            return f"[uefi] Failed: {e}"
        return f"[uefi] {(r.stdout or r.stderr).strip()}"

    @safe
    def cmd_remove_entry(self, arg=""):
        """Remove a boot entry (confirms): /uefi remove-entry <id> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[uefi] Usage: /uefi remove-entry <id> confirm"
        entry_id = parts[0]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["bcdedit", "/delete", entry_id], capture_output=True,
                                    text=True, timeout=10)
            else:
                r = subprocess.run(["efibootmgr", "-b", entry_id, "-B"], capture_output=True,
                                    text=True, timeout=10)
        except FileNotFoundError:
            return "[uefi] Boot manager tool not found on this system."
        except Exception as e:
            return f"[uefi] Failed: {e}"
        return f"[uefi] {(r.stdout or r.stderr).strip() or f'Removed entry {entry_id}'}"

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
