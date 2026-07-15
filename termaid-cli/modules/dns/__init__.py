"""DNS Module — Resolver management. SYSTEM tier.

`set` validates every address with Python's stdlib `ipaddress` module
*before* it ever reaches a PowerShell command string — the same lesson
from /netscan's and /vm's injection fixes applies here: validate the
narrow shape a value actually needs (a real IPv4/IPv6 address) rather than
trusting it, since embedding an unvalidated string into a `-Command`
string is exactly how that class of bug happened before.

Commands (~4):
  /dns current                         Current DNS servers per active adapter
  /dns presets                           Well-known public resolvers, for reference
  /dns set <ip> [ip2] confirm              Set DNS servers on the active adapter
  /dns flush                                 Flush the local DNS cache
  /dns explain                                 How this module works
"""

import ipaddress
import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_PRESETS = {
    "cloudflare": ["1.1.1.1", "1.0.0.1"],
    "google": ["8.8.8.8", "8.8.4.4"],
    "quad9": ["9.9.9.9", "149.112.112.112"],
    "opendns": ["208.67.222.222", "208.67.220.220"],
}


def _valid_ip(s: str) -> bool:
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False


class DnsModule(Module):
    name = "dns"
    version = "1.0.0"
    description = "DNS resolver management"
    author = "termaid"

    def on_load(self):
        for cmd in ["current", "presets", "set", "flush", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _active_interface_alias(self):
        """Best-effort: the Windows interface alias with a default route."""
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
                 "Sort-Object -Property RouteMetric | Select-Object -First 1).InterfaceAlias"],
                capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
            alias = r.stdout.strip()
            return alias or None
        except Exception:
            return None

    @safe
    def cmd_current(self, arg=""):
        """Current DNS servers per active adapter"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-DnsClientServerAddress -AddressFamily IPv4 | "
                     "Where-Object { $_.ServerAddresses } | "
                     "Select-Object InterfaceAlias,ServerAddresses | Format-Table -AutoSize"],
                    capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
                out = r.stdout.strip()
            else:
                resolv = Path("/etc/resolv.conf")
                out = resolv.read_text(errors="replace").strip() if resolv.exists() else ""
        except Exception as e:
            return f"[dns] Failed: {e}"
        return f"[dns] {out or 'No DNS servers found.'}"

    @safe
    def cmd_presets(self, arg=""):
        """Well-known public resolvers, for reference"""
        lines = ["[dns] Public resolvers:"]
        for name, ips in _PRESETS.items():
            lines.append(f"  {name:12s} {', '.join(ips)}")
        lines.append("\n  /dns set <ip> [ip2] confirm — e.g. /dns set 1.1.1.1 1.0.0.1 confirm")
        return "\n".join(lines)

    @safe
    def cmd_set(self, arg=""):
        """Set DNS servers on the active adapter (confirms): /dns set <ip> [ip2] confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[-1].lower() != "confirm":
            return "[dns] Usage: /dns set <ip> [ip2] confirm (see /dns presets for common choices)"
        ips = parts[:-1]
        if len(ips) > 2:
            return "[dns] At most 2 addresses (primary + secondary)."
        for ip in ips:
            if not _valid_ip(ip):
                return f"[dns] '{ip}' is not a valid IP address."

        try:
            if sys.platform == "win32":
                alias = self._active_interface_alias()
                if not alias:
                    return "[dns] Could not determine the active network adapter."
                ip_list = ",".join(f"'{ip}'" for ip in ips)  # each element already IP-validated above
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Set-DnsClientServerAddress -InterfaceAlias '{alias}' -ServerAddresses {ip_list}"],
                    capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            else:
                resolv = Path("/etc/resolv.conf")
                content = "".join(f"nameserver {ip}\n" for ip in ips)
                resolv.write_text(content)
                r = subprocess.CompletedProcess([], 0, "", "")
        except Exception as e:
            return f"[dns] Failed: {e}"
        if r.returncode != 0:
            return f"[dns] {(r.stderr or r.stdout).strip()}"
        return f"[dns] DNS set to {', '.join(ips)}"

    @safe
    def cmd_flush(self, arg=""):
        """Flush the local DNS cache"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, timeout=10)
            else:
                r = subprocess.run(["resolvectl", "flush-caches"], capture_output=True, text=True, timeout=10)
        except FileNotFoundError:
            return "[dns] No known DNS cache-flush tool found on this system."
        except Exception as e:
            return f"[dns] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[dns] {out or 'DNS cache flushed.'}"

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
