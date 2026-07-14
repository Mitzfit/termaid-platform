"""Lessons Module — Patterns learned from past interactions.

Different from /memory (facts) and /rules (behavior contracts). /lessons
captures PATTERNS the AI should remember from what worked and what
didn't in past interactions.

Example lessons:
  "When user asks for code, default to Python unless they specify otherwise"
  "User prefers async/await over callbacks"
  "User wants type hints in Python functions"
  "When fixing a bug, propose tests too"

These are user-validated patterns that shape future AI behavior via the
brain's system prompt.

Commands (12):
  /lessons list                  All lessons
  /lessons add <text>            Add a lesson manually
  /lessons from-last             Generate lesson from last AI exchange
  /lessons remove <id>           Remove
  /lessons toggle <id>           Enable/disable
  /lessons tag <id> <tag>        Tag for grouping
  /lessons by-tag <tag>          Filter
  /lessons promote <id>          Promote to /rules
  /lessons review                Review recent lessons
  /lessons clear                 Remove all
  /lessons export                Export to JSON
  /lessons stats                 How many, by tag
"""

import json
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.atomic import atomic_write_json, atomic_write_text
except ImportError:
    from pathlib import Path as _AtomicPath
    import json as _atomic_json
    def atomic_write_json(p, d, indent=2, **kw):
        _AtomicPath(str(p)).write_text(_atomic_json.dumps(d, indent=indent))
    def atomic_write_text(p, c, **kw):
        _AtomicPath(str(p)).write_text(c)

try:
    from _shared.error_helper import safe
except Exception:
    def safe(fn): return fn


