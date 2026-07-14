"""ADB Module — Android Debug Bridge wrapper. DANGEROUS tier.

Operates on the operator's own connected Android device(s), same as if
they ran `adb` directly in a terminal. List-form subprocess args and
`shlex.split` for the shell command passed to `adb shell` — never a bare
shell string — so this doesn't reintroduce the class of injection bug
already fixed elsewhere in this codebase (see /netscan's history), even
though the underlying capability (arbitrary shell access to a connected
device) is intentionally broad.

Commands (~6):
  /adb devices                    List connected devices
  /adb shell <command>              Run a shell command on the device
  /adb install <apk_path> confirm     Install an APK
  /adb uninstall <package> confirm      Uninstall a package
  /adb reboot confirm                     Reboot the connected device
  /adb explain                              How this module works
"""

import shlex
import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TIMEOUT = 30


class AdbModule(Module):
    name = "adb"
    version = "1.0.0"
    description = "Android Debug Bridge wrapper"
    author = "termaid"

    def on_load(self):
        for cmd in ["devices", "shell", "install", "uninstall", "reboot", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _available(self) -> bool:
        return shutil.which("adb") is not None

    def _run(self, args: list, timeout: int = _TIMEOUT):
        return subprocess.run(["adb"] + args, capture_output=True, text=True,
                               timeout=timeout, encoding="utf-8", errors="replace")

    @safe
    def cmd_devices(self, arg=""):
        """List connected devices"""
        if not self._available():
            return "[adb] adb not found — install Android Platform Tools."
        try:
            r = self._run(["devices", "-l"])
        except Exception as e:
            return f"[adb] Failed: {e}"
        return f"[adb] {r.stdout.strip() or '(no output)'}"

    @safe
    def cmd_shell(self, arg=""):
        """Run a shell command on the device: /adb shell <command>"""
        if not self._available():
            return "[adb] adb not found — install Android Platform Tools."
        command = (arg or "").strip()
        if not command:
            return "[adb] Usage: /adb shell <command>"
        try:
            tokens = shlex.split(command)
        except ValueError as e:
            return f"[adb] Couldn't parse command: {e}"
        try:
            r = self._run(["shell"] + tokens)
        except subprocess.TimeoutExpired:
            return f"[adb] Command timed out after {_TIMEOUT}s."
        except Exception as e:
            return f"[adb] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[adb] {out or '(no output)'}"

    @safe
    def cmd_install(self, arg=""):
        """Install an APK (confirms): /adb install <apk_path> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[-1].lower() != "confirm":
            return "[adb] Usage: /adb install <apk_path> confirm"
        apk_path = " ".join(parts[:-1])
        if not self._available():
            return "[adb] adb not found — install Android Platform Tools."
        try:
            r = self._run(["install", "-r", apk_path], timeout=120)
        except subprocess.TimeoutExpired:
            return "[adb] Install timed out after 120s."
        except Exception as e:
            return f"[adb] Failed: {e}"
        return f"[adb] {(r.stdout or r.stderr).strip()}"

    @safe
    def cmd_uninstall(self, arg=""):
        """Uninstall a package (confirms): /adb uninstall <package> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[adb] Usage: /adb uninstall <package> confirm"
        package = parts[0]
        if not self._available():
            return "[adb] adb not found — install Android Platform Tools."
        try:
            r = self._run(["uninstall", package], timeout=60)
        except Exception as e:
            return f"[adb] Failed: {e}"
        return f"[adb] {(r.stdout or r.stderr).strip()}"

    @safe
    def cmd_reboot(self, arg=""):
        """Reboot the connected device (confirms): /adb reboot confirm"""
        if (arg or "").strip().lower() != "confirm":
            return "[adb] Re-run as: /adb reboot confirm"
        if not self._available():
            return "[adb] adb not found — install Android Platform Tools."
        try:
            r = self._run(["reboot"], timeout=15)
        except Exception as e:
            return f"[adb] Failed: {e}"
        return "[adb] Reboot command sent."

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
