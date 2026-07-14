"""Schedule Module — Reminder / due-task tracker.

This is a tracker, not a scheduler: the backend is a stateless request/
response API with no persistent background worker, so nothing here fires
automatically or wakes anything up. What it does do: persist named items
with a target datetime and note, and tell you what's due or overdue when
you ask. Wire /schedule due into your own polling if you want alerts.

Commands (~5):
  /schedule add <name> <YYYY-MM-DD[ HH:MM]> [note]     Add a reminder
  /schedule list                                          Show all reminders
  /schedule due                                             Overdue + due today
  /schedule remove <name> confirm                             Remove a reminder
  /schedule explain                                              How this module works
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class ScheduleModule(Module):
    name = "schedule"
    version = "1.0.0"
    description = "Reminder / due-task tracker"
    author = "termaid"

    def on_load(self):
        for cmd in ["add", "list", "due", "remove", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "schedule.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    def _parse_when(self, s: str):
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    @safe
    def cmd_add(self, arg=""):
        """Add a reminder: /schedule add <name> <YYYY-MM-DD[ HH:MM]> [note]"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[schedule] Usage: /schedule add <name> <YYYY-MM-DD[ HH:MM]> [note]"
        name = parts[0]
        rest = parts[1]
        # rest starts with a date, optionally a time, optionally a note
        tokens = rest.split(maxsplit=2)
        when_str = tokens[0]
        note = ""
        if len(tokens) > 1 and ":" in tokens[1] and tokens[1].replace(":", "").isdigit():
            when_str = f"{tokens[0]} {tokens[1]}"
            note = tokens[2] if len(tokens) > 2 else ""
        elif len(tokens) > 1:
            note = " ".join(tokens[1:])
        when = self._parse_when(when_str)
        if when is None:
            return "[schedule] Couldn't parse date. Use YYYY-MM-DD or 'YYYY-MM-DD HH:MM'"
        self._data[name] = {"when": when.isoformat(), "note": note}
        self._save()
        return f"[schedule] Added '{name}' due {when.isoformat(sep=' ')}" + (f" — {note}" if note else "")

    @safe
    def cmd_list(self, arg=""):
        """Show all reminders"""
        if not self._data:
            return "[schedule] No reminders yet. /schedule add <name> <date>"
        items = sorted(self._data.items(), key=lambda kv: kv[1]["when"])
        lines = [f"[schedule] {len(items)} reminder(s):"]
        for name, info in items:
            note = f" — {info['note']}" if info.get("note") else ""
            lines.append(f"  {name:20s} {info['when'].replace('T', ' ')}{note}")
        return "\n".join(lines)

    @safe
    def cmd_due(self, arg=""):
        """Overdue + due today"""
        now = datetime.now()
        today = now.date()
        due = []
        for name, info in self._data.items():
            try:
                when = datetime.fromisoformat(info["when"])
            except Exception:
                continue
            if when.date() <= today:
                overdue = when < now
                due.append((when, name, info.get("note", ""), overdue))
        if not due:
            return "[schedule] Nothing due."
        due.sort()
        lines = ["[schedule] Due:"]
        for when, name, note, overdue in due:
            flag = "OVERDUE" if overdue else "TODAY  "
            lines.append(f"  {flag}  {name:20s} {when.isoformat(sep=' ')}" + (f" — {note}" if note else ""))
        return "\n".join(lines)

    @safe
    def cmd_remove(self, arg=""):
        """Remove a reminder (confirms): /schedule remove <name> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            name = parts[0] if parts else "<name>"
            return f"[schedule] Re-run as: /schedule remove {name} confirm"
        name = parts[0]
        if name not in self._data:
            return f"[schedule] No reminder named '{name}'"
        del self._data[name]
        self._save()
        return f"[schedule] Removed '{name}'"

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
