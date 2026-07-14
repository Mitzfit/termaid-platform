"""MultiBoot Module — 3+ OS boot menu overview + guidance. DANGEROUS tier.

Where /dualboot covers the two-OS case, this is the same idea scaled up:
read-only listing of every boot entry currently configured (delegating to
the same sources /uefi and /bootmgr use) plus guidance for managing a menu
with several entries, since boot menu timeout/ordering mistakes get more
confusing as entries increase. No write commands of its own — /bootmgr
and /uefi already own those.

Commands (~2):
  /multiboot list-entries       Every configured boot entry
  /multiboot guide                General guidance for managing 3+ boot entries
  /multiboot explain                 How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_GUIDE = (
    "Managing a boot menu with 3+ entries:\n"
    "  - List everything currently configured: /multiboot list-entries\n"
    "  - Set which one boots by default: /bootmgr set-default <id> confirm\n"
    "  - Give yourself enough time to pick at boot: /bootmgr set-timeout <seconds> confirm\n"
    "    (0 means no menu shown at all — easy to accidentally lock yourself into always booting\n"
    "    the default with no way to pick another OS without a rescue disk)\n"
    "  - Remove stale entries (uninstalled OSes, old kernel versions) with /uefi remove-entry\n"
    "    to keep the menu from growing unmanageably — each OS's own installer/updater often adds\n"
    "    a new entry rather than replacing the old one."
)


class MultiBootModule(Module):
    name = "multiboot"
    version = "1.0.0"
    description = "3+ OS boot menu overview + guidance"
    author = "termaid"

    def on_load(self):
        for cmd in ["list-entries", "guide", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_list_entries(self, arg=""):
        """Every configured boot entry"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(["bcdedit", "/enum"], capture_output=True, text=True, timeout=10)
            else:
                r = subprocess.run(["efibootmgr", "-v"], capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            return "[multiboot] Boot manager tool not found on this system."
        except Exception as e:
            return f"[multiboot] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[multiboot] {out}" if out else "[multiboot] No boot entries found."

    @safe
    def cmd_guide(self, arg=""):
        """General guidance for managing 3+ boot entries"""
        return f"[multiboot] {_GUIDE}"

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
