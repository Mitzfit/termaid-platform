"""Tmx Module — tmux session management.

Wraps `tmux` via list-form subprocess args (no shell string ever built).
Attaching interactively isn't possible over a request/response API, so
this only covers session lifecycle (list/create/kill) and one-shot
`send-keys` into an existing session — not an interactive attach.

Commands (~4):
  /tmx sessions                    List tmux sessions
  /tmx new <name>                    Create a new detached session
  /tmx send <name> <text>              Send a line of input to a session
  /tmx kill <name> confirm               Kill a session
  /tmx explain                             How this module works
"""

import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class TmxModule(Module):
    name = "tmx"
    version = "1.0.0"
    description = "tmux session management"
    author = "termaid"

    def on_load(self):
        for cmd in ["sessions", "new", "send", "kill", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _available(self) -> bool:
        return shutil.which("tmux") is not None

    @safe
    def cmd_sessions(self, arg=""):
        """List tmux sessions"""
        if not self._available():
            return "[tmx] tmux is not installed or not on PATH."
        r = subprocess.run(["tmux", "list-sessions"], capture_output=True, text=True, timeout=5)
        out = (r.stdout or r.stderr).strip()
        return f"[tmx] Sessions:\n{out}" if out else "[tmx] No sessions running."

    @safe
    def cmd_new(self, arg=""):
        """Create a new detached session: /tmx new <name>"""
        if not self._available():
            return "[tmx] tmux is not installed or not on PATH."
        name = (arg or "").strip()
        if not name:
            return "[tmx] Usage: /tmx new <name>"
        r = subprocess.run(["tmux", "new-session", "-d", "-s", name], capture_output=True,
                            text=True, timeout=5)
        if r.returncode != 0:
            return f"[tmx] {r.stderr.strip()}"
        return f"[tmx] Created detached session '{name}'"

    @safe
    def cmd_send(self, arg=""):
        """Send a line of input to a session: /tmx send <name> <text>"""
        if not self._available():
            return "[tmx] tmux is not installed or not on PATH."
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[tmx] Usage: /tmx send <name> <text>"
        name, text = parts
        r = subprocess.run(["tmux", "send-keys", "-t", name, text, "Enter"],
                            capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return f"[tmx] {r.stderr.strip()}"
        return f"[tmx] Sent to '{name}'"

    @safe
    def cmd_kill(self, arg=""):
        """Kill a session (confirms): /tmx kill <name> confirm"""
        if not self._available():
            return "[tmx] tmux is not installed or not on PATH."
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            name = parts[0] if parts else "<name>"
            return f"[tmx] Re-run as: /tmx kill {name} confirm"
        name = parts[0]
        r = subprocess.run(["tmux", "kill-session", "-t", name], capture_output=True,
                            text=True, timeout=5)
        if r.returncode != 0:
            return f"[tmx] {r.stderr.strip()}"
        return f"[tmx] Killed session '{name}'"

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
