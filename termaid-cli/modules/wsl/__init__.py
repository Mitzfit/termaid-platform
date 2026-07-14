"""WSL Module — Windows Subsystem for Linux wrapper.

Wraps `wsl.exe` directly via list-form subprocess args (never a shell
string) — `run`'s command argument is tokenized with `shlex.split` and
passed as separate argv entries after `--`, so shell metacharacters in
the command text are inert rather than being interpreted twice. No-op
with a clear message on non-Windows hosts.

Commands (~3):
  /wsl list                       List installed distros (wsl -l -v)
  /wsl run <distro> <command>       Run a command inside a distro
  /wsl explain                        How this module works
"""

import shlex
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class WslModule(Module):
    name = "wsl"
    version = "1.0.0"
    description = "Windows Subsystem for Linux wrapper"
    author = "termaid"

    def on_load(self):
        for cmd in ["list", "run", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_list(self, arg=""):
        """List installed distros (wsl -l -v)"""
        if sys.platform != "win32":
            return "[wsl] Only available on Windows."
        try:
            r = subprocess.run(["wsl", "-l", "-v"], capture_output=True, timeout=15)
            out = r.stdout.decode("utf-16-le", errors="replace").strip()
        except FileNotFoundError:
            return "[wsl] wsl.exe not found — WSL may not be installed."
        except subprocess.TimeoutExpired:
            return "[wsl] wsl -l -v timed out."
        if r.returncode != 0:
            return f"[wsl] {(r.stderr.decode('utf-16-le', errors='replace') or out).strip()}"
        return f"[wsl] Distros:\n{out}" if out else "[wsl] No distros installed."

    @safe
    def cmd_run(self, arg=""):
        """Run a command inside a distro: /wsl run <distro> <command>"""
        if sys.platform != "win32":
            return "[wsl] Only available on Windows."
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[wsl] Usage: /wsl run <distro> <command>"
        distro, command = parts[0], parts[1]
        try:
            tokens = shlex.split(command, posix=True)
        except ValueError as e:
            return f"[wsl] Couldn't parse command: {e}"
        if not tokens:
            return "[wsl] Usage: /wsl run <distro> <command>"
        try:
            r = subprocess.run(["wsl", "-d", distro, "--"] + tokens, capture_output=True,
                                text=True, timeout=30, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return "[wsl] wsl.exe not found — WSL may not be installed."
        except subprocess.TimeoutExpired:
            return "[wsl] Command timed out (30s)."
        out = r.stdout.strip()
        err = r.stderr.strip()
        result = out or "(no output)"
        if err:
            result += f"\n[stderr]\n{err}"
        return f"[wsl:{distro}] {result}"

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
