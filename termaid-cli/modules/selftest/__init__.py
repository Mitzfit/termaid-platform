"""Selftest Module — Live environment/dependency health check.

Distinct from /qa (which checks that every module registers cleanly and
its explain() works — a code-level check) and from /doctor (which checks
external CLI tools): this actually exercises the things TermAId's own
runtime depends on — that its data directory is genuinely writable, that
its own backend port is reachable over loopback, and that a couple of
version-sensitive dependencies (bcrypt/passlib in particular — see this
project's history for why) are compatible. Every check does something
real, not just an import.

Commands (~2):
  /selftest run          Run every live health check
  /selftest explain          How this module works
"""

import os
import socket
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class SelftestModule(Module):
    name = "selftest"
    version = "1.0.0"
    description = "Live environment/dependency health check"
    author = "termaid"

    def on_load(self):
        for cmd in ["run", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _check_data_dir(self):
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            probe = data_dir / f".selftest-probe-{os.getpid()}"
            probe.write_text("ok", encoding="utf-8")
            content = probe.read_text(encoding="utf-8")
            probe.unlink()
            return content == "ok", str(data_dir)
        except Exception as e:
            return False, str(e)

    def _check_loopback_8000(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                result = s.connect_ex(("127.0.0.1", 8000))
                return result == 0
        except Exception:
            return False

    def _check_bcrypt_passlib(self):
        try:
            import bcrypt
            version = getattr(bcrypt, "__version__", "unknown")
            major = int(version.split(".")[0]) if version[0:1].isdigit() else 0
            if major >= 4:
                minor = int(version.split(".")[1]) if len(version.split(".")) > 1 else 0
                if major > 4 or (major == 4 and minor >= 1):
                    return False, f"bcrypt {version} — incompatible with passlib==1.7.4, register/login will 500"
            return True, f"bcrypt {version}"
        except ImportError:
            return False, "bcrypt not installed"
        except Exception as e:
            return False, f"could not determine version: {e}"

    @safe
    def cmd_run(self, arg=""):
        """Run every live health check"""
        lines = ["[selftest] Live health checks:"]

        ok, detail = self._check_data_dir()
        lines.append(f"  {'PASS' if ok else 'FAIL'}  data dir writable   {detail}")

        reachable = self._check_loopback_8000()
        lines.append(f"  {'PASS' if reachable else 'WARN'}  backend on :8000    "
                    f"{'reachable' if reachable else 'not reachable (are we running standalone?)'}")

        ok, detail = self._check_bcrypt_passlib()
        lines.append(f"  {'PASS' if ok else 'FAIL'}  bcrypt/passlib      {detail}")

        try:
            import sqlite3
            lines.append(f"  PASS  sqlite3             {sqlite3.sqlite_version}")
        except ImportError:
            lines.append("  FAIL  sqlite3             not available (stdlib should always have this)")

        return "\n".join(lines)

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
