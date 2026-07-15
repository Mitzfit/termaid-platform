"""Firewall Module — Firewall rule management. SYSTEM tier.

Windows: wraps `netsh advfirewall`. Linux: wraps `ufw`. Both take plain
command-line arguments directly — no PowerShell `-Command` string is ever
built, so there's no string-interpolation-into-a-shell risk to guard
against here at all (unlike /vm, /device, /disktool). Listing rules is
unrestricted; adding/removing a rule confirms first since a wrong rule can
either lock out legitimate traffic or open a port you didn't mean to.

Commands (~4):
  /firewall list-rules                                    List current firewall rules
  /firewall add-rule <name> <in|out> <allow|block> <port> [tcp|udp] confirm  Add a rule
  /firewall remove-rule <name> confirm                       Remove a rule by name
  /firewall explain                                             How this module works
"""

import shutil
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class FirewallModule(Module):
    name = "firewall"
    version = "1.0.0"
    description = "Firewall rule management (netsh advfirewall / ufw)"
    author = "termaid"

    def on_load(self):
        for cmd in ["list-rules", "add-rule", "remove-rule", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_list_rules(self, arg=""):
        """List current firewall rules"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", "name=all"],
                                    capture_output=True, text=True, timeout=20)
                out = r.stdout.strip()
                # netsh dumps everything including built-in rules; keep it manageable.
                lines = out.splitlines()
                if len(lines) > 300:
                    out = "\n".join(lines[:300]) + f"\n... ({len(lines) - 300} more lines, netsh includes built-in rules)"
            else:
                if not shutil.which("ufw"):
                    return "[firewall] ufw not installed."
                r = subprocess.run(["ufw", "status", "numbered"], capture_output=True, text=True, timeout=10)
                out = r.stdout.strip()
        except Exception as e:
            return f"[firewall] Failed: {e}"
        return f"[firewall] {out or 'No rules found.'}"

    @safe
    def cmd_add_rule(self, arg=""):
        """Add a rule (confirms): /firewall add-rule <name> <in|out> <allow|block> <port> [tcp|udp] confirm"""
        parts = (arg or "").split()
        if len(parts) < 5 or parts[-1].lower() != "confirm":
            return "[firewall] Usage: /firewall add-rule <name> <in|out> <allow|block> <port> [tcp|udp] confirm"
        name, direction, action, port = parts[0], parts[1].lower(), parts[2].lower(), parts[3]
        protocol = parts[4].lower() if len(parts) == 6 else "tcp"
        if direction not in ("in", "out"):
            return "[firewall] Direction must be 'in' or 'out'"
        if action not in ("allow", "block"):
            return "[firewall] Action must be 'allow' or 'block'"
        try:
            if sys.platform == "win32":
                netsh_dir = "in" if direction == "in" else "out"
                netsh_action = "allow" if action == "allow" else "block"
                r = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "add", "rule",
                     f"name={name}", f"dir={netsh_dir}", f"action={netsh_action}",
                     f"protocol={protocol.upper()}", f"localport={port}"],
                    capture_output=True, text=True, timeout=15)
            else:
                if not shutil.which("ufw"):
                    return "[firewall] ufw not installed."
                ufw_action = "allow" if action == "allow" else "deny"
                spec = f"{port}/{protocol}"
                args = ["ufw", ufw_action]
                if direction == "out":
                    args += ["out"]
                args += [spec]
                r = subprocess.run(args, capture_output=True, text=True, timeout=15)
        except Exception as e:
            return f"[firewall] Failed: {e}"
        if r.returncode != 0:
            return f"[firewall] {(r.stderr or r.stdout).strip()}"
        return f"[firewall] Added rule '{name}': {direction} {action} port {port}/{protocol}"

    @safe
    def cmd_remove_rule(self, arg=""):
        """Remove a rule by name (confirms): /firewall remove-rule <name> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[firewall] Usage: /firewall remove-rule <name> confirm"
        name = parts[0]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["netsh", "advfirewall", "firewall", "delete", "rule", f"name={name}"],
                                    capture_output=True, text=True, timeout=15)
            else:
                if not shutil.which("ufw"):
                    return "[firewall] ufw not installed. Use 'ufw status numbered' + 'ufw delete <n>' directly for rule-number-based deletes."
                return "[firewall] ufw deletes rules by number, not name — run /firewall list-rules to find the number, then use /syscmd to run 'ufw delete <n>' if you have that module enabled."
        except Exception as e:
            return f"[firewall] Failed: {e}"
        if r.returncode != 0:
            return f"[firewall] {(r.stderr or r.stdout).strip()}"
        return f"[firewall] Removed rule '{name}'"

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
