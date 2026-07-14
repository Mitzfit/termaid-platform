"""Doctor Module — Environment health check: is this machine set up correctly?

Checks for the tools TermAId's own modules lean on (git, docker, nmap, node)
and flags what's missing, plus a couple of sanity checks on TermAId's own
runtime (Python version, disk headroom, .env presence). Read-only — never
installs or modifies anything, only reports.

Commands (~4):
  /doctor check          Full diagnostic run
  /doctor tool <name>      Check a single tool's availability + version
  /doctor explain            How this module works
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TOOLS = ["git", "docker", "nmap", "node", "npm", "whois", "dig"]


class DoctorModule(Module):
    name = "doctor"
    version = "1.0.0"
    description = "Environment health check: is this machine set up correctly?"
    author = "termaid"

    def on_load(self):
        for cmd in ["check", "tool", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _version(self, tool: str) -> str:
        try:
            r = subprocess.run([tool, "--version"], capture_output=True, text=True,
                                timeout=5, encoding="utf-8", errors="replace")
            first_line = (r.stdout or r.stderr or "").strip().splitlines()
            return first_line[0][:60] if first_line else "(no version output)"
        except Exception:
            return ""

    @safe
    def cmd_check(self, arg=""):
        """Full diagnostic run"""
        lines = ["=== Doctor ===\n", "Tools:"]
        for tool in _TOOLS:
            path = shutil.which(tool)
            if path:
                lines.append(f"  OK    {tool:8s} {self._version(tool)}")
            else:
                lines.append(f"  MISS  {tool:8s} not found on PATH")

        lines.append("\nRuntime:")
        lines.append(f"  Python:      {sys.version.split()[0]}")
        lines.append(f"  Platform:    {sys.platform}")

        env_path = Path(os.getcwd()) / ".env"
        lines.append(f"  .env file:   {'found' if env_path.exists() else 'MISSING'}")

        try:
            usage = shutil.disk_usage(os.getcwd())
            pct = usage.used / usage.total * 100
            free_gb = usage.free / (1024 ** 3)
            flag = "OK" if pct < 90 else "WARN"
            lines.append(f"  Disk space:  {flag}  {pct:.0f}% used, {free_gb:.1f}GB free")
        except Exception:
            pass

        return "\n".join(lines)

    @safe
    def cmd_tool(self, arg=""):
        """Check a single tool's availability + version: /doctor tool <name>"""
        tool = (arg or "").strip()
        if not tool:
            return "[doctor] Usage: /doctor tool <name>"
        path = shutil.which(tool)
        if not path:
            return f"[doctor] '{tool}' not found on PATH"
        return f"[doctor] {tool}: {path}\n  {self._version(tool)}"

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
