"""Session Module — Track session history, last logins, command counts.

Lightweight work-session bookmarking: mark when you started something, jot
short notes as you go, see how long it's been. This is separate from the
platform's own auth session tracking (RefreshSession in the database) —
that's login sessions; this is "what was I doing" notes for yourself.

Commands (~9):
  /session start <label>         Start a labeled session, records the start time
  /session note <text>              Add a timestamped note to the current session
  /session current                    Show the current session + its notes
  /session end                          End the current session
  /session list                           List past sessions (label + duration)
  /session explain                          How this module works
"""

import json
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class SessionModule(Module):
    name = "session"
    version = "1.0.0"
    description = "Track session history, last logins, command counts"
    author = "termaid"

    def on_load(self):
        for cmd in ["start", "note", "current", "end", "list", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "session"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "sessions.json"
        self._current: dict | None = None

    def _load_all(self) -> list:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                pass
        return []

    def _save_all(self, sessions: list) -> None:
        self._file.write_text(json.dumps(sessions, indent=2))

    @safe
    def cmd_start(self, arg=""):
        """Start a labeled session, records the start time"""
        label = (arg or "").strip() or "untitled"
        if self._current:
            return f"[session] Already in a session ('{self._current['label']}'). /session end first."
        self._current = {"label": label, "started": time.time(),
                        "started_str": time.strftime("%Y-%m-%d %H:%M:%S"), "notes": []}
        return f"[session] Started '{label}'"

    @safe
    def cmd_note(self, arg=""):
        """Add a timestamped note to the current session"""
        text = (arg or "").strip()
        if not text:
            return "[session] Usage: /session note <text>"
        if not self._current:
            return "[session] No active session. /session start <label>"
        self._current["notes"].append({"at": time.strftime("%H:%M:%S"), "text": text})
        return f"[session] Noted."

    @safe
    def cmd_current(self, arg=""):
        """Show the current session + its notes"""
        if not self._current:
            return "[session] No active session. /session start <label>"
        elapsed = int(time.time() - self._current["started"])
        lines = [f"[session] '{self._current['label']}' (started {self._current['started_str']}, "
                f"{elapsed}s ago)"]
        for n in self._current["notes"]:
            lines.append(f"  [{n['at']}] {n['text']}")
        return "\n".join(lines)

    @safe
    def cmd_end(self, arg=""):
        """End the current session"""
        if not self._current:
            return "[session] No active session to end."
        self._current["ended"] = time.time()
        self._current["duration_s"] = int(self._current["ended"] - self._current["started"])
        sessions = self._load_all()
        sessions.append(self._current)
        self._save_all(sessions)
        label = self._current["label"]
        duration = self._current["duration_s"]
        n_notes = len(self._current["notes"])
        self._current = None
        return f"[session] Ended '{label}' ({duration}s, {n_notes} note(s) saved)"

    @safe
    def cmd_list(self, arg=""):
        """List past sessions (label + duration)"""
        sessions = self._load_all()
        if not sessions:
            return "[session] No past sessions."
        lines = [f"[session] {len(sessions)} past session(s):"]
        for s in sessions[-20:]:
            dur = s.get("duration_s", 0)
            lines.append(f"  {s.get('started_str','?')}  '{s.get('label','?')}'  "
                        f"({dur}s, {len(s.get('notes', []))} note(s))")
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
