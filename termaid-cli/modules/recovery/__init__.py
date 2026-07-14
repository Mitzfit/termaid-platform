"""Recovery Module — Boot into recovery/advanced startup. DANGEROUS tier.

Windows: wraps `shutdown /r /o` (reboot straight into the Advanced Startup
Options menu). Linux: reboots into the GRUB recovery entry if one exists.
`status` just checks whether a recovery path is available; `reboot` forces
an immediate restart of the whole machine — no different in effect from
pressing the power button mid-session, hence the confirm gate.

Commands (~2):
  /recovery status                    Is a recovery path available?
  /recovery reboot-to-recovery confirm   Force a reboot into recovery/advanced startup
  /recovery explain                        How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class RecoveryModule(Module):
    name = "recovery"
    version = "1.0.0"
    description = "Boot into recovery/advanced startup"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "reboot-to-recovery", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_status(self, arg=""):
        """Is a recovery path available?"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-Partition | Where-Object { $_.Type -eq 'Recovery' } | "
                     "Select-Object DriveLetter,Size | Format-Table -AutoSize"],
                    capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
                out = r.stdout.strip()
                return f"[recovery] Recovery partition(s):\n{out}" if out else "[recovery] No dedicated recovery partition found — Advanced Startup may still work via Windows Update–based recovery."
            else:
                r = subprocess.run(["grep", "-i", "recovery", "/boot/grub/grub.cfg"], capture_output=True,
                                    text=True, timeout=10)
                return f"[recovery] {'Recovery entry found in GRUB config.' if r.returncode == 0 else 'No recovery entry found in GRUB config.'}"
        except Exception as e:
            return f"[recovery] Failed: {e}"

    @safe
    def cmd_reboot_to_recovery(self, arg=""):
        """Force a reboot into recovery/advanced startup (confirms): /recovery reboot-to-recovery confirm"""
        if (arg or "").strip().lower() != "confirm":
            return "[recovery] This reboots the machine RIGHT NOW. Re-run as: /recovery reboot-to-recovery confirm"
        try:
            if sys.platform == "win32":
                r = subprocess.run(["shutdown", "/r", "/o", "/t", "5"], capture_output=True,
                                    text=True, timeout=15)
            else:
                r = subprocess.run(["systemctl", "reboot", "--boot-loader-menu=0"], capture_output=True,
                                    text=True, timeout=15)
        except Exception as e:
            return f"[recovery] Failed: {e}"
        if r.returncode != 0:
            return f"[recovery] {(r.stderr or r.stdout).strip()}"
        return "[recovery] Rebooting to recovery/advanced startup in ~5 seconds."

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
