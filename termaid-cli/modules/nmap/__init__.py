"""Nmap Module — Direct nmap scan control. SYSTEM tier.

/netscan already shells out to nmap for its basic subnet discovery scan;
this gives direct access to nmap's other scan types instead of hiding
behind netscan's fixed defaults. List-form subprocess args throughout
(no shell string ever constructed), so target/port arguments can't reach
a shell regardless of content — same discipline as /nettools.

Commands (~5):
  /nmap ping-scan <target>                 Host discovery only, no port scan (-sn)
  /nmap scan <target> [ports]                 TCP connect/SYN scan (nmap picks based on privileges)
  /nmap version-scan <target> [ports]           Service + version detection (-sV)
  /nmap script-scan <target> <script>             Run a named NSE script (-script)
  /nmap os-detect <target>                          OS fingerprinting (-O, usually needs elevation)
  /nmap explain                                        How this module works
"""

import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TIMEOUT = 120


def _available() -> bool:
    return shutil.which("nmap") is not None


def _run(args: list, timeout: int = _TIMEOUT):
    return subprocess.run(["nmap"] + args, capture_output=True, text=True, timeout=timeout)


class NmapModule(Module):
    name = "nmap"
    version = "1.0.0"
    description = "Direct nmap scan control (ping/connect/version/script/OS scans)"
    author = "termaid"

    def on_load(self):
        for cmd in ["ping-scan", "scan", "version-scan", "script-scan", "os-detect", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    def _fmt(self, r) -> str:
        out = (r.stdout or r.stderr).strip()
        return out or "(no output)"

    @safe
    def cmd_ping_scan(self, arg=""):
        """Host discovery only, no port scan (-sn): /nmap ping-scan <target>"""
        target = (arg or "").strip()
        if not target:
            return "[nmap] Usage: /nmap ping-scan <target>"
        if not _available():
            return "[nmap] nmap not found on PATH."
        try:
            r = _run(["-sn", target], timeout=60)
        except subprocess.TimeoutExpired:
            return "[nmap] Scan timed out (60s)."
        return f"[nmap] {self._fmt(r)}"

    @safe
    def cmd_scan(self, arg=""):
        """TCP scan: /nmap scan <target> [ports]"""
        parts = (arg or "").split()
        if not parts:
            return "[nmap] Usage: /nmap scan <target> [ports, e.g. 1-1000 or 22,80,443]"
        target = parts[0]
        if not _available():
            return "[nmap] nmap not found on PATH."
        args = [target]
        if len(parts) > 1:
            args = ["-p", parts[1], target]
        try:
            r = _run(args)
        except subprocess.TimeoutExpired:
            return f"[nmap] Scan timed out ({_TIMEOUT}s) — try narrowing the port range."
        return f"[nmap] {self._fmt(r)}"

    @safe
    def cmd_version_scan(self, arg=""):
        """Service + version detection (-sV): /nmap version-scan <target> [ports]"""
        parts = (arg or "").split()
        if not parts:
            return "[nmap] Usage: /nmap version-scan <target> [ports]"
        target = parts[0]
        if not _available():
            return "[nmap] nmap not found on PATH."
        args = ["-sV", target]
        if len(parts) > 1:
            args = ["-sV", "-p", parts[1], target]
        try:
            r = _run(args)
        except subprocess.TimeoutExpired:
            return f"[nmap] Scan timed out ({_TIMEOUT}s) — try narrowing the port range."
        return f"[nmap] {self._fmt(r)}"

    @safe
    def cmd_script_scan(self, arg=""):
        """Run a named NSE script (-script): /nmap script-scan <target> <script>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[nmap] Usage: /nmap script-scan <target> <script-name> (e.g. http-title, ssl-cert)"
        target, script = parts
        if not _available():
            return "[nmap] nmap not found on PATH."
        try:
            r = _run(["--script", script, target])
        except subprocess.TimeoutExpired:
            return f"[nmap] Scan timed out ({_TIMEOUT}s)."
        return f"[nmap] {self._fmt(r)}"

    @safe
    def cmd_os_detect(self, arg=""):
        """OS fingerprinting (-O, usually needs elevation): /nmap os-detect <target>"""
        target = (arg or "").strip()
        if not target:
            return "[nmap] Usage: /nmap os-detect <target>"
        if not _available():
            return "[nmap] nmap not found on PATH."
        try:
            r = _run(["-O", target], timeout=90)
        except subprocess.TimeoutExpired:
            return "[nmap] Scan timed out (90s)."
        out = self._fmt(r)
        if "requires root privileges" in out.lower() or "requires administrator" in out.lower():
            return f"[nmap] OS detection needs elevated privileges. {out}"
        return f"[nmap] {out}"

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
