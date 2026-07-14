"""Bots Module — Named background worker processes, with persistence + auto-restart.

Generalizes a simple background-process launcher into something closer to
a lightweight supervisor:
  - Definitions (command, working directory, env vars, auto-restart bound)
    persist to disk, so they survive a backend restart even though the OS
    processes they describe do not — /bots list makes that distinction
    explicit rather than pretending we still hold a live handle we don't.
  - Optional bounded auto-restart: if a bot exits non-zero and has an
    auto-restart budget left, the next /bots list or /bots logs call
    (whichever comes first) relaunches it and counts it against the
    budget. There is no background poll loop — restart only happens when
    you next look, which keeps this out of the async event loop entirely.
  - subprocess.Popen (never .run) so launching never blocks the request/
    response cycle; commands are tokenized with shlex.split into list-form
    argv, never handed to a shell, so shell metacharacters in the command
    text are inert. Only ever stops/restarts PIDs this module itself
    spawned and is still tracking — never touches an arbitrary process.

Commands (~12):
  /bots start <name> <command>              Launch a named background process
  /bots start-in <name> <cwd> <command>       Launch with a specific working directory
  /bots setenv <name> <KEY> <VALUE>             Set an env var for future (re)starts
  /bots unsetenv <name> <KEY>                     Remove a configured env var
  /bots envs <name>                                 List configured env vars
  /bots autorestart <name> <max|off>                  Configure the auto-restart budget
  /bots list                                            Show tracked bots + status
  /bots logs <name> [n_chars]                             Show captured stdout/stderr tail
  /bots stats <name>                                        CPU/memory of a running bot
  /bots restart <name>                                        Stop (if running) and relaunch
  /bots stop <name> confirm                                     Stop a tracked bot
  /bots remove <name> confirm                                     Stop + delete its definition
  /bots explain                                                     How this module works
"""

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _termaid_data_dir() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
    return home / ".termaid"


