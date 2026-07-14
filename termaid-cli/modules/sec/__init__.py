"""Sec Module — Quick security status + firewall toggle. DANGEROUS tier.

The one-line companion to /security's full audit: a fast status check plus
the ability to actually turn the firewall on or off, which is why this one
(unlike /security) needs a confirm gate — disabling a firewall is a real,
consequential change, not just a report.

Commands (~2):
  /sec status                Quick one-line security posture
  /sec firewall <on|off> confirm   Enable or disable the firewall
  /sec explain                       How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class SecModule(Module):
    name = "sec"
    version = "1.0.0"
    description = "Quick security status + firewall toggle"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "firewall", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_status(self, arg=""):
        """Quick one-line security posture"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-NetFirewallProfile -Profile Public).Enabled"],
                    capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
                fw = "on" if r.stdout.strip() == "True" else "off"
            else:
                r = subprocess.run(["systemctl", "is-active", "ufw"], capture_output=True,
                                    text=True, timeout=5)
                fw = "on" if r.stdout.strip() == "active" else "off"
        except Exception:
            fw = "unknown"
        return f"[sec] Firewall: {fw}. Run /security audit for the full picture."

    @safe
    def cmd_firewall(self, arg=""):
        """Enable or disable the firewall (confirms): /sec firewall <on|off> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[0].lower() not in ("on", "off") or parts[1].lower() != "confirm":
            return "[sec] Usage: /sec firewall <on|off> confirm"
        state = parts[0].lower()
        try:
            if sys.platform == "win32":
                flag = "true" if state == "on" else "false"
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Set-NetFirewallProfile -All -Enabled {flag}"],
                    capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(["ufw", state], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[sec] Failed: {e}"
        if r.returncode != 0:
            return f"[sec] {(r.stderr or r.stdout).strip()}"
        return f"[sec] Firewall turned {state}"

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
