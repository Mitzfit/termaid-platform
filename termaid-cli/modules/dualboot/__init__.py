"""DualBoot Module — Guided dual-boot setup helper. DANGEROUS tier.

Informational + detection only — this module does not partition disks or
install an OS itself (that's exactly the kind of irreversible, easy-to-
get-wrong operation /disktool already gates hard). What it does: report
the current disk/boot layout so you know what you're working with, and
walk through the general shape of a dual-boot setup so /disktool and
/bootmgr get used with the right plan instead of blind trial and error.

Commands (~2):
  /dualboot check          Current disk layout + free space relevant to dual-booting
  /dualboot guide             General dual-boot setup walkthrough
  /dualboot explain               How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_GUIDE = (
    "Setting up dual-boot, in general:\n"
    "  1. Check current layout: /dualboot check — you need enough unpartitioned free space\n"
    "     (or a partition you're willing to shrink) for the second OS.\n"
    "  2. Back up everything first — resizing partitions is usually safe but not risk-free.\n"
    "  3. Shrink an existing partition to free up space, using the OS's own disk management tool\n"
    "     (not /disktool format, which erases rather than resizes).\n"
    "  4. Install the second OS into the freed space, choosing 'install alongside' if the installer\n"
    "     offers it, or manually pointing it at the new partition.\n"
    "  5. Most modern installers (Windows, most Linux distros) auto-configure the boot menu, but\n"
    "     verify with /bootmgr show and /uefi list afterward; fix the default entry with\n"
    "     /bootmgr set-default if the wrong OS boots by default.\n"
    "This is the single highest-risk-of-support-headache setup in this whole tier if a partition\n"
    "resize goes wrong — a fresh backup before step 3 is not optional."
)


class DualBootModule(Module):
    name = "dualboot"
    version = "1.0.0"
    description = "Guided dual-boot setup helper (informational — doesn't partition or install anything)"
    author = "termaid"

    def on_load(self):
        for cmd in ["check", "guide", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_check(self, arg=""):
        """Current disk layout + free space relevant to dual-booting"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-Partition | Select-Object DiskNumber,PartitionNumber,DriveLetter,Size,Type | "
                     "Format-Table -AutoSize"],
                    capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(["lsblk", "-o", "NAME,SIZE,FSTYPE,MOUNTPOINT"], capture_output=True,
                                    text=True, timeout=10)
        except Exception as e:
            return f"[dualboot] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[dualboot] Current layout:\n{out}\n\nSee /dualboot guide for the setup walkthrough." if out else "[dualboot] No layout info available."

    @safe
    def cmd_guide(self, arg=""):
        """General dual-boot setup walkthrough"""
        return f"[dualboot] {_GUIDE}"

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
