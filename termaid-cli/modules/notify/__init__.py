"""Notify Module — OS-level toast notifications, with a persisted fallback.

Tries a real desktop notification via platform-native tooling (PowerShell's
BurntToast-free toast API on Windows, `notify-send` on Linux, `osascript`
on macOS). If none of that is available, falls back to a simple persisted
JSON queue other tooling (or a future frontend widget) can poll — degrades
gracefully rather than silently doing nothing.

Commands (~4):
  /notify send <message>       Fire a notification (native, or queued)
  /notify list                   Show queued notifications (fallback mode)
  /notify clear                    Clear the queue (confirms)
  /notify explain                    How this module works
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class NotifyModule(Module):
    name = "notify"
    version = "1.0.0"
    description = "OS-level toast notifications, with a persisted fallback"
    author = "termaid"

    def on_load(self):
        for cmd in ["send", "list", "clear", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._queue_path = data_dir / "notifications.json"

    def _load_queue(self) -> list:
        if self._queue_path.exists():
            try:
                return json.loads(self._queue_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_queue(self, queue: list):
        self._queue_path.write_text(json.dumps(queue, indent=2), encoding="utf-8")

    def _try_native(self, message: str) -> bool:
        try:
            if sys.platform == "win32":
                script = (
                    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
                    "ContentType=WindowsRuntime] > $null; "
                    "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
                    "[Windows.UI.Notifications.ToastTemplateType]::ToastText01); "
                    f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{message}')) > $null; "
                    "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
                    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('TermAId')."
                    "Show($toast)"
                )
                r = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                    capture_output=True, text=True, timeout=5)
                return r.returncode == 0
            if shutil.which("notify-send"):
                r = subprocess.run(["notify-send", "TermAId", message], capture_output=True, timeout=5)
                return r.returncode == 0
            if shutil.which("osascript"):
                script = f'display notification "{message}" with title "TermAId"'
                r = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
                return r.returncode == 0
        except Exception:
            pass
        return False

    @safe
    def cmd_send(self, arg=""):
        """Fire a notification (native, or queued): /notify send <message>"""
        message = (arg or "").strip()
        if not message:
            return "[notify] Usage: /notify send <message>"
        # Strip characters that would break the embedded PowerShell/AppleScript string
        safe_message = message.replace("'", "").replace('"', "").replace("`", "")[:200]
        if self._try_native(safe_message):
            return f"[notify] Sent: {safe_message}"
        queue = self._load_queue()
        queue.append({"message": message, "time": time.strftime("%Y-%m-%d %H:%M:%S")})
        self._save_queue(queue)
        return f"[notify] No native notifier available — queued instead: {message}"

    @safe
    def cmd_list(self, arg=""):
        """Show queued notifications (fallback mode)"""
        queue = self._load_queue()
        if not queue:
            return "[notify] Queue is empty."
        lines = [f"[notify] {len(queue)} queued notification(s):"]
        for n in queue[-20:]:
            lines.append(f"  [{n.get('time', '?')}] {n.get('message', '')}")
        return "\n".join(lines)

    @safe
    def cmd_clear(self, arg=""):
        """Clear the queue (confirms)"""
        if (arg or "").strip().lower() != "confirm":
            return "[notify] This clears the queued notifications. Re-run as: /notify clear confirm"
        n = len(self._load_queue())
        self._save_queue([])
        return f"[notify] Cleared {n} queued notification(s)"

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
