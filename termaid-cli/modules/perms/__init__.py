"""Perms Module — View and change file/directory permissions. DANGEROUS tier.

Windows: wraps `icacls` for both viewing and setting ACLs. Linux/macOS:
wraps `chmod`/`chown`. Viewing is unrestricted; changing permissions
confirms first since a bad permission change (accidentally locking
yourself out of your own files, or over-widening access) is easy to do
by accident and can be awkward to undo.

Commands (~3):
  /perms show <path>                Show current permissions
  /perms set <path> <mode> confirm    Set permissions (chmod-style octal on
                                         Linux/macOS, or an icacls grant string
                                         on Windows, e.g. "Everyone:R")
  /perms explain                        How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class PermsModule(Module):
    name = "perms"
    version = "1.0.0"
    description = "View and change file/directory permissions"
    author = "termaid"

    def on_load(self):
        for cmd in ["show", "set", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_show(self, arg=""):
        """Show current permissions: /perms show <path>"""
        path = (arg or "").strip()
        if not path:
            return "[perms] Usage: /perms show <path>"
        try:
            if sys.platform == "win32":
                r = subprocess.run(["icacls", path], capture_output=True, text=True, timeout=10)
            else:
                r = subprocess.run(["ls", "-ld", path], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[perms] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[perms] {path}:\n{out}" if out else f"[perms] No output for {path}"

    @safe
    def cmd_set(self, arg=""):
        """Set permissions (confirms): /perms set <path> <mode> confirm

        Linux/macOS <mode> is chmod-style octal (e.g. 644). Windows <mode> is
        an icacls grant string (e.g. "Everyone:R" or "%USERNAME%:F")."""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[perms] Usage: /perms set <path> <mode> confirm"
        path, mode = parts[0], parts[1]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["icacls", path, "/grant", mode], capture_output=True,
                                    text=True, timeout=15)
            else:
                r = subprocess.run(["chmod", mode, path], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[perms] Failed: {e}"
        if r.returncode != 0:
            return f"[perms] {(r.stderr or r.stdout).strip()}"
        return f"[perms] Updated {path} -> {mode}"

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
