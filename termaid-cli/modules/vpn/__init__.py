"""VPN Module — WireGuard/OpenVPN client connection management. SYSTEM tier.

Wraps client tools against configs the operator already has — it doesn't
generate keys, configs, or connect to anything of its own choosing.
WireGuard operations (`wg-quick`/`wireguard.exe`) are synchronous and fast
(interface setup, not a persistent process), so they use a bounded
subprocess.run. OpenVPN's client is a genuinely long-running foreground
process that must keep running to hold the tunnel, so it's launched via
non-blocking Popen (never .run) and tracked by PID, the same pattern
/bots and /serve use for anything that must keep running past the
request that started it.

Commands (~5):
  /vpn status                      Active WireGuard/OpenVPN connections
  /vpn list-configs                  List available config files
  /vpn connect <config> confirm        Bring up a VPN connection
  /vpn disconnect <name> confirm         Tear down a VPN connection
  /vpn explain                             How this module works
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


class VpnModule(Module):
    name = "vpn"
    version = "1.0.0"
    description = "WireGuard/OpenVPN client connection management"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "list-configs", "connect", "disconnect", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._config_dir = data_dir / "vpn_configs"
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._openvpn_procs = {}  # name -> Popen

    @safe
    def cmd_status(self, arg=""):
        """Active WireGuard/OpenVPN connections"""
        lines = []
        if shutil.which("wg"):
            try:
                r = subprocess.run(["wg", "show"], capture_output=True, text=True, timeout=10)
                out = r.stdout.strip()
                lines.append(f"WireGuard:\n{out}" if out else "WireGuard: no active tunnels")
            except Exception as e:
                lines.append(f"WireGuard: check failed ({e})")
        elif sys.platform == "win32" and shutil.which("wireguard"):
            lines.append("WireGuard for Windows detected — use 'wireguard /dumplog' for details "
                        "(this module manages tunnels via /installtunnelservice, wg.exe isn't bundled everywhere).")

        for name, proc in list(self._openvpn_procs.items()):
            state = "running" if proc.poll() is None else f"exited ({proc.returncode})"
            lines.append(f"OpenVPN '{name}': {state} (pid {proc.pid})")

        if not lines:
            return "[vpn] No VPN backend detected (install WireGuard or OpenVPN) and no tracked connections."
        return "[vpn] " + "\n".join(lines)

    @safe
    def cmd_list_configs(self, arg=""):
        """List available config files"""
        configs = sorted(self._config_dir.glob("*.conf")) + sorted(self._config_dir.glob("*.ovpn"))
        if not configs:
            return f"[vpn] No configs found in {self._config_dir}. Drop your .conf (WireGuard) or .ovpn (OpenVPN) files there."
        lines = [f"[vpn] {len(configs)} config(s) in {self._config_dir}:"]
        for p in configs:
            lines.append(f"  {p.name}")
        return "\n".join(lines)

    @safe
    def cmd_connect(self, arg=""):
        """Bring up a VPN connection (confirms): /vpn connect <config> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[vpn] Usage: /vpn connect <config-filename> confirm (see /vpn list-configs)"
        config_name = parts[0]
        path = self._config_dir / config_name
        if not path.is_file():
            return f"[vpn] No config named '{config_name}' in {self._config_dir}"

        if path.suffix == ".conf":
            # WireGuard
            try:
                if sys.platform == "win32":
                    if not shutil.which("wireguard"):
                        return "[vpn] wireguard.exe not found."
                    r = subprocess.run(["wireguard", "/installtunnelservice", str(path)],
                                        capture_output=True, text=True, timeout=20)
                else:
                    if not shutil.which("wg-quick"):
                        return "[vpn] wg-quick not found."
                    r = subprocess.run(["wg-quick", "up", str(path)], capture_output=True,
                                        text=True, timeout=20)
            except subprocess.TimeoutExpired:
                return "[vpn] Bringing up the tunnel timed out (20s)."
            if r.returncode != 0:
                return f"[vpn] Failed: {(r.stderr or r.stdout).strip()}"
            return f"[vpn] WireGuard tunnel '{config_name}' is up."
        elif path.suffix == ".ovpn":
            if not shutil.which("openvpn"):
                return "[vpn] openvpn not found."
            if config_name in self._openvpn_procs and self._openvpn_procs[config_name].poll() is None:
                return f"[vpn] '{config_name}' is already running (pid {self._openvpn_procs[config_name].pid})"
            try:
                proc = subprocess.Popen(["openvpn", "--config", str(path)],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                return f"[vpn] Failed to launch: {e}"
            self._openvpn_procs[config_name] = proc
            return f"[vpn] Launched OpenVPN '{config_name}' (pid {proc.pid}) — check /vpn status shortly to confirm it connected."
        return "[vpn] Config must end in .conf (WireGuard) or .ovpn (OpenVPN)"

    @safe
    def cmd_disconnect(self, arg=""):
        """Tear down a VPN connection (confirms): /vpn disconnect <name> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[vpn] Usage: /vpn disconnect <config-name> confirm"
        name = parts[0]

        if name in self._openvpn_procs:
            proc = self._openvpn_procs.pop(name)
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=10)
                except Exception:
                    pass
            return f"[vpn] Stopped OpenVPN '{name}'"

        path = self._config_dir / name
        try:
            if sys.platform == "win32":
                tunnel_name = path.stem
                r = subprocess.run(["wireguard", "/uninstalltunnelservice", tunnel_name],
                                    capture_output=True, text=True, timeout=20)
            else:
                r = subprocess.run(["wg-quick", "down", str(path)], capture_output=True,
                                    text=True, timeout=20)
        except subprocess.TimeoutExpired:
            return "[vpn] Tearing down the tunnel timed out (20s)."
        except Exception as e:
            return f"[vpn] Failed: {e}"
        if r.returncode != 0:
            return f"[vpn] {(r.stderr or r.stdout).strip()}"
        return f"[vpn] Tunnel '{name}' brought down."

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
