"""Termux Module — Android Termux environment integration.

Detects whether we're actually running inside Termux (checks for the
`com.termux` marker in `$PREFIX`) before doing anything else — every
command reports clearly that it's a no-op on any other platform rather
than failing confusingly, and the same check runs again per-command
(this module can be loaded once and queried from many contexts, so it
never assumes the environment hasn't changed). Wraps the `termux-api`
package's CLI tools via list-form subprocess args with an explicit
timeout on every call — termux-location in particular can otherwise
block waiting for a GPS fix, and every external call in this codebase
gets a bound for exactly that reason.

Deliberately excludes SMS, call log, and contacts wrappers — those are
a materially more sensitive data category than battery/clipboard/toast,
and this module sticks to the lower-sensitivity, clearly-useful subset
of termux-api.

Commands (~13):
  /termux status                        Detect Termux + list available termux-api tools
  /termux battery                          Battery status
  /termux toast <message>                     Show an Android toast notification
  /termux notification <title> <text>            Post a persistent notification
  /termux clipboard-get                            Read the Android clipboard
  /termux clipboard-set <text>                        Write the Android clipboard
  /termux vibrate [ms]                                  Vibrate the device (default 200ms)
  /termux brightness <0-255|auto>                         Set screen brightness
  /termux torch <on|off>                                    Toggle the flashlight
  /termux volume [stream] [level]                             Show/set audio volume
  /termux wifi-info                                             WiFi connection info
  /termux telephony-info                                          Device/telephony info
  /termux location                                                  One-shot GPS fix (15s timeout)
  /termux sensors                                                     List available sensors
  /termux explain                                                       How this module works
"""

import os
import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _in_termux() -> bool:
    return "com.termux" in os.environ.get("PREFIX", "")