class BotsModule(Module):
    name = "bots"
    version = "1.1.0"
    description = "Named background worker processes, with persistence + auto-restart"
    author = "termaid"

    def on_load(self):
        for cmd in ["start", "start-in", "setenv", "unsetenv", "envs", "autorestart",
                    "list", "logs", "stats", "restart", "stop", "remove", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        data_dir = _termaid_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = data_dir / "bots.json"
        self._registry = self._load()
        self._procs = {}  # name -> Popen (only valid for this process's lifetime)

    # ------------------------------------------------------------------ #
    def _load(self) -> dict:
        if self._registry_path.exists():
            try:
                return json.loads(self._registry_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self._registry_path.write_text(json.dumps(self._registry, indent=2), encoding="utf-8")

    def _log_path(self, name: str) -> Path:
        return Path(tempfile.gettempdir()) / f"termaid-bot-{name}.log"

    def _spawn(self, name: str) -> str:
        """Launch a bot from its persisted definition. Returns an error string, or '' on success."""
        entry = self._registry.get(name)
        if not entry:
            return f"no definition for '{name}'"
        try:
            tokens = shlex.split(entry["command"], posix=(sys.platform != "win32"))
        except ValueError as e:
            return f"couldn't parse command: {e}"
        if not tokens:
            return "empty command"

        env = None
        if entry.get("env"):
            env = os.environ.copy()
            env.update(entry["env"])

        log_path = self._log_path(name)
        try:
            log_file = log_path.open("wb")
            proc = subprocess.Popen(tokens, stdout=log_file, stderr=subprocess.STDOUT,
                                     cwd=entry.get("cwd") or None, env=env)
        except Exception as e:
            return str(e)
        self._procs[name] = proc
        entry["last_pid"] = proc.pid
        entry["last_started"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save()
        return ""

    def _check_autorestart(self, name: str):
        """Lazily relaunch a crashed bot if it has auto-restart budget left. Called from list/logs/stats."""
        entry = self._registry.get(name)
        if not entry or not entry.get("autorestart_max"):
            return
        proc = self._procs.get(name)
        if proc is None or proc.poll() is None:
            return  # not tracked as exited (never started this process lifetime, or still running)
        if proc.returncode == 0:
            return  # clean exit, don't auto-restart
        if entry.get("restart_count", 0) >= entry["autorestart_max"]:
            return  # budget exhausted
        entry["restart_count"] = entry.get("restart_count", 0) + 1
        self._save()
        self._spawn(name)

    def _ensure_known(self, name: str):
        return name in self._registry

    # ------------------------------------------------------------------ #
    @safe
    def cmd_start(self, arg=""):
        """Launch a named background process: /bots start <name> <command>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[bots] Usage: /bots start <name> <command>"
        name, command = parts
        if name in self._procs and self._procs[name].poll() is None:
            return f"[bots] '{name}' is already running (pid {self._procs[name].pid})"
        self._registry[name] = {"command": command, "cwd": None, "env": {},
                                 "autorestart_max": None, "restart_count": 0,
                                 "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        self._save()
        err = self._spawn(name)
        if err:
            return f"[bots] Failed to start '{name}': {err}"
        return f"[bots] Started '{name}' (pid {self._procs[name].pid}): {command}\n  logs: /bots logs {name}"

    @safe
    def cmd_start_in(self, arg=""):
        """Launch with a specific working directory: /bots start-in <name> <cwd> <command>"""
        parts = (arg or "").split(maxsplit=2)
        if len(parts) < 3:
            return "[bots] Usage: /bots start-in <name> <cwd> <command>"
        name, cwd, command = parts
        cwd_path = Path(cwd).expanduser()
        if not cwd_path.is_dir():
            return f"[bots] Not a directory: {cwd_path}"
        if name in self._procs and self._procs[name].poll() is None:
            return f"[bots] '{name}' is already running (pid {self._procs[name].pid})"
        self._registry[name] = {"command": command, "cwd": str(cwd_path), "env": {},
                                 "autorestart_max": None, "restart_count": 0,
                                 "created": time.strftime("%Y-%m-%d %H:%M:%S")}
        self._save()
        err = self._spawn(name)
        if err:
            return f"[bots] Failed to start '{name}': {err}"
        return f"[bots] Started '{name}' in {cwd_path} (pid {self._procs[name].pid}): {command}"

    @safe
    def cmd_setenv(self, arg=""):
        """Set an env var for future (re)starts: /bots setenv <name> <KEY> <VALUE>"""
        parts = (arg or "").split(maxsplit=2)
        if len(parts) < 3:
            return "[bots] Usage: /bots setenv <name> <KEY> <VALUE>"
        name, key, value = parts
        if not self._ensure_known(name):
            return f"[bots] No bot named '{name}'. /bots start first."
        self._registry[name].setdefault("env", {})[key] = value
        self._save()
        return f"[bots] Set {key} for '{name}' (applies on next start/restart)"

    @safe
    def cmd_unsetenv(self, arg=""):
        """Remove a configured env var: /bots unsetenv <name> <KEY>"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[bots] Usage: /bots unsetenv <name> <KEY>"
        name, key = parts
        if not self._ensure_known(name):
            return f"[bots] No bot named '{name}'"
        env = self._registry[name].get("env", {})
        if key not in env:
            return f"[bots] '{key}' isn't set for '{name}'"
        del env[key]
        self._save()
        return f"[bots] Removed {key} from '{name}' (applies on next start/restart)"

    @safe
    def cmd_envs(self, arg=""):
        """List configured env vars: /bots envs <name>"""
        name = (arg or "").strip()
        if not self._ensure_known(name):
            return "[bots] Usage: /bots envs <name>"
        env = self._registry[name].get("env", {})
        if not env:
            return f"[bots] No env vars configured for '{name}'"
        lines = [f"[bots] '{name}' env:"]
        for k, v in sorted(env.items()):
            lines.append(f"  {k}={v}")
        return "\n".join(lines)

    @safe
    def cmd_autorestart(self, arg=""):
        """Configure the auto-restart budget: /bots autorestart <name> <max|off>"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[bots] Usage: /bots autorestart <name> <max_restarts|off>"
        name, value = parts
        if not self._ensure_known(name):
            return f"[bots] No bot named '{name}'"
        if value.lower() == "off":
            self._registry[name]["autorestart_max"] = None
            self._save()
            return f"[bots] Auto-restart disabled for '{name}'"
        try:
            n = int(value)
        except ValueError:
            return "[bots] Usage: /bots autorestart <name> <max_restarts|off>"
        self._registry[name]["autorestart_max"] = max(0, n)
        self._registry[name]["restart_count"] = 0
        self._save()
        return f"[bots] Auto-restart budget for '{name}' set to {n} (checked lazily on /bots list or /bots logs)"

    @safe
    def cmd_list(self, arg=""):
        """Show tracked bots + status"""
        if not self._registry:
            return "[bots] No bots tracked. /bots start <name> <command>"
        for name in self._registry:
            self._check_autorestart(name)
        lines = [f"[bots] {len(self._registry)} bot(s):"]
        for name, entry in sorted(self._registry.items()):
            proc = self._procs.get(name)
            if proc is None:
                status = "not tracked (backend restarted since — /bots restart to relaunch)"
                pid_s = "-"
            elif proc.poll() is None:
                status = "running"
                pid_s = str(proc.pid)
            else:
                status = f"exited ({proc.returncode})"
                pid_s = str(proc.pid)
            ar = entry.get("autorestart_max")
            ar_s = f"  autorestart {entry.get('restart_count', 0)}/{ar}" if ar else ""
            lines.append(f"  {name:15s} {status:45s} pid {pid_s:<7s} {entry['command']}{ar_s}")
        return "\n".join(lines)

    @safe
    def cmd_logs(self, arg=""):
        """Show captured stdout/stderr tail: /bots logs <name> [n_chars]"""
        parts = (arg or "").split()
        if not parts:
            return "[bots] Usage: /bots logs <name> [n_chars]"
        name = parts[0]
        try:
            n_chars = int(parts[1]) if len(parts) > 1 else 4000
        except ValueError:
            n_chars = 4000
        if not self._ensure_known(name):
            return f"[bots] No bot named '{name}'"
        self._check_autorestart(name)
        log_path = self._log_path(name)
        if not log_path.exists():
            return f"[bots] No log output yet for '{name}'"
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[bots] Could not read log: {e}"
        tail = text[-n_chars:]
        return f"[bots] {name} log (last {len(tail)} chars):\n{tail or '(empty)'}"

    @safe
    def cmd_stats(self, arg=""):
        """CPU/memory of a running bot: /bots stats <name>"""
        name = (arg or "").strip()
        if not self._ensure_known(name):
            return "[bots] Usage: /bots stats <name>"
        proc = self._procs.get(name)
        if proc is None or proc.poll() is not None:
            return f"[bots] '{name}' isn't currently running."
        pid = proc.pid
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-Process -Id {pid} -ErrorAction SilentlyContinue | "
                     "Select-Object CPU,WorkingSet64 | ConvertTo-Json -Compress"],
                    capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
                data = json.loads(r.stdout.strip()) if r.stdout.strip() else {}
                mem_mb = (data.get("WorkingSet64") or 0) / (1024 * 1024)
                cpu_s = data.get("CPU")
                return f"[bots] '{name}' (pid {pid}): CPU time {cpu_s}s, memory {mem_mb:.1f}MB"
            else:
                stat_path = Path(f"/proc/{pid}/status")
                if not stat_path.exists():
                    return f"[bots] Could not read /proc/{pid}/status"
                text = stat_path.read_text(errors="replace")
                vm_rss = next((l for l in text.splitlines() if l.startswith("VmRSS:")), "")
                return f"[bots] '{name}' (pid {pid}): {vm_rss.strip() or 'unavailable'}"
        except Exception as e:
            return f"[bots] Could not read stats: {e}"

    @safe
    def cmd_restart(self, arg=""):
        """Stop (if running) and relaunch: /bots restart <name>"""
        name = (arg or "").strip()
        if not self._ensure_known(name):
            return f"[bots] No bot named '{name}'. /bots start <name> <command> first."
        proc = self._procs.get(name)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                pass
        err = self._spawn(name)
        if err:
            return f"[bots] Failed to restart '{name}': {err}"
        return f"[bots] Restarted '{name}' (pid {self._procs[name].pid})"

    @safe
    def cmd_stop(self, arg=""):
        """Stop a tracked bot (confirms): /bots stop <name> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            name = parts[0] if parts else "<name>"
            return f"[bots] Re-run as: /bots stop {name} confirm"
        name = parts[0]
        proc = self._procs.get(name)
        if proc is None or proc.poll() is not None:
            return f"[bots] '{name}' isn't currently running."
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            pass
        return f"[bots] Stopped '{name}' (definition kept — /bots restart to relaunch, /bots remove to delete it)"

    @safe
    def cmd_remove(self, arg=""):
        """Stop + delete its definition (confirms): /bots remove <name> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            name = parts[0] if parts else "<name>"
            return f"[bots] Re-run as: /bots remove {name} confirm"
        name = parts[0]
        if not self._ensure_known(name):
            return f"[bots] No bot named '{name}'"
        proc = self._procs.pop(name, None)
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                pass
        del self._registry[name]
        self._save()
        return f"[bots] Removed '{name}'"

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
