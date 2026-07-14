"""FwOwn Module — Firmware/TPM ownership status + TPM clear. DANGEROUS tier.

Windows-focused: TPM ownership and Secure Boot state are the two things
that gate whether firmware-level security features are actually doing
anything. Clearing the TPM resets it to factory state — genuinely
destructive since it invalidates any keys/credentials sealed to that TPM
(BitLocker volumes, Windows Hello, some password managers' hardware-backed
storage), which can lock you out of your own encrypted data if you didn't
know what was relying on it. Confirm-gated for exactly that reason.

Commands (~2):
  /fwown status               TPM presence/ownership + Secure Boot state
  /fwown clear-tpm confirm      Clear the TPM to factory state
  /fwown explain                 How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class FwOwnModule(Module):
    name = "fwown"
    version = "1.0.0"
    description = "Firmware/TPM ownership status + TPM clear"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "clear-tpm", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_status(self, arg=""):
        """TPM presence/ownership + Secure Boot state"""
        if sys.platform != "win32":
            return "[fwown] TPM/Secure Boot status checks are Windows-specific in this module."
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Tpm | Select-Object TpmPresent,TpmReady,TpmEnabled,TpmOwned | Format-List"],
                capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
            tpm_info = r.stdout.strip() or "TPM info unavailable"

            r2 = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "(Confirm-SecureBootUEFI -ErrorAction SilentlyContinue)"],
                capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
            sb = r2.stdout.strip()
            sb_status = "enabled" if sb == "True" else "disabled/unsupported" if sb == "False" else "unknown"
        except Exception as e:
            return f"[fwown] Failed: {e}"
        return f"[fwown] {tpm_info}\nSecure Boot: {sb_status}"

    @safe
    def cmd_clear_tpm(self, arg=""):
        """Clear the TPM to factory state (confirms): /fwown clear-tpm confirm

        Invalidates anything sealed to the current TPM state (BitLocker,
        Windows Hello, hardware-backed credential stores)."""
        if (arg or "").strip().lower() != "confirm":
            return ("[fwown] This invalidates BitLocker/Windows Hello/hardware-backed credentials "
                    "sealed to this TPM. Re-run as: /fwown clear-tpm confirm")
        if sys.platform != "win32":
            return "[fwown] TPM clear is Windows-specific in this module."
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", "Clear-Tpm -ErrorAction Stop"],
                capture_output=True, text=True, timeout=30, encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[fwown] Failed: {e}"
        if r.returncode != 0:
            return f"[fwown] {(r.stderr or r.stdout).strip()}"
        return "[fwown] TPM clear requested — a restart may be required to complete it."

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
