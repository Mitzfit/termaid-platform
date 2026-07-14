"""RootGuide Module — Guided Android rooting walkthrough. DANGEROUS tier.

Informational — this module does not root a device itself (that's a
device-specific process, typically bootloader unlock + custom recovery +
a root solution like Magisk, and doing it wrong can brick the device or
trip a hardware fuse that voids warranty permanently). What it does: check
the connected device's current state via adb/fastboot and give concrete,
device-aware next steps, and hand off to /fastboot and /adb for the actual
mechanical steps once you know what they are.

Commands (~2):
  /rootguide guide            General rooting walkthrough (stage overview)
  /rootguide check-device       Connected device's current bootloader/root state
  /rootguide explain               How this module works
"""

import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_GUIDE = (
    "Rooting an Android device, in general (specifics vary a LOT by manufacturer/model):\n"
    "  1. Back up everything — most bootloader unlocks wipe all user data.\n"
    "  2. Enable Developer Options + USB debugging + OEM unlocking on the device.\n"
    "  3. Check current state: /rootguide check-device\n"
    "  4. Unlock the bootloader: /fastboot unlock (irreversible, wipes data, may trip a warranty fuse).\n"
    "  5. Flash a patched boot image or recovery (Magisk is the common modern approach) via /fastboot flash.\n"
    "  6. Verify root with a root-checker app, then re-lock the bootloader only if your specific "
    "device/ROM supports staying rooted with a locked bootloader (most don't).\n"
    "This is device-specific enough that you should find your exact model's guide before step 4 — "
    "generic steps applied to the wrong device are how devices get bricked."
)


class RootGuideModule(Module):
    name = "rootguide"
    version = "1.0.0"
    description = "Guided Android rooting walkthrough (informational — doesn't root anything itself)"
    author = "termaid"

    def on_load(self):
        for cmd in ["guide", "check-device", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_guide(self, arg=""):
        """General rooting walkthrough (stage overview)"""
        return f"[rootguide] {_GUIDE}"

    @safe
    def cmd_check_device(self, arg=""):
        """Connected device's current bootloader/root state"""
        if not shutil.which("adb") and not shutil.which("fastboot"):
            return "[rootguide] Neither adb nor fastboot found — install Android Platform Tools first."
        lines = []
        if shutil.which("adb"):
            try:
                r = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=15)
                lines.append(f"adb devices:\n{r.stdout.strip()}")
                r2 = subprocess.run(["adb", "shell", "getprop", "ro.boot.verifiedbootstate"],
                                    capture_output=True, text=True, timeout=15)
                if r2.stdout.strip():
                    lines.append(f"Verified boot state: {r2.stdout.strip()}")
            except Exception as e:
                lines.append(f"adb check failed: {e}")
        if shutil.which("fastboot"):
            try:
                r = subprocess.run(["fastboot", "devices"], capture_output=True, text=True, timeout=15)
                if r.stdout.strip():
                    lines.append(f"fastboot devices:\n{r.stdout.strip()}")
                    r2 = subprocess.run(["fastboot", "getvar", "unlocked"], capture_output=True,
                                        text=True, timeout=15)
                    lines.append((r2.stdout + r2.stderr).strip())
            except Exception as e:
                lines.append(f"fastboot check failed: {e}")
        return "[rootguide] " + ("\n".join(lines) if lines else "No device detected — connect it and enable USB debugging.")

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
