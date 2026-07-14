"""Serve Module — Background static file server (python -m http.server).

Spawns a detached subprocess per server (`subprocess.Popen`, not `.run` —
launch returns immediately, so this never blocks the request/response
event loop the way a real `input()` or foreground process wait would).
Only ever stops PIDs this module itself spawned and is still tracking in
memory — never touches an arbitrary system process.

Note: tracked state is in-process only (a dict, not a file) — it resets
if the backend restarts, but any server processes it spawned keep running
until stopped explicitly or the OS reaps them.

Commands (~4):
  /serve start <path> [port]     Start a static file server (default port 8090+)
  /serve list                      Show servers this module has started
  /serve stop <port> confirm         Stop a tracked server
  /serve explain                       How this module works
"""

import socket
import subprocess
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_DEFAULT_PORT_RANGE = range(8090, 8100)


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) != 0


class ServeModule(Module):
    name = "serve"
    version = "1.0.0"
    description = "Background static file server (python -m http.server)"
    author = "termaid"

    def on_load(self):
        for cmd in ["start", "list", "stop", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        self._servers = {}  # port -> {"proc": Popen, "path": str, "started": str}

    @safe
    def cmd_start(self, arg=""):
        """Start a static file server: /serve start <path> [port]"""
        parts = (arg or "").split()
        if not parts:
            return "[serve] Usage: /serve start <path> [port]"
        path = Path(parts[0]).expanduser().resolve()
        if not path.is_dir():
            return f"[serve] Not a directory: {path}"

        port = None
        if len(parts) > 1:
            try:
                port = int(parts[1])
            except ValueError:
                return f"[serve] Invalid port: {parts[1]}"
            if port in self._servers:
                return f"[serve] Port {port} is already serving {self._servers[port]['path']}"
            if not _port_free(port):
                return f"[serve] Port {port} is already in use by something else."
        else:
            for candidate in _DEFAULT_PORT_RANGE:
                if candidate not in self._servers and _port_free(candidate):
                    port = candidate
                    break
            if port is None:
                return "[serve] No free port found in the default range 8090-8099."

        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(port), "--directory", str(path)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            return f"[serve] Failed to start: {e}"
        self._servers[port] = {"proc": proc, "path": str(path), "started": time.strftime("%H:%M:%S")}
        return f"[serve] Serving {path} at http://127.0.0.1:{port} (pid {proc.pid})"

    @safe
    def cmd_list(self, arg=""):
        """Show servers this module has started"""
        # Reap any that died on their own
        for port in list(self._servers.keys()):
            if self._servers[port]["proc"].poll() is not None:
                del self._servers[port]
        if not self._servers:
            return "[serve] No servers running."
        lines = [f"[serve] {len(self._servers)} server(s):"]
        for port, info in sorted(self._servers.items()):
            lines.append(f"  :{port:<6d} pid {info['proc'].pid:<7d} since {info['started']}  {info['path']}")
        return "\n".join(lines)

    @safe
    def cmd_stop(self, arg=""):
        """Stop a tracked server (confirms): /serve stop <port> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            port_s = parts[0] if parts else "<port>"
            return f"[serve] Re-run as: /serve stop {port_s} confirm"
        try:
            port = int(parts[0])
        except ValueError:
            return f"[serve] Invalid port: {parts[0]}"
        info = self._servers.pop(port, None)
        if not info:
            return f"[serve] No tracked server on port {port}"
        try:
            info["proc"].terminate()
            info["proc"].wait(timeout=5)
        except Exception:
            pass
        return f"[serve] Stopped server on port {port}"

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