class TermuxModule(Module):
    name = "termux"
    version = "1.1.0"
    description = "Android Termux environment integration"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "battery", "toast", "notification", "clipboard-get",
                    "clipboard-set", "vibrate", "brightness", "torch", "volume",
                    "wifi-info", "telephony-info", "location", "sensors", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    def _run(self, tool: str, args: list, timeout: int = 10):
        """Run a termux-api tool, list-form args, always with a timeout."""
        if not _in_termux():
            return None, "[termux] Not running under Termux (no $PREFIX with 'com.termux')."
        if not shutil.which(tool):
            return None, f"[termux] {tool} not found. Install the Termux:API app + `pkg install termux-api`."
        try:
            r = subprocess.run([tool] + args, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return None, f"[termux] {tool} timed out after {timeout}s."
        except Exception as e:
            return None, f"[termux] {tool} failed: {e}"
        return r, None

    @safe
    def cmd_status(self, arg=""):
        """Detect Termux + list available termux-api tools"""
        if not _in_termux():
            return "[termux] Not running under Termux (no $PREFIX with 'com.termux')."
        tools = ["termux-battery-status", "termux-toast", "termux-notification",
                "termux-clipboard-get", "termux-clipboard-set", "termux-vibrate",
                "termux-brightness", "termux-torch", "termux-volume",
                "termux-wifi-connectioninfo", "termux-telephony-deviceinfo",
                "termux-location", "termux-sensor"]
        lines = [f"[termux] Running under Termux (PREFIX={os.environ.get('PREFIX')})", "", "termux-api tools:"]
        for tool in tools:
            lines.append(f"  {'OK' if shutil.which(tool) else '--'}    {tool}")
        return "\n".join(lines)

    @safe
    def cmd_battery(self, arg=""):
        """Battery status"""
        r, err = self._run("termux-battery-status", [])
        if err:
            return err
        return f"[termux] {r.stdout.strip() or r.stderr.strip()}"

    @safe
    def cmd_toast(self, arg=""):
        """Show an Android toast notification: /termux toast <message>"""
        message = (arg or "").strip()
        if not message:
            return "[termux] Usage: /termux toast <message>"
        r, err = self._run("termux-toast", [message])
        if err:
            return err
        return f"[termux] Toast sent: {message}"

    @safe
    def cmd_notification(self, arg=""):
        """Post a persistent notification: /termux notification <title> <text>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[termux] Usage: /termux notification <title> <text>"
        title, content = parts
        r, err = self._run("termux-notification", ["-t", title, "-c", content])
        if err:
            return err
        return f"[termux] Notification posted: {title}"

    @safe
    def cmd_clipboard_get(self, arg=""):
        """Read the Android clipboard"""
        r, err = self._run("termux-clipboard-get", [])
        if err:
            return err
        return f"[termux] Clipboard: {r.stdout.strip() or '(empty)'}"

    @safe
    def cmd_clipboard_set(self, arg=""):
        """Write the Android clipboard: /termux clipboard-set <text>"""
        text = (arg or "").strip()
        if not text:
            return "[termux] Usage: /termux clipboard-set <text>"
        r, err = self._run("termux-clipboard-set", [text])
        if err:
            return err
        return f"[termux] Clipboard set ({len(text)} chars)"

    @safe
    def cmd_vibrate(self, arg=""):
        """Vibrate the device (default 200ms): /termux vibrate [ms]"""
        s = (arg or "").strip()
        try:
            ms = int(s) if s else 200
        except ValueError:
            return f"[termux] Invalid duration: {s}"
        r, err = self._run("termux-vibrate", ["-d", str(ms)])
        if err:
            return err
        return f"[termux] Vibrated for {ms}ms"

    @safe
    def cmd_brightness(self, arg=""):
        """Set screen brightness: /termux brightness <0-255|auto>"""
        value = (arg or "").strip().lower()
        if not value:
            return "[termux] Usage: /termux brightness <0-255|auto>"
        if value != "auto":
            try:
                n = int(value)
            except ValueError:
                return "[termux] Usage: /termux brightness <0-255|auto>"
            if not (0 <= n <= 255):
                return "[termux] Brightness must be 0-255, or 'auto'"
            value = str(n)
        r, err = self._run("termux-brightness", [value])
        if err:
            return err
        return f"[termux] Brightness set to {value}"

    @safe
    def cmd_torch(self, arg=""):
        """Toggle the flashlight: /termux torch <on|off>"""
        state = (arg or "").strip().lower()
        if state not in ("on", "off"):
            return "[termux] Usage: /termux torch <on|off>"
        r, err = self._run("termux-torch", [state])
        if err:
            return err
        return f"[termux] Torch {state}"

    @safe
    def cmd_volume(self, arg=""):
        """Show/set audio volume: /termux volume [stream] [level]"""
        parts = (arg or "").split()
        if not parts:
            r, err = self._run("termux-volume", [])
            if err:
                return err
            return f"[termux] Volumes:\n{r.stdout.strip()}"
        if len(parts) == 1:
            return "[termux] Usage: /termux volume [stream] [level] (e.g. /termux volume music 8)"
        stream, level = parts[0], parts[1]
        r, err = self._run("termux-volume", [stream, level])
        if err:
            return err
        return f"[termux] Set {stream} volume to {level}"

    @safe
    def cmd_wifi_info(self, arg=""):
        """WiFi connection info"""
        r, err = self._run("termux-wifi-connectioninfo", [])
        if err:
            return err
        return f"[termux] WiFi:\n{r.stdout.strip()}"

    @safe
    def cmd_telephony_info(self, arg=""):
        """Device/telephony info"""
        r, err = self._run("termux-telephony-deviceinfo", [])
        if err:
            return err
        return f"[termux] Telephony:\n{r.stdout.strip()}"

    @safe
    def cmd_location(self, arg=""):
        """One-shot GPS fix (15s timeout)"""
        r, err = self._run("termux-location", ["-r", "once"], timeout=15)
        if err:
            return err
        return f"[termux] Location:\n{r.stdout.strip() or '(no fix — check location permission/GPS)'}"

    @safe
    def cmd_sensors(self, arg=""):
        """List available sensors"""
        r, err = self._run("termux-sensor", ["-l"])
        if err:
            return err
        return f"[termux] Sensors:\n{r.stdout.strip()}"

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
