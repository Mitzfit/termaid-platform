"""Memory Module — Long-term facts the AI should remember.

Different from /notes (personal notes for you) and /learn (knowledge base
with examples). /memory is specifically for FACTS THE AI NEEDS TO KNOW
about you and your setup. Gets injected into the brain's system prompt.

Examples:
  /memory add "I'm on a Pixel Fold running Termux with Kali in proot"
  /memory add "My main language is Python; I'm learning Rust"
  /memory add "I prefer Vim keybindings"
  /memory add "I work on a project called TermAId"

The AI sees these facts on every interaction, so it doesn't have to
re-learn them in each session.

Commands (12):
  /memory list                 All memories
  /memory add <text>           Add a fact
  /memory remove <id>          Remove
  /memory toggle <id>          Enable/disable a memory
  /memory edit <id> <text>     Edit
  /memory search <query>       Find memories matching text
  /memory tag <id> <tag>       Tag for grouping
  /memory by-tag <tag>         Filter by tag
  /memory clear                Remove all (confirms)
  /memory limit <n>            Set max memories included in prompt
  /memory export               Export to JSON
  /memory import <path>        Import
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


def _hex(c):
    if not c or not c.startswith("#"): return ""
    try:
        r=int(c[1:3],16);g=int(c[3:5],16);b=int(c[5:7],16)
        return f"\033[38;2;{r};{g};{b}m"
    except Exception: return ""
def _r(): return "\033[0m"


class MemoryModule(Module):
    name = "memory"
    version = "1.0.0"
    description = "Long-term facts the AI should remember about user/setup"
    author = "termaid"

    def on_load(self):
        cmds = ["list","add","remove","toggle","edit","search","tag",
                "by-tag","clear","limit","export","import", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "memory"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "memories.json"
        if not self._file.exists():
            self._save({"facts": [], "limit": 50})

    def _load(self):
        try: return json.loads(self._file.read_text())
        except Exception: return {"facts": [], "limit": 50}

    def _save(self, data):
        atomic_write_json(self._file, data)

    def _theme(self):
        try:
            home = Path.home()
            if sys.platform == "win32":
                p = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid" / "style" / "active.json"
            else:
                p = home / ".termaid" / "style" / "active.json"
            return json.loads(p.read_text()) if p.exists() else {}
        except Exception: return {}

    @safe
    def cmd_list(self, arg=""):
        """All memories"""
        data = self._load()
        facts = data.get("facts", [])
        if not facts: return "[memory] No memories yet. /memory add <fact>"
        t = self._theme()
        sc = _hex(t.get("success","#00FF87"))
        mut = _hex(t.get("muted","#6B7280"))
        lines = [f"[memory] {len(facts)} memories (limit: {data.get('limit', 50)} included in prompt):"]
        for f in sorted(facts, key=lambda x: x.get("id", 0)):
            mark = sc + "●" if f.get("enabled", True) else mut + "○"
            tag = f" #{f['tag']}" if f.get("tag") else ""
            lines.append(f"  {mark}{_r()} [{f.get('id',0):>3d}]{tag}  {f.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_add(self, arg=""):
        """Add a fact"""
        text = (arg or "").strip()
        if not text: return "[memory] Usage: /memory add <fact>"
        if len(text) > 500: return f"[memory] Too long ({len(text)} chars). Keep under 500."
        data = self._load()
        facts = data.get("facts", [])
        new_id = max((f.get("id", 0) for f in facts), default=0) + 1
        facts.append({
            "id": new_id, "text": text, "enabled": True, "tag": "",
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        data["facts"] = facts
        self._save(data)
        return f"[memory] ✓ Added memory [{new_id}]: {text}"

    @safe
    def cmd_remove(self, arg=""):
        """Remove a memory by ID"""
        try: mid = int((arg or "").strip())
        except Exception: return "[memory] Usage: /memory remove <id>"
        data = self._load()
        facts = [f for f in data.get("facts", []) if f.get("id") != mid]
        if len(facts) == len(data.get("facts", [])):
            return f"[memory] No memory [{mid}]"
        data["facts"] = facts
        self._save(data)
        return f"[memory] ✓ Removed memory [{mid}]"

    @safe
    def cmd_toggle(self, arg=""):
        """Enable/disable a memory"""
        try: mid = int((arg or "").strip())
        except Exception: return "[memory] Usage: /memory toggle <id>"
        data = self._load()
        for f in data.get("facts", []):
            if f.get("id") == mid:
                f["enabled"] = not f.get("enabled", True)
                self._save(data)
                return f"[memory] ✓ [{mid}] {'enabled' if f['enabled'] else 'disabled'}"
        return f"[memory] No memory [{mid}]"

    @safe
    def cmd_edit(self, arg=""):
        """Edit memory text: /memory edit <id> <new text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) < 2: return "[memory] Usage: /memory edit <id> <new text>"
        try: mid = int(parts[0])
        except Exception: return "[memory] First arg must be ID"
        data = self._load()
        for f in data.get("facts", []):
            if f.get("id") == mid:
                f["text"] = parts[1]
                self._save(data)
                return f"[memory] ✓ Updated [{mid}]"
        return f"[memory] No memory [{mid}]"

    @safe
    def cmd_search(self, arg=""):
        """Find memories matching text"""
        q = (arg or "").strip().lower()
        if not q: return "[memory] Usage: /memory search <query>"
        data = self._load()
        matches = [f for f in data.get("facts", []) if q in f.get("text","").lower() or q in f.get("tag","").lower()]
        if not matches: return f"[memory] No memories matching '{q}'"
        lines = [f"[memory] {len(matches)} match(es):"]
        for f in matches:
            mark = "●" if f.get("enabled", True) else "○"
            lines.append(f"  {mark} [{f.get('id'):>3d}]  {f.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_tag(self, arg=""):
        """Tag a memory: /memory tag <id> <tag>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2: return "[memory] Usage: /memory tag <id> <tag>"
        try: mid = int(parts[0])
        except Exception: return "[memory] First arg must be ID"
        data = self._load()
        for f in data.get("facts", []):
            if f.get("id") == mid:
                f["tag"] = parts[1].strip()
                self._save(data)
                return f"[memory] ✓ [{mid}] tagged: {parts[1]}"
        return f"[memory] No memory [{mid}]"

    @safe
    def cmd_by_tag(self, arg=""):
        """Filter by tag"""
        tag = (arg or "").strip()
        if not tag: return "[memory] Usage: /memory by-tag <tag>"
        data = self._load()
        matches = [f for f in data.get("facts", []) if f.get("tag") == tag]
        if not matches: return f"[memory] No memories tagged '{tag}'"
        lines = [f"[memory] {len(matches)} memory/ies tagged '{tag}':"]
        for f in matches:
            mark = "●" if f.get("enabled", True) else "○"
            lines.append(f"  {mark} [{f.get('id'):>3d}]  {f.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_clear(self, arg=""):
        """Remove all memories"""
        if (arg or "").strip().lower() != "confirm":
            return "[memory] This removes ALL memories. Re-run as: /memory clear confirm"
        self._save({"facts": [], "limit": self._load().get("limit", 50)})
        return "[memory] ✓ All memories cleared."

    @safe
    def cmd_limit(self, arg=""):
        """Set max memories included in prompt"""
        try: n = int((arg or "").strip())
        except Exception: return f"[memory] Current limit: {self._load().get('limit', 50)}"
        if n < 1: return "[memory] Limit must be >= 1"
        data = self._load()
        data["limit"] = n
        self._save(data)
        return f"[memory] ✓ Will include up to {n} enabled memories in AI prompts"

    @safe
    def cmd_export(self, arg=""):
        """Export to JSON"""
        path = (arg or "").strip() or str(self._dir / f"memory-{int(time.time())}.json")
        Path(path).expanduser().write_text(json.dumps(self._load(), indent=2))
        return f"[memory] ✓ Exported to {path}"

    @safe
    def cmd_import(self, arg=""):
        """Import from JSON"""
        path = (arg or "").strip()
        if not path: return "[memory] Usage: /memory import <path>"
        try:
            data = json.loads(Path(path).expanduser().read_text())
        except Exception as e: return f"[memory] Cannot read: {e}"
        existing = self._load()
        # Merge facts, avoiding duplicates by text
        existing_text = {f.get("text") for f in existing.get("facts", [])}
        added = 0
        max_id = max((f.get("id", 0) for f in existing.get("facts", [])), default=0)
        for f in data.get("facts", []):
            if f.get("text") in existing_text: continue
            max_id += 1
            f["id"] = max_id
            existing.setdefault("facts", []).append(f)
            added += 1
        self._save(existing)
        return f"[memory] ✓ Imported {added} new fact(s)"
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
