"""Security Module — Full security posture audit. DANGEROUS tier (read-only).

Read-only despite the tier: it's classified DANGEROUS because a full
posture audit (firewall rules, Defender status, listening ports, UAC,
update status) reveals exactly what an attacker would want to know about
this machine's defenses, so it's gated the same as anything else that
touches host security configuration. For the quick one-line version plus
a couple of confirm-gated toggles, see /sec.

Commands (~2):
  /security audit         Full security posture report
  /security explain          How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _ps(script: str, timeout: int = 10):
    return subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")


class SecurityModule(Module):
    name = "security"
    version = "1.0.0"
    description = "Full security posture audit"
    author = "termaid"

    def on_load(self):
        for cmd in ["audit", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_audit(self, arg=""):
        """Full security posture report"""
        lines = ["=== Security Audit ===\n"]

        if sys.platform == "win32":
            try:
                r = _ps("(Get-NetFirewallProfile).Name + ':' + (Get-NetFirewallProfile).Enabled -join ' | '")
                lines.append(f"Firewall profiles: {r.stdout.strip() or 'unknown'}")
            except Exception:
                lines.append("Firewall profiles: unavailable")

            try:
                r = _ps("(Get-MpComputerStatus -ErrorAction SilentlyContinue).AntivirusEnabled")
                av = r.stdout.strip()
                lines.append(f"Defender antivirus: {'enabled' if av == 'True' else 'disabled/unknown'}")
            except Exception:
                lines.append("Defender antivirus: unavailable")

            try:
                r = _ps("(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
                        "-Name EnableLUA -ErrorAction SilentlyContinue).EnableLUA")
                val = r.stdout.strip()
                lines.append(f"UAC (EnableLUA): {'enabled' if val == '1' else 'disabled' if val == '0' else 'unknown'}")
            except Exception:
                lines.append("UAC: unavailable")

            try:
                r = _ps("(Get-Service wuauserv -ErrorAction SilentlyContinue).Status")
                lines.append(f"Windows Update service: {r.stdout.strip() or 'unknown'}")
            except Exception:
                lines.append("Windows Update service: unavailable")

            try:
                r = _ps("(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | "
                        "Measure-Object).Count")
                lines.append(f"Listening TCP ports: {r.stdout.strip() or 'unknown'}")
            except Exception:
                lines.append("Listening TCP ports: unavailable")
        else:
            try:
                r = subprocess.run(["systemctl", "is-active", "ufw"], capture_output=True,
                                    text=True, timeout=5)
                lines.append(f"ufw firewall: {r.stdout.strip() or 'not installed'}")
            except Exception:
                lines.append("ufw firewall: unavailable")
            try:
                r = subprocess.run(["ss", "-tln"], capture_output=True, text=True, timeout=5)
                count = max(0, len(r.stdout.splitlines()) - 1)
                lines.append(f"Listening TCP ports: {count}")
            except Exception:
                lines.append("Listening TCP ports: unavailable")

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
