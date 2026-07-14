"""Fastboot Module — Android Fastboot wrapper. DANGEROUS tier.

The highest-stakes module in this batch: `flash` writes directly to a
device partition, and a wrong partition name or a bad image can brick the
device (render it unable to boot). `unlock` is separately destructive in
a different way — it wipes all user data on most devices as a side effect
and can void warranty. Both require the confirm gate plus an extra
explicit acknowledgement string, not just "confirm", given the
irreversibility.

Commands (~4):
  /fastboot devices                          List connected devices in fastboot mode
  /fastboot reboot confirm                     Reboot out of fastboot mode
  /fastboot flash <partition> <image> I-UNDERSTAND-THIS-CAN-BRICK-THE-DEVICE
                                                  Flash an image to a partition
  /fastboot unlock I-UNDERSTAND-THIS-WIPES-THE-DEVICE
                                                  Unlock the bootloader (wipes data)
  /fastboot explain                                How this module works
"""

import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_FLASH_ACK = "I-UNDERSTAND-THIS-CAN-BRICK-THE-DEVICE"
_UNLOCK_ACK = "I-UNDERSTAND-THIS-WIPES-THE-DEVICE"


class FastbootModule(Module):
    name = "fastboot"
    version = "1.0.0"
    description = "Android Fastboot wrapper (flash/unlock are irreversible — extra ack required)"
    author = "termaid"

    def on_load(self):
        for cmd in ["devices", "reboot", "flash", "unlock", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _available(self) -> bool:
        return shutil.which("fastboot") is not None

    @safe
    def cmd_devices(self, arg=""):
        """List connected devices in fastboot mode"""
        if not self._available():
            return "[fastboot] fastboot not found — install Android Platform Tools."
        try:
            r = subprocess.run(["fastboot", "devices"], capture_output=True, text=True, timeout=15)
        except Exception as e:
            return f"[fastboot] Failed: {e}"
        return f"[fastboot] {r.stdout.strip() or '(no devices found)'}"

    @safe
    def cmd_reboot(self, arg=""):
        """Reboot out of fastboot mode (confirms): /fastboot reboot confirm"""
        if (arg or "").strip().lower() != "confirm":
            return "[fastboot] Re-run as: /fastboot reboot confirm"
        if not self._available():
            return "[fastboot] fastboot not found — install Android Platform Tools."
        try:
            r = subprocess.run(["fastboot", "reboot"], capture_output=True, text=True, timeout=15)
        except Exception as e:
            return f"[fastboot] Failed: {e}"
        return f"[fastboot] {(r.stdout or r.stderr).strip() or 'Reboot command sent.'}"

    @safe
    def cmd_flash(self, arg=""):
        """Flash an image to a partition (irreversible — extra ack required):
        /fastboot flash <partition> <image> I-UNDERSTAND-THIS-CAN-BRICK-THE-DEVICE"""
        parts = (arg or "").split()
        if len(parts) != 3 or parts[2] != _FLASH_ACK:
            return (f"[fastboot] A wrong partition or bad image can permanently brick the device. "
                    f"Re-run as: /fastboot flash <partition> <image> {_FLASH_ACK}")
        partition, image = parts[0], parts[1]
        if not self._available():
            return "[fastboot] fastboot not found — install Android Platform Tools."
        try:
            r = subprocess.run(["fastboot", "flash", partition, image], capture_output=True,
                                text=True, timeout=180)
        except subprocess.TimeoutExpired:
            return "[fastboot] Flash timed out after 180s — do not disconnect the device."
        except Exception as e:
            return f"[fastboot] Failed: {e}"
        return f"[fastboot] {(r.stdout or r.stderr).strip()}"

    @safe
    def cmd_unlock(self, arg=""):
        """Unlock the bootloader — wipes device data (extra ack required):
        /fastboot unlock I-UNDERSTAND-THIS-WIPES-THE-DEVICE"""
        if (arg or "").strip() != _UNLOCK_ACK:
            return f"[fastboot] This wipes all data on the device and may void warranty. Re-run as: /fastboot unlock {_UNLOCK_ACK}"
        if not self._available():
            return "[fastboot] fastboot not found — install Android Platform Tools."
        try:
            r = subprocess.run(["fastboot", "flashing", "unlock"], capture_output=True,
                                text=True, timeout=30)
        except Exception as e:
            return f"[fastboot] Failed: {e}"
        return f"[fastboot] {(r.stdout or r.stderr).strip()} — confirm any on-device prompt to complete."

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
