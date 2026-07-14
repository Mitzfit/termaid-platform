"""Sudo Module — Run a command with sudo (Linux/macOS). DANGEROUS tier.

Uses `sudo -n` (non-interactive) deliberately: a real sudo password prompt
is exactly the class of blocking call this codebase avoids everywhere else
(see the input()-removal history in this project's verify skill) — it
would hang waiting on stdin that a request/response API can never supply,
freezing the shared event loop. `-n` makes sudo fail fast with a clear
error instead if a password would actually be required, which means this
only works when NOPASSWD is configured for the relevant command, or the
sudo timestamp is still fresh from a recent interactive use. No-op on
Windows — see /privesc for the equivalent there.

Commands (~2):
  /sudo run <command> confirm     Run a command with sudo -n
  /sudo explain                     How this module works
"""

import shlex
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TIMEOUT = 60


class SudoModule(Module):
    name = "sudo"
    version = "1.0.0"
    description = "Run a command with sudo -n (Linux/macOS only)"
    author = "termaid"

    def on_load(self):
        for cmd in ["run", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_run(self, arg=""):
        """Run a command with sudo -n (confirms): /sudo run <command> confirm"""
        if sys.platform == "win32":
            return "[sudo] Not applicable on Windows — see /privesc for elevating the current session."
        text = (arg or "").rstrip()
        if not text.lower().endswith("confirm"):
            return "[sudo] This runs a command as root. Re-run as: /sudo run <command> confirm"
        command = text[:-len("confirm")].rstrip()
        if not command:
            return "[sudo] Usage: /sudo run <command> confirm"
        try:
            tokens = shlex.split(command)
        except ValueError as e:
            return f"[sudo] Couldn't parse command: {e}"
        if not tokens:
            return "[sudo] Usage: /sudo run <command> confirm"
        try:
            r = subprocess.run(["sudo", "-n"] + tokens, capture_output=True, text=True,
                                timeout=_TIMEOUT, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return "[sudo] sudo not found on this system."
        except subprocess.TimeoutExpired:
            return f"[sudo] Command timed out after {_TIMEOUT}s."
        if r.returncode != 0 and "password is required" in (r.stderr or "").lower():
            return ("[sudo] A password is required and this is a non-interactive API — "
                    "either configure NOPASSWD for this command in sudoers, or run it "
                    "interactively yourself once first so the sudo timestamp is fresh.")
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out or "(no stdout)"
        if err:
            result += f"\n[stderr]\n{err}"
        return f"[sudo] (exit {r.returncode}) {result}"

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