class LessonsModule(Module):
    name = "lessons"
    version = "1.0.0"
    description = "User-validated patterns shaping future AI behavior"
    author = "termaid"

    def on_load(self):
        cmds = ["list","add","from-last","remove","toggle","tag","by-tag",
                "promote","review","clear","export","stats", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "lessons"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "lessons.jsonl"
        self._data_dir = data_dir

    def _load(self):
        if not self._file.exists(): return []
        try:
            return [json.loads(l) for l in self._file.read_text().splitlines() if l.strip()]
        except Exception: return []

    def _save_all(self, lessons):
        self._file.write_text("\n".join(json.dumps(l) for l in lessons) + ("\n" if lessons else ""))

    def _next_id(self, lessons):
        return max((l.get("id", 0) for l in lessons), default=0) + 1

    @safe
    def cmd_list(self, arg=""):
        """All lessons"""
        lessons = self._load()
        if not lessons: return "[lessons] No lessons yet."
        lines = [f"[lessons] {len(lessons)} lesson(s):"]
        for l in sorted(lessons, key=lambda x: x.get("id", 0)):
            mark = "●" if l.get("enabled", True) else "○"
            tag = f" #{l['tag']}" if l.get("tag") else ""
            src = f" ({l.get('source','manual')})" if l.get("source") else ""
            lines.append(f"  {mark} [{l.get('id',0):>3d}]{tag}{src}  {l.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_add(self, arg=""):
        """Add a lesson manually"""
        text = (arg or "").strip()
        if not text: return "[lessons] Usage: /lessons add <pattern>"
        if len(text) > 300: return f"[lessons] Too long ({len(text)} chars). Keep under 300."
        lessons = self._load()
        new_id = self._next_id(lessons)
        lessons.append({
            "id": new_id, "text": text, "enabled": True, "tag": "",
            "source": "manual", "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._save_all(lessons)
        return f"[lessons] ✓ Added [{new_id}]: {text}"

    @safe
    def cmd_from_last(self, arg=""):
        """Generate a lesson from your last AI exchange"""
        # Best-effort: look at session history if available
        if not getattr(self, "ai", None):
            return ("[lessons] AI not configured.\n"
                    "  Manually add: /lessons add <pattern>")
        # Build a prompt asking AI to extract a lesson from recent context
        ctx_file = self._data_dir / "smart" / "context.json"
        recent_commands = []
        if ctx_file.exists():
            try:
                recent_commands = json.loads(ctx_file.read_text()).get("recent", [])
            except Exception: pass
        prompt = (f"Based on the user's recent commands and any session context, suggest ONE\n"
                  f"behavioral lesson that should improve future interactions. Format:\n"
                  f"A single sentence in the form: 'When X, Y'.\n\n"
                  f"Recent commands: {recent_commands}\n\n"
                  f"Return ONLY the lesson text — one sentence, nothing else.")
        try:
            response = self.ask_ai(prompt, system="You extract concise patterns. One sentence. No preamble.")
        except Exception as e:
            return f"[lessons] AI error: {e}"
        # Take the first non-empty line
        lesson_text = response.strip().split("\n")[0].strip().strip('"')
        if not lesson_text or len(lesson_text) > 300:
            return f"[lessons] AI response unusable. Raw: {response[:200]}"
        # Never auto-save AI-generated content: show the proposal and let the
        # caller explicitly /lessons add it if they want it kept (a request/
        # response API has no way to prompt-and-wait for approval mid-command).
        return (f"[lessons] AI proposes: {lesson_text}\n"
                f"  Keep it with: /lessons add {lesson_text}")
        return f"[lessons] ✓ Added [{new_id}]: {lesson_text}"

    @safe
    def cmd_remove(self, arg=""):
        """Remove a lesson"""
        try: lid = int((arg or "").strip())
        except Exception: return "[lessons] Usage: /lessons remove <id>"
        lessons = self._load()
        new_lessons = [l for l in lessons if l.get("id") != lid]
        if len(new_lessons) == len(lessons): return f"[lessons] No lesson [{lid}]"
        self._save_all(new_lessons)
        return f"[lessons] ✓ Removed [{lid}]"

    @safe
    def cmd_toggle(self, arg=""):
        """Enable/disable a lesson"""
        try: lid = int((arg or "").strip())
        except Exception: return "[lessons] Usage: /lessons toggle <id>"
        lessons = self._load()
        for l in lessons:
            if l.get("id") == lid:
                l["enabled"] = not l.get("enabled", True)
                self._save_all(lessons)
                return f"[lessons] ✓ [{lid}] {'enabled' if l['enabled'] else 'disabled'}"
        return f"[lessons] No lesson [{lid}]"

    @safe
    def cmd_tag(self, arg=""):
        """Tag a lesson"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2: return "[lessons] Usage: /lessons tag <id> <tag>"
        try: lid = int(parts[0])
        except Exception: return "[lessons] First arg must be ID"
        lessons = self._load()
        for l in lessons:
            if l.get("id") == lid:
                l["tag"] = parts[1].strip()
                self._save_all(lessons)
                return f"[lessons] ✓ [{lid}] tagged: {parts[1]}"
        return f"[lessons] No lesson [{lid}]"

    @safe
    def cmd_by_tag(self, arg=""):
        """Filter by tag"""
        tag = (arg or "").strip()
        if not tag: return "[lessons] Usage: /lessons by-tag <tag>"
        lessons = self._load()
        matches = [l for l in lessons if l.get("tag") == tag]
        if not matches: return f"[lessons] No lessons tagged '{tag}'"
        lines = [f"[lessons] {len(matches)} lesson(s) tagged '{tag}':"]
        for l in matches:
            mark = "●" if l.get("enabled", True) else "○"
            lines.append(f"  {mark} [{l.get('id'):>3d}]  {l.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_promote(self, arg=""):
        """Promote a lesson to a /rules instruction"""
        try: lid = int((arg or "").strip())
        except Exception: return "[lessons] Usage: /lessons promote <id>"
        lessons = self._load()
        lesson = next((l for l in lessons if l.get("id") == lid), None)
        if not lesson: return f"[lessons] No lesson [{lid}]"
        # Write to /rules data dir
        rules_file = self._data_dir / "rules" / "rules.json"
        if not rules_file.exists():
            rules_data = {"restrictions": [], "instructions": []}
        else:
            try: rules_data = json.loads(rules_file.read_text())
            except Exception: rules_data = {"restrictions": [], "instructions": []}
        # Add as instruction
        all_ids = rules_data.get("restrictions",[]) + rules_data.get("instructions",[])
        new_rid = max((r.get("id", 0) for r in all_ids), default=0) + 1
        rules_data.setdefault("instructions", []).append({
            "id": new_rid, "text": lesson["text"], "enabled": True,
            "priority": 3, "tag": "from-lesson",
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
            "promoted_from_lesson": lid,
        })
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(rules_file, rules_data)
        return (f"[lessons] ✓ Promoted lesson [{lid}] to /rules instruction [{new_rid}]\n"
                f"  Lesson still exists in /lessons. Disable original?\n"
                f"  /lessons toggle {lid}")

    @safe
    def cmd_review(self, arg=""):
        """Review recent lessons"""
        try: n = int((arg or "").strip()) if arg.strip() else 10
        except Exception: n = 10
        lessons = sorted(self._load(), key=lambda x: x.get("created",""), reverse=True)[:n]
        if not lessons: return "[lessons] No lessons yet."
        lines = [f"[lessons] {len(lessons)} most recent lesson(s):"]
        for l in lessons:
            mark = "●" if l.get("enabled", True) else "○"
            lines.append(f"  {mark} [{l.get('id'):>3d}] {l.get('created','?')}")
            lines.append(f"        {l.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_clear(self, arg=""):
        """Remove all lessons"""
        if (arg or "").strip().lower() != "confirm":
            return "[lessons] This removes ALL lessons. Re-run as: /lessons clear confirm"
        self._save_all([])
        return "[lessons] ✓ All cleared."

    @safe
    def cmd_export(self, arg=""):
        """Export to JSON"""
        path = (arg or "").strip() or str(self._dir / f"lessons-{int(time.time())}.json")
        Path(path).expanduser().write_text(json.dumps(self._load(), indent=2))
        return f"[lessons] ✓ Exported to {path}"

    @safe
    def cmd_stats(self, arg=""):
        """How many, by tag"""
        lessons = self._load()
        if not lessons: return "[lessons] No lessons yet."
        enabled = sum(1 for l in lessons if l.get("enabled", True))
        from collections import Counter
        by_tag = Counter(l.get("tag","(none)") for l in lessons)
        by_source = Counter(l.get("source","manual") for l in lessons)
        lines = [f"[lessons] Statistics:"]
        lines.append(f"  Total:      {len(lessons)}")
        lines.append(f"  Enabled:    {enabled}")
        lines.append(f"\n  By tag:")
        for tag, n in by_tag.most_common():
            lines.append(f"    {tag:<14s}  {n}")
        lines.append(f"\n  By source:")
        for src, n in by_source.most_common():
            lines.append(f"    {src:<14s}  {n}")
        return "\n".join(lines)
    @safe
    def cmd_explain(self, arg=""):  # v3.11: auto-injected cmd_explain
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            # Fallback if _shared.explain isn't importable
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{getattr(self, 'name', '?')}] {getattr(self, 'description', '')}"]
            lines.append("")
            lines.append("Commands:")
            for c in cmds:
                lines.append(f"  /{getattr(self, 'name', '?')} {c}")
            return "\n".join(lines)
