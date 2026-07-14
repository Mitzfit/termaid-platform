"""Env Module — Environment variable and PATH management.

Important limitation: this backend runs as its own OS process. Changes made
here affect THIS process's environment (and anything it spawns afterward) —
they do NOT reach back into your shell session. There is no general way for
a server process to modify the environment of the terminal that's talking to
it. Use this for inspecting what the backend sees, and for setting variables
that affect subprocess-spawning modules (git, docker, etc.) for the rest of
this process's lifetime.

Commands (~10):
  /env get <name>            Show one variable's value
  /env set <name> <value>      Set a variable for this process (see limitation above)
  /env unset <name>              Remove a variable
  /env list [prefix]                List variables, optionally filtered by name prefix
  /env path                           Show PATH entries, one per line
  /env path-add <dir>                   Prepend a directory to PATH (this process only)
  /env which <name>                       Find a binary on PATH
  /env explain                              How this module works
"""

import os
import shutil
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class EnvModule(Module):
    name = "env"
    version = "1.0.0"
    description = "Environment variable and PATH management"
    author = "termaid"

    def on_load(self):
        for cmd in ["get", "set", "unset", "list", "path", "path-add", "which", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_get(self, arg=""):
        """Show one variable's value"""
        name = (arg or "").strip()
        if not name:
            return "[env] Usage: /env get <name>"
        val = os.environ.get(name)
        return f"[env] {name} = {val!r}" if val is not None else f"[env] {name} is not set"

    @safe
    def cmd_set(self, arg=""):
        """Set a variable for this process (does not reach your shell — see /env explain)"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[env] Usage: /env set <name> <value>"
        name, value = parts
        os.environ[name] = value
        return f"[env] Set {name} for this backend process only (your shell is unaffected)."

    @safe
    def cmd_unset(self, arg=""):
        """Remove a variable"""
        name = (arg or "").strip()
        if not name:
            return "[env] Usage: /env unset <name>"
        if name not in os.environ:
            return f"[env] {name} is not set"
        del os.environ[name]
        return f"[env] Unset {name} (this process only)"

    @safe
    def cmd_list(self, arg=""):
        """List variables, optionally filtered by name prefix"""
        prefix = (arg or "").strip()
        items = sorted(os.environ.items())
        if prefix:
            items = [(k, v) for k, v in items if k.startswith(prefix)]
        if not items:
            return f"[env] No variables{' matching prefix ' + prefix if prefix else ''}."
        lines = [f"[env] {len(items)} variable(s):"]
        for k, v in items:
            display = v if len(v) <= 80 else v[:77] + "..."
            lines.append(f"  {k}={display}")
        return "\n".join(lines)

    @safe
    def cmd_path(self, arg=""):
        """Show PATH entries, one per line"""
        entries = os.environ.get("PATH", "").split(os.pathsep)
        if not entries or entries == [""]:
            return "[env] PATH is empty or unset."
        return f"[env] {len(entries)} PATH entr{'y' if len(entries) == 1 else 'ies'}:\n" + \
              "\n".join(f"  {e}" for e in entries)

    @safe
    def cmd_path_add(self, arg=""):
        """Prepend a directory to PATH (this process only)"""
        d = (arg or "").strip()
        if not d:
            return "[env] Usage: /env path-add <directory>"
        current = os.environ.get("PATH", "")
        os.environ["PATH"] = d + os.pathsep + current
        return f"[env] Prepended '{d}' to PATH for this process."

    @safe
    def cmd_which(self, arg=""):
        """Find a binary on PATH"""
        name = (arg or "").strip()
        if not name:
            return "[env] Usage: /env which <name>"
        path = shutil.which(name)
        return f"[env] {name} -> {path}" if path else f"[env] '{name}' not found on PATH"

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
