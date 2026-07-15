"""Security Module — Full security posture audit AND control. DANGEROUS tier.

Read checks (`audit`/`score`) are unrestricted; every write action confirms
first, and BitLocker specifically needs a stronger explicit acknowledgement
than a bare "confirm" — enabling disk encryption without a backed-up
recovery key is one of the few ways this whole codebase can genuinely lock
you out of your own data, the same class of irreversibility as
/fastboot's flash or /disktool's format. `disable` is deliberately the
scarier of the two directions (turning OFF a protection) and says so in
its own confirmation prompt.

Commands (~6):
  /security audit                     Full security posture report (read-only)
  /security score                        Quick pass/fail count across every check
  /security enable <check> confirm          Turn ON a protection: firewall, defender, uac, block-smb1, disable-guest, block-rdp
  /security disable <check> confirm            Turn OFF a protection (same check names) — this weakens security, not hardens it
  /security bitlocker-enable I-HAVE-BACKED-UP-MY-RECOVERY-KEY
                                                   Enable BitLocker on the system drive
  /security harden confirm                          Apply every safe recommended fix in one pass (excludes BitLocker)
  /security explain                                    How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_BITLOCKER_ACK = "I-HAVE-BACKED-UP-MY-RECOVERY-KEY"


def _ps(script: str, timeout: int = 15):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")


class SecurityModule(Module):
    name = "security"
    version = "1.2.0"
    description = "Full security posture audit AND control"
    author = "termaid"

    def on_load(self):
        for cmd in ["audit", "score", "enable", "disable", "bitlocker-enable", "harden", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    def _checks_windows(self):
        """Returns a list of (label, status_str, is_good_or_none) tuples."""
        checks = []

        try:
            r = _ps("(Get-NetFirewallProfile).Name + ':' + (Get-NetFirewallProfile).Enabled -join ' | '")
            out = r.stdout.strip()
            checks.append(("Firewall profiles", out or "unknown", "False" not in out if out else None))
        except Exception:
            checks.append(("Firewall profiles", "unavailable", None))

        try:
            r = _ps("(Get-MpComputerStatus -ErrorAction SilentlyContinue).AntivirusEnabled")
            av = r.stdout.strip()
            checks.append(("Defender antivirus", "enabled" if av == "True" else "disabled/unknown", av == "True" or None))
        except Exception:
            checks.append(("Defender antivirus", "unavailable", None))

        try:
            r = _ps("Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntiVirusProduct "
                    "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty displayName")
            products = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            checks.append(("Registered AV products", ", ".join(products) if products else "none registered", bool(products) or None))
        except Exception:
            checks.append(("Registered AV products", "unavailable", None))

        try:
            r = _ps("(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
                    "-Name EnableLUA -ErrorAction SilentlyContinue).EnableLUA")
            val = r.stdout.strip()
            checks.append(("UAC (EnableLUA)", "enabled" if val == "1" else "disabled" if val == "0" else "unknown", val == "1" or None))
        except Exception:
            checks.append(("UAC", "unavailable", None))

        try:
            r = _ps("(Get-Service wuauserv -ErrorAction SilentlyContinue).Status")
            status = r.stdout.strip()
            checks.append(("Windows Update service", status or "unknown", status == "Running" or None))
        except Exception:
            checks.append(("Windows Update service", "unavailable", None))

        try:
            r = _ps("(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Measure-Object).Count")
            checks.append(("Listening TCP ports", r.stdout.strip() or "unknown", None))
        except Exception:
            checks.append(("Listening TCP ports", "unavailable", None))

        try:
            r = _ps("(Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction SilentlyContinue).ProtectionStatus")
            val = r.stdout.strip()
            checks.append(("BitLocker (system drive)", "on" if val == "1" else "off" if val == "0" else "unavailable (not Pro/Enterprise?)",
                          val == "1" if val in ("0", "1") else None))
        except Exception:
            checks.append(("BitLocker", "unavailable", None))

        try:
            r = _ps("(Get-ItemProperty 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' "
                    "-Name fDenyTSConnections -ErrorAction SilentlyContinue).fDenyTSConnections")
            val = r.stdout.strip()
            checks.append(("Remote Desktop (RDP)", "disabled" if val == "1" else "ENABLED" if val == "0" else "unknown",
                          val == "1" if val in ("0", "1") else None))
        except Exception:
            checks.append(("Remote Desktop (RDP)", "unavailable", None))

        try:
            r = _ps("(Get-SmbServerConfiguration -ErrorAction SilentlyContinue).EnableSMB1Protocol")
            val = r.stdout.strip()
            checks.append(("SMBv1 protocol", "disabled" if val == "False" else "ENABLED (legacy, vulnerable)" if val == "True" else "unknown",
                          val == "False" if val in ("True", "False") else None))
        except Exception:
            checks.append(("SMBv1 protocol", "unavailable", None))

        try:
            r = _ps("(Get-LocalUser -Name 'Guest' -ErrorAction SilentlyContinue).Enabled")
            val = r.stdout.strip()
            checks.append(("Guest account", "disabled" if val == "False" else "ENABLED" if val == "True" else "not found",
                          val == "False" if val in ("True", "False") else None))
        except Exception:
            checks.append(("Guest account", "unavailable", None))

        try:
            r = _ps("Get-SmbShare -ErrorAction SilentlyContinue | Where-Object { $_.Name -notlike '*$' } | "
                    "Select-Object -ExpandProperty Name")
            shares = [l.strip() for l in r.stdout.splitlines() if l.strip()]
            checks.append(("Non-admin network shares", ", ".join(shares) if shares else "none", not shares or None))
        except Exception:
            checks.append(("Network shares", "unavailable", None))

        return checks

    def _checks_linux(self):
        checks = []
        try:
            r = subprocess.run(["systemctl", "is-active", "ufw"], capture_output=True, text=True, timeout=5)
            status = r.stdout.strip()
            checks.append(("ufw firewall", status or "not installed", status == "active" or None))
        except Exception:
            checks.append(("ufw firewall", "unavailable", None))
        try:
            r = subprocess.run(["ss", "-tln"], capture_output=True, text=True, timeout=5)
            count = max(0, len(r.stdout.splitlines()) - 1)
            checks.append(("Listening TCP ports", str(count), None))
        except Exception:
            checks.append(("Listening TCP ports", "unavailable", None))
        try:
            r = subprocess.run(["systemctl", "is-active", "sshd"], capture_output=True, text=True, timeout=5)
            checks.append(("sshd", r.stdout.strip() or "not installed", None))
        except Exception:
            checks.append(("sshd", "unavailable", None))
        try:
            import os
            luks = os.path.exists("/dev/mapper") and bool(os.listdir("/dev/mapper"))
            checks.append(("LUKS/mapper devices present", "yes" if luks else "no (may not be full-disk-encrypted)", luks or None))
        except Exception:
            checks.append(("Disk encryption", "unavailable", None))
        return checks

    @safe
    def cmd_audit(self, arg=""):
        """Full security posture report (read-only)"""
        checks = self._checks_windows() if sys.platform == "win32" else self._checks_linux()
        lines = ["=== Security Audit ===\n"]
        for label, status, _ in checks:
            lines.append(f"{label}: {status}")
        return "\n".join(lines)

    @safe
    def cmd_score(self, arg=""):
        """Quick pass/fail count across every check"""
        checks = self._checks_windows() if sys.platform == "win32" else self._checks_linux()
        good = sum(1 for _, _, ok in checks if ok is True)
        bad = sum(1 for _, _, ok in checks if ok is False)
        unknown = sum(1 for _, _, ok in checks if ok is None)
        lines = [f"[security] {good} good, {bad} concerning, {unknown} unknown (of {len(checks)} checks)"]
        for label, status, ok in checks:
            if ok is False:
                lines.append(f"  CONCERN  {label}: {status}")
        if bad == 0:
            lines.append("  No concerning findings.")
        return "\n".join(lines)

    def _apply(self, check: str, turn_on: bool) -> str:
        """Windows-only actuator for a named check. Returns a result message."""
        if sys.platform != "win32":
            return "[security] Write actions are Windows-specific in this module — use /sec firewall on Linux, or the platform's own tools for the rest."

        if check == "firewall":
            flag = "true" if turn_on else "false"
            r = _ps(f"Set-NetFirewallProfile -All -Enabled {flag}")
        elif check == "defender":
            flag = "$false" if turn_on else "$true"
            r = _ps(f"Set-MpPreference -DisableRealtimeMonitoring {flag}")
        elif check == "uac":
            val = "1" if turn_on else "0"
            r = _ps("Set-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
                    f"-Name EnableLUA -Value {val}")
        elif check in ("block-smb1", "allow-smb1"):
            flag = "$false" if turn_on else "$true"
            r = _ps(f"Set-SmbServerConfiguration -EnableSMB1Protocol {flag} -Force")
        elif check in ("disable-guest", "enable-guest"):
            verb = "Disable-LocalUser" if turn_on else "Enable-LocalUser"
            r = _ps(f"{verb} -Name 'Guest'")
        elif check in ("block-rdp", "allow-rdp"):
            val = "1" if turn_on else "0"
            r = _ps("Set-ItemProperty -Path 'HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Terminal Server' "
                    f"-Name fDenyTSConnections -Value {val}")
        else:
            return (f"[security] Unknown check '{check}'. Choose from: firewall, defender, uac, "
                    "block-smb1/allow-smb1, disable-guest/enable-guest, block-rdp/allow-rdp")

        if r.returncode != 0:
            return f"[security] {(r.stderr or r.stdout).strip()}"
        return f"[security] Applied: {check} ({'on' if turn_on else 'off'})"

    @safe
    def cmd_enable(self, arg=""):
        """Turn ON a protection (confirms): /security enable <check> confirm

        Checks: firewall, defender, uac, block-smb1, disable-guest, block-rdp"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[security] Usage: /security enable <check> confirm"
        return self._apply(parts[0].lower(), turn_on=True)

    @safe
    def cmd_disable(self, arg=""):
        """Turn OFF a protection — this WEAKENS security (confirms): /security disable <check> confirm

        Checks: firewall, defender, uac, allow-smb1, enable-guest, allow-rdp"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return ("[security] This turns OFF a protection, not on — double check that's really what you want. "
                    "Re-run as: /security disable <check> confirm")
        return self._apply(parts[0].lower(), turn_on=False)

    @safe
    def cmd_bitlocker_enable(self, arg=""):
        """Enable BitLocker on the system drive (extra ack required):
        /security bitlocker-enable I-HAVE-BACKED-UP-MY-RECOVERY-KEY

        Without a saved recovery key, a hardware change or Windows repair can
        permanently lock you out of the drive — this is not a reversible toggle."""
        if sys.platform != "win32":
            return "[security] BitLocker is Windows-specific."
        if (arg or "").strip() != _BITLOCKER_ACK:
            return (f"[security] This encrypts your system drive — losing the recovery key means losing the data. "
                    f"Back it up first, then re-run as: /security bitlocker-enable {_BITLOCKER_ACK}")
        try:
            r = _ps("Enable-BitLocker -MountPoint $env:SystemDrive -RecoveryPasswordProtector -ErrorAction Stop",
                    timeout=60)
        except subprocess.TimeoutExpired:
            return "[security] BitLocker enable is running in the background but didn't finish within 60s — check /security audit shortly."
        except Exception as e:
            return f"[security] Failed: {e}"
        if r.returncode != 0:
            return f"[security] {(r.stderr or r.stdout).strip()}"
        return ("[security] BitLocker encryption started. Find the recovery key with: "
                "(Get-BitLockerVolume -MountPoint $env:SystemDrive).KeyProtector — save it somewhere safe, now.")

    @safe
    def cmd_harden(self, arg=""):
        """Apply every safe recommended fix in one pass, excludes BitLocker (confirms): /security harden confirm"""
        if (arg or "").strip().lower() != "confirm":
            return ("[security] This applies every recommended fix below at once (firewall on, Defender on, UAC on, "
                    "SMBv1 off, Guest account off, RDP off) — BitLocker is excluded since it needs its own explicit "
                    "acknowledgement (/security bitlocker-enable). Re-run as: /security harden confirm")
        if sys.platform != "win32":
            return "[security] harden is Windows-specific in this module."
        results = []
        for check in ("firewall", "defender", "uac", "block-smb1", "disable-guest", "block-rdp"):
            results.append(self._apply(check, turn_on=True))
        return "[security] Hardening pass:\n" + "\n".join(f"  {r.replace('[security] ', '')}" for r in results)

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
