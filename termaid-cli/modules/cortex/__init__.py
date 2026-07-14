"""Cortex Module — Persistent AI memory, persona, and logic rules (dashboard).

/memory, /persona, /lessons, and /rules already own their own storage and
commands; /cortex doesn't duplicate that — it's a read-only consolidated view
across all of them (the same on-disk files /brain reads), so you can see the
AI's whole "mind" in one place instead of four separate modules. Beyond the
dashboard views, it adds unified search across all four stores, a health
check for things that quietly degrade answer quality (no persona set, memory
count exceeding what /brain will actually include), and a single-file export
of the whole consolidated state.

Commands (~10):
  /cortex status       Consolidated view: persona, memory count, lesson count, rules count
  /cortex memory        Recent memory facts (delegates to reading /memory's store)
  /cortex persona        Active persona summary
  /cortex lessons         Recent lessons summary
  /cortex rules            Active rules summary
  /cortex search <query>    Search persona/rules/memory/lessons text for a match
  /cortex health              Flag things likely to degrade AI answer quality
  /cortex export <path>         Write the full consolidated mind state to a file
  /cortex summary                 One-paragraph plain-English summary of the current mind state
  /cortex explain                    How this module works
"""

import json
import os
import sys
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


class CortexModule(Module):
    name = "cortex"
    version = "1.1.0"
    description = "Persistent AI memory, persona, and logic rules"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "memory", "persona", "lessons", "rules",
                    "search", "health", "export", "summary", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        self._data_dir = _termaid_data_dir()

    def _read_json(self, *parts: str, default=None):
        p = self._data_dir.joinpath(*parts)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return default

    def _read_jsonl(self, *parts: str) -> list:
        p = self._data_dir.joinpath(*parts)
        if not p.exists():
            return []
        try:
            return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        except Exception:
            return []

    @safe
    def cmd_status(self, arg=""):
        """Consolidated view across persona/memory/lessons/rules"""
        persona_data = self._read_json("persona", "personas.json", default={})
        active_persona = persona_data.get("active", "(none)") if persona_data else "(none)"
        memory_data = self._read_json("memory", "memories.json", default={})
        facts = memory_data.get("facts", []) if memory_data else []
        lessons = self._read_jsonl("lessons", "lessons.jsonl")
        rules_data = self._read_json("rules", "rules.json", default={})
        rules_count = len(rules_data.get("instructions", []) if rules_data else []) + \
                     len(rules_data.get("restrictions", []) if rules_data else [])
        lines = ["[cortex] Consolidated mind state:"]
        lines.append(f"  Persona:   {active_persona}")
        lines.append(f"  Memories:  {len(facts)} ({sum(1 for f in facts if f.get('enabled', True))} enabled)")
        lines.append(f"  Lessons:   {len(lessons)} ({sum(1 for l in lessons if l.get('enabled', True))} enabled)")
        lines.append(f"  Rules:     {rules_count}")
        lines.append(f"  AI ready:  {'yes' if self.ai else 'no'}")
        return "\n".join(lines)

    @safe
    def cmd_memory(self, arg=""):
        """Recent memory facts"""
        memory_data = self._read_json("memory", "memories.json", default={})
        facts = memory_data.get("facts", []) if memory_data else []
        if not facts:
            return "[cortex] No memory facts yet. Use /memory add <fact>"
        lines = [f"[cortex] {len(facts)} memory fact(s):"]
        for f in facts[-10:]:
            mark = "x" if f.get("enabled", True) else " "
            lines.append(f"  [{mark}] {f.get('text', '')}")
        return "\n".join(lines)

    @safe
    def cmd_persona(self, arg=""):
        """Active persona summary"""
        data = self._read_json("persona", "personas.json", default={})
        if not data:
            return "[cortex] No persona configured yet."
        active = data.get("active", "default")
        p = data.get("personas", {}).get(active, {})
        return (f"[cortex] Active persona: {active}\n"
                f"  {p.get('description', '')}\n"
                f"  tone: {p.get('tone', 'neutral')}  verbosity: {p.get('verbosity', 'concise')}")

    @safe
    def cmd_lessons(self, arg=""):
        """Recent lessons summary"""
        lessons = self._read_jsonl("lessons", "lessons.jsonl")
        if not lessons:
            return "[cortex] No lessons yet. Use /lessons add <pattern>"
        lines = [f"[cortex] {len(lessons)} lesson(s):"]
        for l in lessons[-10:]:
            mark = "x" if l.get("enabled", True) else " "
            lines.append(f"  [{mark}] {l.get('text', '')}")
        return "\n".join(lines)

    @safe
    def cmd_rules(self, arg=""):
        """Active rules summary"""
        data = self._read_json("rules", "rules.json", default={})
        if not data:
            return "[cortex] No rules configured yet."
        lines = ["[cortex] Rules:"]
        for r in data.get("instructions", []):
            lines.append(f"  + {r.get('text', '')}")
        for r in data.get("restrictions", []):
            lines.append(f"  - MUST NOT: {r.get('text', '')}")
        if len(lines) == 1:
            lines.append("  (none defined)")
        return "\n".join(lines)

    @safe
    def cmd_search(self, arg=""):
        """Search persona/rules/memory/lessons text for a match: /cortex search <query>"""
        query = (arg or "").strip().lower()
        if not query:
            return "[cortex] Usage: /cortex search <query>"
        hits = []

        persona_data = self._read_json("persona", "personas.json", default={})
        for name, p in (persona_data.get("personas", {}) if persona_data else {}).items():
            if query in p.get("description", "").lower():
                hits.append(f"persona:{name}  {p.get('description', '')}")

        rules_data = self._read_json("rules", "rules.json", default={})
        for r in (rules_data.get("instructions", []) if rules_data else []):
            if query in r.get("text", "").lower():
                hits.append(f"rule (instruction)  {r.get('text', '')}")
        for r in (rules_data.get("restrictions", []) if rules_data else []):
            if query in r.get("text", "").lower():
                hits.append(f"rule (restriction)  {r.get('text', '')}")

        memory_data = self._read_json("memory", "memories.json", default={})
        for f in (memory_data.get("facts", []) if memory_data else []):
            if query in f.get("text", "").lower():
                hits.append(f"memory  {f.get('text', '')}")

        for l in self._read_jsonl("lessons", "lessons.jsonl"):
            if query in l.get("text", "").lower():
                hits.append(f"lesson  {l.get('text', '')}")

        if not hits:
            return f"[cortex] No matches for '{query}' across persona/rules/memory/lessons."
        lines = [f"[cortex] {len(hits)} match(es) for '{query}':"]
        for h in hits[:30]:
            lines.append(f"  {h}")
        return "\n".join(lines)

    @safe
    def cmd_health(self, arg=""):
        """Flag things likely to degrade AI answer quality"""
        issues = []

        persona_data = self._read_json("persona", "personas.json", default={})
        if not persona_data or not persona_data.get("active"):
            issues.append("No active persona set — the AI has no defined voice/tone. /persona activate <name>")

        if not self.ai:
            issues.append("No AI provider configured — /brain think and friends will just report this back.")

        memory_data = self._read_json("memory", "memories.json", default={})
        n_facts = len(memory_data.get("facts", [])) if memory_data else 0
        brain_cfg = self._read_json("brain", "config.json", default={})
        depth = brain_cfg.get("depth", 10) if brain_cfg else 10
        if n_facts > depth:
            issues.append(f"{n_facts} memories stored but /brain only includes the last {depth} — "
                          f"{n_facts - depth} won't reach the AI. Raise depth with /brain depth {n_facts}, "
                          "or prune with /memory list + /memory disable.")

        lessons = self._read_jsonl("lessons", "lessons.jsonl")
        if len(lessons) > depth:
            issues.append(f"{len(lessons)} lessons stored but /brain only includes the last {depth} for the same reason.")

        rules_data = self._read_json("rules", "rules.json", default={})
        rules_count = len(rules_data.get("instructions", []) if rules_data else []) + \
                     len(rules_data.get("restrictions", []) if rules_data else [])
        if rules_count == 0:
            issues.append("No rules defined — the AI has no explicit dos/don'ts beyond its base identity.")

        if not issues:
            return "[cortex] No issues found — persona, rules, memory, and lessons all look reasonable."
        return "[cortex] Potential issues:\n" + "\n".join(f"  - {i}" for i in issues)

    @safe
    def cmd_export(self, arg=""):
        """Write the full consolidated mind state to a file: /cortex export <path>"""
        path = (arg or "").strip()
        if not path:
            return "[cortex] Usage: /cortex export <path>"
        state = {
            "persona": self._read_json("persona", "personas.json", default={}),
            "rules": self._read_json("rules", "rules.json", default={}),
            "memory": self._read_json("memory", "memories.json", default={}),
            "lessons": self._read_jsonl("lessons", "lessons.jsonl"),
        }
        try:
            Path(path).expanduser().write_text(json.dumps(state, indent=2), encoding="utf-8")
        except Exception as e:
            return f"[cortex] Failed to write {path}: {e}"
        return f"[cortex] Exported consolidated mind state to {path}"

    @safe
    def cmd_summary(self, arg=""):
        """One-paragraph plain-English summary of the current mind state"""
        persona_data = self._read_json("persona", "personas.json", default={})
        active_persona = persona_data.get("active", "default") if persona_data else "default"
        memory_data = self._read_json("memory", "memories.json", default={})
        n_facts = len(memory_data.get("facts", [])) if memory_data else 0
        lessons = self._read_jsonl("lessons", "lessons.jsonl")
        return (f"[cortex] Running as persona '{active_persona}', remembering {n_facts} "
                f"fact(s) and {len(lessons)} learned pattern(s). "
                f"AI provider is {'configured' if self.ai else 'NOT configured'}.")

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
