"""SysCmd Module — Run a raw shell command. DANGEROUS tier: unrestricted.

This is the one module in the entire codebase where `shell=True` is
deliberate, not a bug. Every other module in this codebase treats an
unexpected shell layer as an injection vulnerability (see /netscan's fix
history) because those modules never advertised "give me a raw shell" —
this one does, explicitly, as its entire purpose. The operator already has
a real terminal with the same capability; this just makes it reachable
through TermAId's own command interface. Never loaded in server mode, and
requires explicit per-module opt-in even in local mode (see backend/policy.py)
on top of the confirm gate below.

Commands (~2):
  /syscmd run <command> confirm     Run a raw command through the shell
  /syscmd explain                     How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TIMEOUT = 60


class SysCmdModule(Module):
    name = "syscmd"
    version = "1.0.0"
    description = "Run a raw shell command (DANGEROUS: unrestricted, operator-consent tool)"
    author = "termaid"

    def on_load(self):
        for cmd in ["run", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_run(self, arg=""):
        """Run a raw command through the shell (confirms): /syscmd run <command> confirm"""
        text = (arg or "").rstrip()
        if not text.lower().endswith("confirm"):
            return ("[syscmd] This runs an UNRESTRICTED shell command with this process's full "
                    "permissions. Re-run as: /syscmd run <command> confirm")
        command = text[:-len("confirm")].rstrip()
        if not command:
            return "[syscmd] Usage: /syscmd run <command> confirm"
        try:
            if sys.platform == "win32":
                r = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                                    capture_output=True, text=True, timeout=_TIMEOUT,
                                    encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(command, shell=True, capture_output=True, text=True,
                                    timeout=_TIMEOUT, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            return f"[syscmd] Command timed out after {_TIMEOUT}s."
        except Exception as e:
            return f"[syscmd] Failed to launch: {e}"
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out or "(no stdout)"
        if err:
            result += f"\n[stderr]\n{err}"
        return f"[syscmd] (exit {r.returncode}) {result}"

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
