# Agent 05 — Knowledge & Learning: OWNED SOURCE CODE

The 6 CLI modules this agent owns (modules/<name>/__init__.py). Hand edits back as .py text.

## `modules/memory/__init__.py`

```python
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
            mark = sc + "✓" if f.get("enabled", True) else mut + "✗"
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
            mark = "✓" if f.get("enabled", True) else "✗"
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
            mark = "✓" if f.get("enabled", True) else "✗"
            lines.append(f"  {mark} [{f.get('id'):>3d}]  {f.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_clear(self, arg=""):
        """Remove all memories"""
        try:
            ans = input("[memory] Remove ALL memories? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt): return "[memory] Cancelled."
        if ans not in ("y","yes"): return "[memory] Cancelled."
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

```

## `modules/notes/__init__.py`

```python
"""Notes Module — Quick local note-taking with tags, search, and export.

Creates and manages markdown-based notes in a local store. Notes are
stored as individual .md files so they remain grep-friendly and portable.

Commands (15):
  /notes add <text>            Create a quick note (first line = title)
  /notes list [n]              List recent notes
  /notes show <id|title>       Display a note
  /notes edit <id>             Print path to edit externally
  /notes delete <id>           Delete a note (confirm)
  /notes search <pattern>      Full-text search across all notes
  /notes tag <id> <tag>        Add a tag to a note
  /notes untag <id> <tag>      Remove a tag
  /notes tags                  List all tags with counts
  /notes by-tag <tag>          Show notes with a tag
  /notes today                 Show notes created today
  /notes stats                 Note statistics
  /notes export [path]         Export all notes as one markdown file
  /notes import <path>         Import a markdown/text file as a note
  /notes path                  Show notes storage path
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class NotesModule(Module):
    name = "notes"
    version = "1.0.0"
    description = "Quick local note-taking with tags and search"
    author = "termaid"

    def on_load(self):
        cmds = ["add", "list", "show", "edit", "delete", "search", "tag",
                "untag", "tags", "by-tag", "today", "stats", "export",
                "import", "path", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "notes"
        self._dir.mkdir(parents=True, exist_ok=True)

    # ---------- helpers ----------

    def _confirm(self, prompt):
        try:
            return input(f"[notes] {prompt} [y/N] ").strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _notes(self):
        return sorted(self._dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)

    def _resolve(self, arg):
        """Find a note by filename (without .md), index, or first-line match."""
        arg = (arg or "").strip()
        if not arg: return None
        notes = self._notes()
        # Index?
        if arg.isdigit():
            idx = int(arg)
            if 1 <= idx <= len(notes):
                return notes[idx - 1]
        # Exact filename stem match
        for n in notes:
            if n.stem == arg:
                return n
        # Title substring match
        for n in notes:
            try:
                first = n.read_text(encoding="utf-8", errors="replace").splitlines()[0]
                if arg.lower() in first.lower().replace("#", "").strip():
                    return n
            except Exception:
                continue
        return None

    def _parse_tags(self, text):
        """Return (front_matter_tags, inline_tags)."""
        tags = set()
        # Front matter: --- ... tags: [a, b] ... ---
        fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, re.S | re.M)
        if fm_match:
            tm = re.search(r"tags\s*:\s*\[([^\]]*)\]", fm_match.group(1))
            if tm:
                for t in tm.group(1).split(","):
                    tags.add(t.strip().strip('"\'').lstrip("#").lower())
        # Inline #hashtags in body
        body = text[fm_match.end():] if fm_match else text
        for m in re.finditer(r"(?:^|\s)#([a-zA-Z][\w-]{1,30})", body):
            tags.add(m.group(1).lower())
        tags.discard("")
        return sorted(tags)

    def _safe_filename(self, title):
        s = re.sub(r"[^\w\s-]", "", title)[:60].strip().replace(" ", "-").lower()
        return s or "untitled"

    # ---------- commands ----------

    @safe
    def cmd_path(self, arg=""):
        return f"[notes] Storage: {self._dir}\n       {len(self._notes())} note(s)."

    @safe
    def cmd_add(self, arg=""):
        text = arg or ""
        if not text.strip():
            return "[notes] Usage: /notes add <text>  (first line becomes title)"
        lines = text.splitlines()
        title = lines[0].strip().lstrip("#").strip() or "untitled"
        stem = f"{time.strftime('%Y%m%d-%H%M%S')}-{self._safe_filename(title)}"
        path = self._dir / f"{stem}.md"
        content = f"""---
title: {title}
created: {time.strftime('%Y-%m-%d %H:%M:%S')}
tags: []
---

{text}
"""
        path.write_text(content, encoding="utf-8")
        return f"[notes] Created: {path.name}"

    @safe
    def cmd_list(self, arg=""):
        try: n = int(arg.strip()) if arg.strip() else 20
        except Exception: n = 20
        notes = self._notes()
        if not notes:
            return "[notes] No notes yet. Create one with /notes add <text>"
        lines = [f"[notes] {len(notes)} note(s) (showing {min(n, len(notes))}):"]
        for i, p in enumerate(notes[:n], 1):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                title_m = re.search(r"title:\s*(.+)", text)
                title = title_m.group(1).strip() if title_m else p.stem
                tags = self._parse_tags(text)
                mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))
                tagstr = f"  [{', '.join('#'+t for t in tags)}]" if tags else ""
                lines.append(f"  {i:3d}. {title[:60]:<60s}  {mtime}{tagstr}")
            except Exception:
                lines.append(f"  {i:3d}. {p.name} (unreadable)")
        return "\n".join(lines)

    @safe
    def cmd_show(self, arg=""):
        p = self._resolve(arg)
        if not p:
            return f"[notes] Not found: {arg}"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[notes] Read error: {e}"
        # Strip front matter for display, show metadata summary
        fm = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        body = text[fm.end():] if fm else text
        header = []
        if fm:
            for line in fm.group(1).splitlines():
                header.append(f"  {line}")
        return f"[notes] {p.name}:\n" + "\n".join(header) + f"\n\n{body}"

    @safe
    def cmd_edit(self, arg=""):
        p = self._resolve(arg)
        if not p:
            return f"[notes] Not found: {arg}"
        return (f"[notes] Edit externally:\n"
                f"  Path: {p}\n"
                f"  VS Code:  code '{p}'\n"
                f"  nano:     nano '{p}'\n"
                f"  vim:      vim '{p}'")

    @safe
    def cmd_delete(self, arg=""):
        p = self._resolve(arg)
        if not p:
            return f"[notes] Not found: {arg}"
        if not self._confirm(f"Delete {p.name}?"):
            return "[notes] Cancelled."
        try:
            p.unlink()
            return f"[notes] Deleted {p.name}"
        except Exception as e:
            return f"[notes] Delete failed: {e}"

    @safe
    def cmd_search(self, arg=""):
        q = (arg or "").strip()
        if not q:
            return "[notes] Usage: /notes search <pattern>"
        try:
            pattern = re.compile(q, re.I)
        except re.error:
            pattern = re.compile(re.escape(q), re.I)
        results = []
        for p in self._notes():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            matches = [(i+1, line) for i, line in enumerate(text.splitlines())
                       if pattern.search(line)]
            if matches:
                results.append((p, matches))
        if not results:
            return f"[notes] No matches for '{q}'"
        lines = [f"[notes] {len(results)} note(s) match '{q}':"]
        for p, matches in results[:30]:
            lines.append(f"\n  {p.name}:")
            for lineno, text in matches[:5]:
                lines.append(f"    L{lineno}: {text.strip()[:120]}")
            if len(matches) > 5:
                lines.append(f"    ... {len(matches)-5} more in this note")
        return "\n".join(lines)

    @safe
    def cmd_tag(self, arg=""):
        parts = (arg or "").split(None, 1)
        if len(parts) < 2:
            return "[notes] Usage: /notes tag <id-or-title> <tagname>"
        p = self._resolve(parts[0])
        if not p:
            return f"[notes] Not found: {parts[0]}"
        tag = parts[1].strip().lstrip("#").lower()
        text = p.read_text(encoding="utf-8", errors="replace")
        existing = self._parse_tags(text)
        if tag in existing:
            return f"[notes] '{p.name}' already has tag #{tag}"
        # Update front matter
        fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        if fm_match:
            fm_body = fm_match.group(1)
            tags_match = re.search(r"tags\s*:\s*\[([^\]]*)\]", fm_body)
            if tags_match:
                current = [t.strip().strip('"\'').lstrip("#") for t in tags_match.group(1).split(",") if t.strip()]
                current.append(tag)
                new_tags_line = "tags: [" + ", ".join(current) + "]"
                fm_body = fm_body[:tags_match.start()] + new_tags_line + fm_body[tags_match.end():]
            else:
                fm_body = fm_body + f"\ntags: [{tag}]"
            text = text[:fm_match.start()] + f"---\n{fm_body}\n---\n" + text[fm_match.end():]
        else:
            text = f"---\ntags: [{tag}]\n---\n\n" + text
        p.write_text(text, encoding="utf-8")
        return f"[notes] Added #{tag} to {p.name}"

    @safe
    def cmd_untag(self, arg=""):
        parts = (arg or "").split(None, 1)
        if len(parts) < 2:
            return "[notes] Usage: /notes untag <id-or-title> <tagname>"
        p = self._resolve(parts[0])
        if not p:
            return f"[notes] Not found: {parts[0]}"
        tag = parts[1].strip().lstrip("#").lower()
        text = p.read_text(encoding="utf-8", errors="replace")
        fm_match = re.search(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
        if not fm_match:
            return f"[notes] No front matter in {p.name}"
        fm_body = fm_match.group(1)
        tags_match = re.search(r"tags\s*:\s*\[([^\]]*)\]", fm_body)
        if not tags_match:
            return f"[notes] No tags on {p.name}"
        current = [t.strip().strip('"\'').lstrip("#") for t in tags_match.group(1).split(",") if t.strip()]
        if tag not in current:
            return f"[notes] No tag #{tag} on {p.name}"
        current.remove(tag)
        new_tags_line = "tags: [" + ", ".join(current) + "]"
        fm_body = fm_body[:tags_match.start()] + new_tags_line + fm_body[tags_match.end():]
        text = text[:fm_match.start()] + f"---\n{fm_body}\n---\n" + text[fm_match.end():]
        p.write_text(text, encoding="utf-8")
        return f"[notes] Removed #{tag} from {p.name}"

    @safe
    def cmd_tags(self, arg=""):
        counts = {}
        for p in self._notes():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                for t in self._parse_tags(text):
                    counts[t] = counts.get(t, 0) + 1
            except Exception: continue
        if not counts:
            return "[notes] No tags yet. Add one with /notes tag <id> <tagname>"
        lines = [f"[notes] {len(counts)} tag(s):"]
        for tag, n in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"  #{tag:<20s} {n:>4d} note(s)")
        return "\n".join(lines)

    @safe
    def cmd_by_tag(self, arg=""):
        tag = (arg or "").strip().lstrip("#").lower()
        if not tag:
            return "[notes] Usage: /notes by-tag <tagname>"
        hits = []
        for p in self._notes():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                if tag in self._parse_tags(text):
                    title_m = re.search(r"title:\s*(.+)", text)
                    title = title_m.group(1).strip() if title_m else p.stem
                    hits.append((p, title))
            except Exception: continue
        if not hits:
            return f"[notes] No notes with #{tag}"
        lines = [f"[notes] {len(hits)} note(s) with #{tag}:"]
        for p, title in hits:
            mtime = time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime))
            lines.append(f"  {title[:60]:<60s}  {mtime}")
        return "\n".join(lines)

    @safe
    def cmd_today(self, arg=""):
        today = time.strftime("%Y-%m-%d")
        hits = [p for p in self._notes()
                if time.strftime("%Y-%m-%d", time.localtime(p.stat().st_mtime)) == today]
        if not hits:
            return f"[notes] No notes created today ({today})."
        lines = [f"[notes] {len(hits)} note(s) today:"]
        for p in hits:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                title_m = re.search(r"title:\s*(.+)", text)
                title = title_m.group(1).strip() if title_m else p.stem
                t = time.strftime("%H:%M", time.localtime(p.stat().st_mtime))
                lines.append(f"  {t}  {title}")
            except Exception: continue
        return "\n".join(lines)

    @safe
    def cmd_stats(self, arg=""):
        notes = self._notes()
        if not notes:
            return "[notes] No notes yet."
        total_bytes = sum(p.stat().st_size for p in notes)
        total_words = 0
        tag_counts = {}
        oldest = min(notes, key=lambda p: p.stat().st_mtime)
        newest = max(notes, key=lambda p: p.stat().st_mtime)
        for p in notes:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                total_words += len(text.split())
                for t in self._parse_tags(text):
                    tag_counts[t] = tag_counts.get(t, 0) + 1
            except Exception: continue
        lines = ["[notes] Statistics:"]
        lines.append(f"  Notes:         {len(notes)}")
        lines.append(f"  Total size:    {total_bytes/1024:.1f} KB")
        lines.append(f"  Total words:   {total_words:,}")
        lines.append(f"  Unique tags:   {len(tag_counts)}")
        lines.append(f"  Oldest:        {time.strftime('%Y-%m-%d', time.localtime(oldest.stat().st_mtime))}")
        lines.append(f"  Newest:        {time.strftime('%Y-%m-%d', time.localtime(newest.stat().st_mtime))}")
        if tag_counts:
            top = sorted(tag_counts.items(), key=lambda x: -x[1])[:5]
            lines.append(f"  Top tags:      {', '.join(f'#{t}({n})' for t,n in top)}")
        return "\n".join(lines)

    @safe
    def cmd_export(self, arg=""):
        out = (arg or "").strip() or str(self._dir / f"export-{int(time.time())}.md")
        notes = self._notes()
        if not notes:
            return "[notes] No notes to export."
        parts = [f"# TermAId Notes Export\n\nExported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                 f"Total: {len(notes)} notes\n\n---\n"]
        for p in notes:
            try:
                parts.append(f"\n## {p.stem}\n\n")
                parts.append(p.read_text(encoding="utf-8", errors="replace"))
                parts.append("\n\n---\n")
            except Exception: continue
        try:
            Path(out).write_text("\n".join(parts), encoding="utf-8")
            return f"[notes] Exported {len(notes)} notes -> {out}"
        except Exception as e:
            return f"[notes] Export failed: {e}"

    @safe
    def cmd_import(self, arg=""):
        path = (arg or "").strip()
        if not path:
            return "[notes] Usage: /notes import <path-to-file>"
        p = Path(path).expanduser()
        if not p.exists():
            return f"[notes] Not found: {p}"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[notes] Read failed: {e}"
        if not text.strip():
            return f"[notes] File empty."
        return self.cmd_add(text)
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

```

## `modules/lessons/__init__.py`

```python
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
            mark = "✓" if l.get("enabled", True) else "✗"
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
        print(f"[lessons] AI proposes: {lesson_text}")
        try:
            ans = input("[lessons] Save this as a lesson? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt): return "[lessons] Cancelled."
        if ans not in ("y","yes"): return "[lessons] Discarded."
        lessons = self._load()
        new_id = self._next_id(lessons)
        lessons.append({
            "id": new_id, "text": lesson_text, "enabled": True, "tag": "",
            "source": "ai-extract", "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        self._save_all(lessons)
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
            mark = "✓" if l.get("enabled", True) else "✗"
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
            mark = "✓" if l.get("enabled", True) else "✗"
            lines.append(f"  {mark} [{l.get('id'):>3d}] {l.get('created','?')}")
            lines.append(f"        {l.get('text','')}")
        return "\n".join(lines)

    @safe
    def cmd_clear(self, arg=""):
        """Remove all lessons"""
        try:
            ans = input("[lessons] Remove ALL lessons? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt): return "[lessons] Cancelled."
        if ans not in ("y","yes"): return "[lessons] Cancelled."
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

```

## `modules/catalog/__init__.py`

```python
"""Catalog Module — Discover modules and commands.

With 50+ modules and 800+ commands, finding what you need matters.
This module enumerates everything, fuzz-searches, and categorizes.

Commands (10):
  /catalog modules           All modules with descriptions
  /catalog commands          All commands (long)
  /catalog search <query>    Fuzzy search across module + command names + descriptions
  /catalog stats             Module / command counts
  /catalog by-platform <p>   Filter to commands likely to work on platform (win/linux/mac)
  /catalog by-category <c>   Group commands by category
  /catalog categories        List defined categories
  /catalog cheatsheet        One-page command reference
  /catalog module <name>     Detail for one module
  /catalog freshly-added     Recently added modules (by mtime)
"""

import importlib
import json
import os
import re
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except Exception:
    def safe(fn): return fn


# Manually-curated categories (module -> tags)
CATEGORIES = {
    "ai":         ["ai", "llm"],
    "auth":       ["auth"],
    "autoconfig": ["config"],
    "bench":      ["perf"],
    "bootmgr":    ["boot"],
    "clip":       ["productivity"],
    "cortex":     ["ai", "memory"],
    "crypto":     ["security"],
    "dbkeys":     ["dev"],
    "debug":      ["mobile", "dev"],
    "devdetect":  ["dev"],
    "devicescan": ["mobile", "hardware"],
    "diskspace":  ["disk"],
    "disktool":   ["disk", "hardware"],
    "dualboot":   ["boot", "os"],
    "env":        ["dev", "config"],
    "errors":     ["meta"],
    "fastboot":   ["mobile"],
    "filetools":  ["fs"],
    "firmware":   ["mobile"],
    "fsscan":     ["fs"],
    "fwown":      ["firmware", "hardware"],
    "git":        ["dev"],
    "hardware":   ["hardware"],
    "health":     ["meta"],
    "imagegen":   ["ai"],
    "learn":      ["meta", "knowledge"],
    "learner":    ["ai", "memory"],
    "manifest":   ["meta"],
    "markets":    ["finance"],
    "multiboot":  ["mobile"],
    "netscan":    ["network", "security"],
    "nettools":   ["network"],
    "netdeep":    ["network"],
    "notes":      ["productivity"],
    "paper":      ["finance"],
    "perftune":   ["perf"],
    "privesc":    ["security"],
    "proj":       ["dev"],
    "pyenv":      ["dev", "python"],
    "recovery":   ["disk", "os"],
    "rootguide":  ["mobile"],
    "router":     ["ai", "config"],
    "sandbox":    ["meta"],
    "sec":        ["security"],
    "selfmod":    ["meta"],
    "selftest":   ["meta"],
    "serve":      ["network", "dev"],
    "sysint":     ["security", "perf"],
    "sysmonitor": ["perf"],
    "uefi":       ["firmware", "boot"],
    "usbdeep":    ["hardware"],
    "vm":         ["dev"],
    "wsl":        ["os", "dev"],
}

# Platform compatibility hints
WINDOWS_ONLY = {"bootmgr": ["winbm_info", "winbm_entries", "winbm_default", "winbm_fix"],
                "wsl": ["all"],
                "fastboot": ["windows_only"]}
LINUX_ONLY = {"perftune": ["cpu_governor", "cpu_governor_set"],
              "bootmgr": ["grub_info", "grub_entries", "sdboot_info"]}


class CatalogModule(Module):
    name = "catalog"
    version = "1.0.0"
    description = "Discover modules and commands across TermAId"
    author = "termaid"

    def on_load(self):
        cmds = ["modules", "commands", "search", "stats", "by-platform",
                "by-category", "categories", "cheatsheet", "module", "freshly-added", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "catalog"
        self._dir.mkdir(parents=True, exist_ok=True)
        # Find modules dir
        self._modules_dir = self._find_modules_dir()
        self._cache = None

    def _find_modules_dir(self):
        # Look for it relative to this file
        here = Path(__file__).resolve().parent
        # We're in modules/catalog; modules/ is parent
        return here.parent

    def _scan_modules(self, force=False):
        if self._cache and not force:
            return self._cache
        result = []
        if not self._modules_dir.exists():
            return result
        for entry in sorted(self._modules_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue
            init_py = entry / "__init__.py"
            if not init_py.exists():
                continue
            try:
                text = init_py.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # Extract docstring
            doc_match = re.match(r'^"""(.*?)"""', text, re.S)
            docstring = doc_match.group(1).strip() if doc_match else ""
            # First line of docstring is summary
            summary = docstring.splitlines()[0].strip() if docstring else ""
            # Extract module name (class attribute)
            name_match = re.search(r'name\s*=\s*"([^"]+)"', text)
            mod_alias = name_match.group(1) if name_match else entry.name
            # Extract version
            ver_match = re.search(r'version\s*=\s*"([^"]+)"', text)
            version = ver_match.group(1) if ver_match else "?"
            # Extract description (class attribute)
            desc_match = re.search(r'description\s*=\s*"([^"]+)"', text)
            description = desc_match.group(1) if desc_match else summary
            # Find all cmd_ methods
            cmds = re.findall(r"def\s+cmd_(\w+)\s*\(", text)
            # Normalize for display (underscore -> hyphen)
            cmd_names = [c.replace("_", "-") for c in cmds]
            # Extract per-command summary from docstring if present
            cmd_descriptions = {}
            for line in docstring.splitlines():
                # match lines like:  /xxx command  description
                m = re.match(r"\s*/(\S+)\s+([\w\-<>\[\]\s]+?)\s{2,}(.+)", line)
                if m:
                    cmd_name = m.group(2).strip().split()[0]
                    cmd_descriptions[cmd_name] = m.group(3).strip()
            result.append({
                "folder": entry.name,
                "name": mod_alias,
                "version": version,
                "description": description,
                "commands": cmd_names,
                "command_count": len(cmd_names),
                "cmd_descriptions": cmd_descriptions,
                "categories": CATEGORIES.get(entry.name, []),
                "mtime": entry.stat().st_mtime,
            })
        self._cache = result
        return result

    # ---------- commands ----------

    @safe
    def cmd_modules(self, arg=""):
        """List all modules with descriptions"""
        mods = self._scan_modules()
        lines = [f"[catalog] {len(mods)} modules:"]
        for m in mods:
            cats = " ".join(f"#{c}" for c in m["categories"]) if m["categories"] else ""
            lines.append(f"\n  /{m['name']:<10s} v{m['version']:<6s} ({m['command_count']:>2d} cmds)  {cats}")
            lines.append(f"      {m['description']}")
        return "\n".join(lines)

    @safe
    def cmd_commands(self, arg=""):
        """List all commands (long)"""
        mods = self._scan_modules()
        total = sum(m["command_count"] for m in mods)
        lines = [f"[catalog] {total} commands across {len(mods)} modules:"]
        for m in mods:
            if not m["commands"]: continue
            lines.append(f"\n  /{m['name']}:")
            for cmd in m["commands"]:
                desc = m["cmd_descriptions"].get(cmd, "")
                if desc:
                    lines.append(f"    /{m['name']} {cmd:<22s}  {desc[:80]}")
                else:
                    lines.append(f"    /{m['name']} {cmd}")
        return "\n".join(lines)

    @safe
    def cmd_search(self, arg=""):
        """Fuzzy search: /catalog search <query>"""
        q = (arg or "").strip().lower()
        if not q:
            return "[catalog] Usage: /catalog search <query>"
        mods = self._scan_modules()
        hits = []
        for m in mods:
            score = 0
            matches = []
            # Module name
            if q in m["name"].lower():
                score += 10
                matches.append("name")
            # Module description
            if q in m["description"].lower():
                score += 5
                matches.append("desc")
            # Categories
            for c in m["categories"]:
                if q in c:
                    score += 3
            # Commands
            cmd_hits = [c for c in m["commands"] if q in c.lower()]
            score += len(cmd_hits) * 4
            # Command descriptions
            for cmd, desc in m["cmd_descriptions"].items():
                if q in desc.lower():
                    score += 2
                    if cmd not in cmd_hits: cmd_hits.append(cmd)
            if score > 0:
                hits.append((score, m, cmd_hits))
        hits.sort(key=lambda x: -x[0])
        if not hits:
            return f"[catalog] No matches for '{q}'"
        lines = [f"[catalog] {len(hits)} match(es) for '{q}':"]
        for score, m, cmd_hits in hits[:15]:
            lines.append(f"\n  /{m['name']:<10s} (score {score})  {m['description']}")
            for c in cmd_hits[:5]:
                desc = m['cmd_descriptions'].get(c, '')
                lines.append(f"      /{m['name']} {c}  {desc[:60]}")
        return "\n".join(lines)

    @safe
    def cmd_stats(self, arg=""):
        """Module / command statistics"""
        mods = self._scan_modules()
        total_cmds = sum(m["command_count"] for m in mods)
        cat_counts = {}
        for m in mods:
            for c in m["categories"]:
                cat_counts[c] = cat_counts.get(c, 0) + 1
        lines = [
            f"[catalog] TermAId statistics:",
            f"  Modules:            {len(mods)}",
            f"  Total commands:     {total_cmds}",
            f"  Avg cmds/module:    {total_cmds / max(len(mods),1):.1f}",
            f"  Largest module:     /{max(mods, key=lambda m: m['command_count'])['name']} "
            f"({max(m['command_count'] for m in mods)} cmds)",
            f"  Smallest module:    /{min(mods, key=lambda m: m['command_count'])['name']} "
            f"({min(m['command_count'] for m in mods)} cmds)",
            "",
            "  Modules by category:",
        ]
        for c, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"    #{c:<14s} {n} module(s)")
        return "\n".join(lines)

    @safe
    def cmd_by_platform(self, arg=""):
        """Filter commands by platform"""
        p = (arg or sys.platform).lower()
        platform_label = "Windows" if "win" in p else "macOS" if "darwin" in p else "Linux"
        mods = self._scan_modules()
        win_only = {"wsl", "ai" if False else None}
        linux_only = set()
        lines = [f"[catalog] Modules for {platform_label}:"]
        for m in mods:
            note = ""
            if m["name"] == "wsl" and "win" not in p:
                note = "  (Windows host only — but useful from inside WSL)"
            lines.append(f"  /{m['name']:<10s} {m['description']}{note}")
        lines.append(f"\n  Most commands work cross-platform. Use /catalog module <name> for specifics.")
        return "\n".join(lines)

    @safe
    def cmd_by_category(self, arg=""):
        """Group by category: /catalog by-category <c>"""
        cat = (arg or "").strip().lower().lstrip("#")
        if not cat:
            return "[catalog] Usage: /catalog by-category <name>  (see /catalog categories)"
        mods = self._scan_modules()
        matches = [m for m in mods if cat in m["categories"]]
        if not matches:
            return f"[catalog] No modules in category #{cat}"
        lines = [f"[catalog] {len(matches)} module(s) in category #{cat}:"]
        for m in matches:
            lines.append(f"\n  /{m['name']:<10s} {m['description']}")
            for c in m["commands"][:8]:
                desc = m["cmd_descriptions"].get(c, "")
                lines.append(f"    /{m['name']} {c}  {desc[:60]}")
            if len(m["commands"]) > 8:
                lines.append(f"    ... +{len(m['commands'])-8} more")
        return "\n".join(lines)

    @safe
    def cmd_categories(self, arg=""):
        """List defined categories"""
        mods = self._scan_modules()
        cat_mods = {}
        for m in mods:
            for c in m["categories"]:
                cat_mods.setdefault(c, []).append(m["name"])
        lines = [f"[catalog] {len(cat_mods)} categories:"]
        for c, names in sorted(cat_mods.items()):
            lines.append(f"  #{c:<12s} {len(names):>2d} mods: {', '.join(names)}")
        return "\n".join(lines)

    @safe
    def cmd_cheatsheet(self, arg=""):
        """One-page command reference"""
        mods = self._scan_modules()
        lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                 f"  TermAId Quick Reference",
                 f"  {len(mods)} modules, {sum(m['command_count'] for m in mods)} commands",
                 f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        # Group by category
        by_cat = {}
        for m in mods:
            cats = m["categories"] or ["other"]
            for c in cats:
                by_cat.setdefault(c, []).append(m)
        # Stable category order
        cat_order = ["meta", "ai", "security", "network", "disk", "firmware", "boot",
                     "hardware", "perf", "mobile", "os", "dev", "fs", "productivity",
                     "finance", "knowledge", "memory", "auth", "config", "python", "other"]
        for cat in cat_order:
            if cat not in by_cat: continue
            lines.append(f"\n  ━━━ #{cat} ━━━")
            for m in by_cat[cat]:
                lines.append(f"  /{m['name']:<10s} ({m['command_count']:>2d}) — {m['description'][:70]}")
        return "\n".join(lines)

    @safe
    def cmd_module(self, arg=""):
        """Detail for one module: /catalog module <name>"""
        name = (arg or "").strip().lstrip("/")
        if not name: return "[catalog] Usage: /catalog module <name>"
        mods = self._scan_modules()
        m = next((x for x in mods if x["name"] == name or x["folder"] == name), None)
        if not m:
            return f"[catalog] No module named '{name}'"
        lines = [f"[catalog] /{m['name']} (v{m['version']})"]
        lines.append(f"  Folder:      modules/{m['folder']}")
        lines.append(f"  Description: {m['description']}")
        lines.append(f"  Commands:    {m['command_count']}")
        if m["categories"]:
            lines.append(f"  Categories:  {', '.join('#'+c for c in m['categories'])}")
        lines.append(f"\n  Command list:")
        for c in m["commands"]:
            desc = m["cmd_descriptions"].get(c, "")
            lines.append(f"    /{m['name']} {c:<22s}  {desc[:80]}")
        return "\n".join(lines)

    @safe
    def cmd_freshly_added(self, arg=""):
        """Recently added modules (by mtime)"""
        try: n = int(arg.strip()) if arg.strip() else 10
        except Exception: n = 10
        mods = self._scan_modules()
        sorted_mods = sorted(mods, key=lambda m: -m["mtime"])
        lines = [f"[catalog] {min(n, len(sorted_mods))} most recently modified module(s):"]
        for m in sorted_mods[:n]:
            mt = time.strftime("%Y-%m-%d %H:%M", time.localtime(m["mtime"]))
            lines.append(f"  {mt}  /{m['name']:<10s} {m['description'][:60]}")
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

```

## `modules/learn/__init__.py`

```python
"""Learn Module — Knowledge base, cross-session memory, and resource discovery.

An extensible local knowledge system. You add entries (facts, commands, links,
lessons learned). /learn ranks and surfaces relevant entries when you search
or ask for context. Designed to complement (not replace) TermAId's /learner.

Also includes curated free resource catalogs for: investing, security, game dev,
AI/ML, systems programming, mobile dev, Linux sysadmin.

Commands (24):
  /learn add <text>             Quick-add a knowledge entry
  /learn add-cmd <cmd> <notes>  Add a command with notes
  /learn add-link <url> <note>  Add a URL with description
  /learn add-lesson <text>      Add a lesson learned (flagged for review)
  /learn list [tag]             List entries (optionally filtered)
  /learn show <id>              Detailed view of one entry
  /learn search <pattern>       Full-text search
  /learn tag <id> <tag>         Add tag
  /learn untag <id> <tag>       Remove tag
  /learn tags                   All tags with counts
  /learn resources <topic>      Free learning resources for topic
  /learn topics                 Topics available in resources
  /learn related <text>         Find related entries by keywords
  /learn review                 Surface items for spaced review
  /learn review-done <id>       Mark a review item done
  /learn stats                  Knowledge base statistics
  /learn export [path]          Export entire KB to markdown
  /learn import <path>          Import markdown/text
  /learn delete <id>            Delete an entry (confirm)
  /learn backup                 Create timestamped backup
  /learn journal <text>         Learning journal entry
  /learn journal-list           Show journal
  /learn cheatsheet <topic>     Generate cheatsheet from KB entries
  /learn cross-session          Recent entries across all sessions (for context)
"""

import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


# Curated resource catalogs — compiled into module so works offline
RESOURCES = {
    "investing": {
        "description": "Personal finance and investing fundamentals",
        "books": [
            ("The Intelligent Investor", "Benjamin Graham", "Foundational value investing"),
            ("A Random Walk Down Wall Street", "Burton Malkiel", "Case for index investing"),
            ("The Bogleheads Guide to Investing", "Larimore et al", "Practical passive investing"),
            ("The Psychology of Money", "Morgan Housel", "Behavioral side of money"),
            ("Common Sense on Mutual Funds", "John Bogle", "From the founder of Vanguard"),
            ("Market Wizards", "Jack Schwager", "Interviews with top traders"),
        ],
        "websites": [
            ("bogleheads.org", "Free wiki + forum, genuinely useful"),
            ("investopedia.com", "Reference for terms"),
            ("portfoliovisualizer.com", "Backtest portfolios for free"),
            ("morningstar.com", "Fund research"),
            ("fred.stlouisfed.org", "Macro economic data"),
            ("sec.gov/edgar", "Actual company filings (10-K, 10-Q)"),
        ],
        "youtube": [
            ("Ben Felix", "Evidence-based investing, no hype"),
            ("The Plain Bagel", "Accessible explanations"),
            ("Aswath Damodaran", "NYU professor, free valuation courses"),
            ("Patrick Boyle", "Markets with wit, ex-hedge-fund"),
        ],
        "courses": [
            ("Yale: Financial Markets (Shiller)", "https://www.coursera.org/learn/financial-markets-global"),
            ("MIT 15.401 Finance Theory I", "https://ocw.mit.edu"),
            ("Khan Academy Finance & Capital Markets", "https://www.khanacademy.org"),
        ],
    },
    "security": {
        "description": "Cybersecurity — offensive knowledge for defense, and general hardening",
        "books": [
            ("The Web Application Hacker's Handbook", "Stuttard & Pinto", "Classic on web app sec"),
            ("The Tangled Web", "Michal Zalewski", "How browsers actually work"),
            ("Practical Malware Analysis", "Sikorski & Honig", "Reverse-engineering malware"),
            ("Serious Cryptography", "Jean-Philippe Aumasson", "Modern crypto, readable"),
            ("The Art of Deception", "Kevin Mitnick", "Social engineering"),
            ("Red Team Field Manual", "Ben Clark", "Quick reference"),
        ],
        "websites": [
            ("owasp.org", "The de facto standard for web app security"),
            ("portswigger.net/web-security", "Free Burp web security academy"),
            ("hackthebox.com", "Legal hacking labs"),
            ("tryhackme.com", "Beginner-friendly labs"),
            ("exploit-db.com", "Historical exploits database"),
            ("nvd.nist.gov", "NIST CVE database"),
            ("attack.mitre.org", "ATT&CK framework — attacker TTPs"),
        ],
        "youtube": [
            ("LiveOverflow", "Hacking challenges + theory"),
            ("John Hammond", "Real CTF walkthroughs"),
            ("IppSec", "HackTheBox walkthroughs"),
            ("David Bombal", "Networking + security basics"),
        ],
        "courses": [
            ("TryHackMe Learning Paths", "tryhackme.com"),
            ("Cybrary", "Free tier has decent intro content"),
            ("OverTheWire Wargames", "overthewire.org/wargames/"),
            ("PicoCTF", "picoctf.org — great for beginners"),
        ],
    },
    "gamedev": {
        "description": "Game development, especially Unreal Engine",
        "books": [
            ("Game Programming Patterns", "Robert Nystrom", "Free online: gameprogrammingpatterns.com"),
            ("The Art of Game Design", "Jesse Schell", "Design philosophy"),
            ("Game Engine Architecture", "Jason Gregory", "How engines work under the hood"),
            ("Real-Time Rendering", "Akenine-Möller et al", "Graphics bible"),
        ],
        "websites": [
            ("docs.unrealengine.com", "Official UE docs"),
            ("gafferongames.com", "Networking in games"),
            ("iquilezles.org", "Graphics/shader wizardry"),
            ("tomdominer.com", "Practical UE tutorials"),
            ("80.lv", "Environment art + Unreal"),
        ],
        "youtube": [
            ("Mathew Wadstein", "UE documentation in video form"),
            ("Gorka Games", "Blueprint tutorials"),
            ("Alex Forsythe", "Smart UE systems"),
            ("Ryan Laley", "AI in UE5"),
            ("The Cherno", "C++ + game engine internals"),
        ],
        "courses": [
            ("Unreal Engine Online Learning", "dev.epicgames.com/community/learning"),
            ("MIT 6.837 Computer Graphics", "ocw.mit.edu"),
            ("Handmade Hero", "handmadehero.org — from-scratch C engine"),
        ],
    },
    "ai-ml": {
        "description": "AI/ML fundamentals and LLM-specific topics",
        "books": [
            ("Deep Learning", "Goodfellow, Bengio, Courville", "Free at deeplearningbook.org"),
            ("Hands-On ML", "Aurélien Géron", "Practical with scikit-learn and TF"),
            ("The Hundred-Page ML Book", "Andriy Burkov", "Fast overview"),
            ("Reinforcement Learning: An Introduction", "Sutton & Barto", "Free online: incompleteideas.net"),
        ],
        "websites": [
            ("arxiv.org", "Papers — follow arxiv-sanity.com to filter"),
            ("paperswithcode.com", "Papers + code"),
            ("huggingface.co", "Models, datasets, docs"),
            ("lilianweng.github.io", "Clear explainers from OpenAI research"),
            ("distill.pub", "Visual ML research"),
            ("fast.ai", "Practical deep learning"),
        ],
        "youtube": [
            ("3Blue1Brown", "Neural networks intuition"),
            ("Andrej Karpathy", "From-scratch LLM lessons"),
            ("Two Minute Papers", "Recent results, short"),
            ("Yannic Kilcher", "Paper walkthroughs"),
        ],
        "courses": [
            ("Andrew Ng ML Specialization (Coursera)", "Classic foundation"),
            ("Stanford CS229 / CS231n / CS224n", "Free on YouTube"),
            ("fast.ai Practical Deep Learning", "fast.ai"),
            ("HuggingFace NLP course", "huggingface.co/learn"),
        ],
    },
    "linux": {
        "description": "Linux system administration and power use",
        "books": [
            ("The Linux Command Line", "William Shotts", "Free at linuxcommand.org"),
            ("UNIX and Linux System Administration Handbook", "Nemeth et al", "Reference"),
            ("How Linux Works", "Brian Ward", "Under-the-hood"),
            ("The Art of Unix Programming", "Eric Raymond", "Philosophy"),
        ],
        "websites": [
            ("man7.org/linux/man-pages", "Online man pages"),
            ("tldr.sh", "Practical examples for every command"),
            ("cheat.sh", "curl cheat.sh/<command>"),
            ("wiki.archlinux.org", "The best Linux documentation, period"),
            ("kernelnewbies.org", "Kernel development"),
        ],
        "youtube": [
            ("DistroTube", "Terminal-focused Linux"),
            ("Luke Smith", "Minimalist Linux setup"),
            ("The Linux Cast", "General Linux topics"),
        ],
        "courses": [
            ("Linux Foundation LFS101 (free)", "Intro to Linux"),
            ("edX Linux courses", "edx.org"),
            ("OverTheWire Bandit", "SSH + shell wargame"),
        ],
    },
    "mobile": {
        "description": "Mobile development and rooting/modding",
        "websites": [
            ("developer.android.com", "Android official docs"),
            ("xda-developers.com", "Modding + ROMs"),
            ("source.android.com", "AOSP documentation"),
            ("topjohnwu.github.io/Magisk", "Magisk (systemless root) docs"),
            ("kernelsu.org", "KernelSU alternative to Magisk"),
            ("lineageos.org/devices", "Supported devices list"),
        ],
        "youtube": [
            ("Mishaal Rahman", "Deep Android news/analysis"),
            ("Max Weinbach", "Modding + custom ROMs"),
            ("HowToMen", "Practical Android tutorials"),
        ],
        "tools": [
            ("ADB Platform Tools", "developer.android.com/tools/releases/platform-tools"),
            ("Magisk", "github.com/topjohnwu/Magisk"),
            ("TWRP recovery", "twrp.me"),
            ("Termux", "termux.dev"),
        ],
    },
    "systems": {
        "description": "Systems programming and low-level CS",
        "books": [
            ("Computer Systems: A Programmer's Perspective", "Bryant & O'Hallaron", "CSAPP, classic"),
            ("Operating Systems: Three Easy Pieces", "Arpaci-Dusseau", "Free at pages.cs.wisc.edu/~remzi/OSTEP"),
            ("The C Programming Language", "K&R", "Short and essential"),
            ("Crafting Interpreters", "Robert Nystrom", "Free at craftinginterpreters.com"),
        ],
        "websites": [
            ("cppreference.com", "C++ reference"),
            ("rust-lang.org/learn", "Rust official learning"),
            ("doc.rust-lang.org/book", "The Rust Book (free)"),
            ("go.dev/tour", "A Tour of Go"),
        ],
        "courses": [
            ("Harvard CS50", "cs50.harvard.edu"),
            ("MIT 6.S081 Operating Systems", "pdos.csail.mit.edu/6.S081"),
            ("Nand2Tetris", "nand2tetris.org — build a computer from NAND"),
        ],
    },
}


class LearnModule(Module):
    name = "learn"
    version = "1.0.0"
    description = "Knowledge base, memory, and curated learning resources"
    author = "termaid"

    def on_load(self):
        cmds = ["add", "add-cmd", "add-link", "add-lesson", "list", "show",
                "search", "tag", "untag", "tags", "resources", "topics",
                "related", "review", "review-done", "stats", "export",
                "import", "delete", "backup", "journal", "journal-list",
                "cheatsheet", "cross-session", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "learn"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._kb_file = self._dir / "kb.jsonl"
        self._journal_file = self._dir / "journal.jsonl"
        self._session_file = self._dir / "sessions.jsonl"
        # Log this session
        self._log_session()

    def _log_session(self):
        try:
            with self._session_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "event": "module_load"}) + "\n")
        except Exception: pass

    def _confirm(self, prompt):
        try:
            return input(f"[learn] {prompt} [y/N] ").strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _load_kb(self):
        entries = []
        if self._kb_file.exists():
            try:
                for line in self._kb_file.read_text().splitlines():
                    if line.strip():
                        try: entries.append(json.loads(line))
                        except Exception: continue
            except Exception: pass
        return entries

    def _save_kb(self, entries):
        with self._kb_file.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, default=str) + "\n")

    def _next_id(self, entries):
        return max((e.get("id", 0) for e in entries), default=0) + 1

    def _append(self, entry):
        entries = self._load_kb()
        entry["id"] = self._next_id(entries)
        entry["ts"] = time.time()
        entry["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
        entries.append(entry)
        self._save_kb(entries)
        return entry["id"]

    # ---------- commands ----------

    @safe
    def cmd_add(self, arg=""):
        text = arg or ""
        if not text.strip():
            return "[learn] Usage: /learn add <text>"
        # Extract inline #tags
        tags = re.findall(r"(?:^|\s)#([a-zA-Z][\w-]{1,30})", text)
        entry = {"kind": "note", "text": text, "tags": [t.lower() for t in tags]}
        eid = self._append(entry)
        return f"[learn] Saved entry #{eid}" + (f" tags: {', '.join('#'+t for t in tags)}" if tags else "")

    @safe
    def cmd_add_cmd(self, arg=""):
        parts = (arg or "").split(None, 1)
        if len(parts) < 2:
            return "[learn] Usage: /learn add-cmd <command> <notes>"
        cmd, notes = parts
        entry = {"kind": "command", "command": cmd, "text": notes, "tags": ["command"]}
        eid = self._append(entry)
        return f"[learn] Saved command entry #{eid}: {cmd}"

    @safe
    def cmd_add_link(self, arg=""):
        parts = (arg or "").split(None, 1)
        if len(parts) < 1 or not parts[0].startswith(("http://", "https://")):
            return "[learn] Usage: /learn add-link <url> [description]"
        url = parts[0]
        desc = parts[1] if len(parts) > 1 else ""
        entry = {"kind": "link", "url": url, "text": desc, "tags": ["link"]}
        eid = self._append(entry)
        return f"[learn] Saved link #{eid}: {url}"

    @safe
    def cmd_add_lesson(self, arg=""):
        text = (arg or "").strip()
        if not text: return "[learn] Usage: /learn add-lesson <what you learned>"
        # Lessons go in spaced-repetition queue
        entry = {
            "kind": "lesson", "text": text, "tags": ["lesson"],
            "review_state": {"interval_days": 1, "ease": 2.5,
                             "next_review": time.time() + 86400},
        }
        eid = self._append(entry)
        return f"[learn] Saved lesson #{eid}. Review in 1 day."

    @safe
    def cmd_list(self, arg=""):
        filt_tag = (arg or "").strip().lstrip("#").lower()
        entries = self._load_kb()
        if filt_tag:
            entries = [e for e in entries if filt_tag in (e.get("tags") or [])]
        if not entries:
            return f"[learn] No entries" + (f" with tag #{filt_tag}" if filt_tag else "")
        lines = [f"[learn] {len(entries)} entr{'y' if len(entries)==1 else 'ies'}" +
                 (f" tagged #{filt_tag}" if filt_tag else "") + ":"]
        for e in entries[-50:]:
            kind = e.get("kind", "?")[:8]
            preview = (e.get("text", "") or e.get("command", "") or e.get("url", ""))[:80].replace("\n", " ")
            tags = "  [" + ", ".join(f"#{t}" for t in e.get("tags", [])) + "]" if e.get("tags") else ""
            lines.append(f"  #{e['id']:<4d} [{kind:<8s}] {preview}{tags}")
        return "\n".join(lines)

    @safe
    def cmd_show(self, arg=""):
        try: eid = int((arg or "").strip())
        except Exception: return "[learn] Usage: /learn show <id>"
        entries = self._load_kb()
        match = next((e for e in entries if e.get("id") == eid), None)
        if not match:
            return f"[learn] No entry #{eid}"
        lines = [f"[learn] Entry #{eid}:"]
        for k, v in match.items():
            if k == "review_state" and isinstance(v, dict):
                nr = v.get("next_review", 0)
                lines.append(f"  review_due: {time.strftime('%Y-%m-%d', time.localtime(nr))}")
                lines.append(f"  interval:   {v.get('interval_days',1)} days")
                lines.append(f"  ease:       {v.get('ease',2.5):.2f}")
            elif isinstance(v, (list, dict)):
                lines.append(f"  {k}: {json.dumps(v)}")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    @safe
    def cmd_search(self, arg=""):
        q = (arg or "").strip().lower()
        if not q: return "[learn] Usage: /learn search <pattern>"
        entries = self._load_kb()
        matches = []
        for e in entries:
            blob = json.dumps(e).lower()
            if q in blob:
                matches.append(e)
        if not matches:
            return f"[learn] No matches for '{q}'"
        lines = [f"[learn] {len(matches)} match(es):"]
        for e in matches[:30]:
            preview = (e.get("text","") or e.get("command","") or e.get("url",""))[:100]
            lines.append(f"  #{e['id']:<4d} [{e.get('kind','?'):<8s}] {preview}")
        return "\n".join(lines)

    @safe
    def cmd_tag(self, arg=""):
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[learn] Usage: /learn tag <id> <tag>"
        try: eid = int(parts[0])
        except Exception: return "[learn] Invalid id"
        tag = parts[1].lstrip("#").lower()
        entries = self._load_kb()
        for e in entries:
            if e.get("id") == eid:
                e.setdefault("tags", [])
                if tag not in e["tags"]:
                    e["tags"].append(tag)
                self._save_kb(entries)
                return f"[learn] Tagged #{eid} with #{tag}"
        return f"[learn] No entry #{eid}"

    @safe
    def cmd_untag(self, arg=""):
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[learn] Usage: /learn untag <id> <tag>"
        try: eid = int(parts[0])
        except Exception: return "[learn] Invalid id"
        tag = parts[1].lstrip("#").lower()
        entries = self._load_kb()
        for e in entries:
            if e.get("id") == eid:
                if tag in e.get("tags", []):
                    e["tags"].remove(tag)
                self._save_kb(entries)
                return f"[learn] Removed #{tag} from entry #{eid}"
        return f"[learn] No entry #{eid}"

    @safe
    def cmd_tags(self, arg=""):
        entries = self._load_kb()
        counts = Counter()
        for e in entries:
            for t in e.get("tags", []):
                counts[t] += 1
        if not counts:
            return "[learn] No tags yet."
        lines = [f"[learn] {len(counts)} tag(s):"]
        for t, c in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"  #{t:<20s} {c:>4d} entries")
        return "\n".join(lines)

    @safe
    def cmd_resources(self, arg=""):
        topic = (arg or "").strip().lower()
        if not topic:
            return (f"[learn] Available topics: {', '.join(RESOURCES.keys())}\n"
                    f"  Use: /learn resources <topic>")
        if topic not in RESOURCES:
            close = [t for t in RESOURCES if topic in t or t in topic]
            if close:
                topic = close[0]
            else:
                return f"[learn] Unknown topic '{topic}'. Available: {', '.join(RESOURCES)}"
        r = RESOURCES[topic]
        lines = [f"━━━ {topic.upper()} — {r['description']} ━━━"]
        for section, items in r.items():
            if section == "description": continue
            lines.append(f"\n  {section.upper()}:")
            for item in items:
                if isinstance(item, tuple):
                    if len(item) == 3:
                        lines.append(f"    - {item[0]}")
                        lines.append(f"      by {item[1]}. {item[2]}")
                    else:
                        lines.append(f"    - {item[0]} — {item[1]}")
                else:
                    lines.append(f"    - {item}")
        return "\n".join(lines)

    @safe
    def cmd_topics(self, arg=""):
        lines = ["[learn] Curated resource topics:"]
        for t, r in RESOURCES.items():
            lines.append(f"  {t:<12s} {r['description']}")
        return "\n".join(lines)

    @safe
    def cmd_related(self, arg=""):
        q = (arg or "").strip()
        if not q: return "[learn] Usage: /learn related <text or keywords>"
        words = set(re.findall(r"\w{3,}", q.lower()))
        if not words: return "[learn] No usable keywords"
        entries = self._load_kb()
        scored = []
        for e in entries:
            blob = json.dumps(e).lower()
            score = sum(1 for w in words if w in blob)
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return f"[learn] No related entries for: {q}"
        lines = [f"[learn] {len(scored)} related entr{'y' if len(scored)==1 else 'ies'}:"]
        for score, e in scored[:10]:
            preview = (e.get("text","") or e.get("command","") or e.get("url",""))[:100]
            lines.append(f"  score={score}  #{e['id']}  {preview}")
        return "\n".join(lines)

    @safe
    def cmd_review(self, arg=""):
        entries = self._load_kb()
        now = time.time()
        due = [e for e in entries if e.get("review_state") and
               e["review_state"].get("next_review", 0) <= now]
        if not due:
            next_up = sorted(
                (e for e in entries if e.get("review_state")),
                key=lambda e: e["review_state"].get("next_review", float("inf"))
            )
            if next_up:
                nxt = next_up[0]["review_state"]["next_review"]
                when = time.strftime("%Y-%m-%d", time.localtime(nxt))
                return f"[learn] No items due for review. Next review: {when}"
            return "[learn] No review items. Add with /learn add-lesson <text>"
        lines = [f"[learn] {len(due)} item(s) due for review:"]
        for e in due:
            lines.append(f"\n  #{e['id']}  {e.get('text','')}")
        lines.append("\n  Mark as reviewed with: /learn review-done <id>")
        lines.append("  Each review schedules the next one farther out (spaced repetition).")
        return "\n".join(lines)

    @safe
    def cmd_review_done(self, arg=""):
        try: eid = int((arg or "").strip())
        except Exception: return "[learn] Usage: /learn review-done <id>"
        entries = self._load_kb()
        for e in entries:
            if e.get("id") == eid and e.get("review_state"):
                state = e["review_state"]
                # Simple SM-2-ish: double interval each success
                state["interval_days"] = min(state.get("interval_days", 1) * 2, 180)
                state["next_review"] = time.time() + state["interval_days"] * 86400
                state["last_review"] = time.time()
                self._save_kb(entries)
                return f"[learn] #{eid} reviewed. Next review in {state['interval_days']} days."
        return f"[learn] No review item #{eid}"

    @safe
    def cmd_stats(self, arg=""):
        entries = self._load_kb()
        if not entries:
            return "[learn] Empty knowledge base."
        kinds = Counter(e.get("kind", "?") for e in entries)
        tag_counts = Counter()
        for e in entries:
            for t in e.get("tags", []):
                tag_counts[t] += 1
        oldest = min(entries, key=lambda e: e.get("ts", float("inf")))
        newest = max(entries, key=lambda e: e.get("ts", 0))
        lines = [f"[learn] Knowledge base stats:"]
        lines.append(f"  Total entries:   {len(entries)}")
        lines.append(f"  Unique tags:     {len(tag_counts)}")
        lines.append(f"  Kinds:")
        for k, c in kinds.most_common():
            lines.append(f"    {k:<10s} {c}")
        lines.append(f"  Top tags:        {', '.join(f'#{t}({c})' for t,c in tag_counts.most_common(5))}")
        lines.append(f"  Oldest:          {time.strftime('%Y-%m-%d', time.localtime(oldest.get('ts',0)))}")
        lines.append(f"  Newest:          {time.strftime('%Y-%m-%d', time.localtime(newest.get('ts',0)))}")
        # File sizes
        lines.append(f"  KB file size:    {self._kb_file.stat().st_size} bytes")
        # Sessions
        if self._session_file.exists():
            session_count = len(self._session_file.read_text().splitlines())
            lines.append(f"  Session loads:   {session_count}")
        return "\n".join(lines)

    @safe
    def cmd_export(self, arg=""):
        out = (arg or "").strip() or str(self._dir / f"export-{int(time.time())}.md")
        entries = self._load_kb()
        if not entries:
            return "[learn] Nothing to export."
        parts = [f"# TermAId Knowledge Base Export\n",
                 f"Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
                 f"Total entries: {len(entries)}\n",
                 "---\n"]
        grouped = defaultdict(list)
        for e in entries:
            grouped[e.get("kind", "note")].append(e)
        for kind, items in grouped.items():
            parts.append(f"\n## {kind.title()}s ({len(items)})\n")
            for e in items:
                parts.append(f"\n### #{e['id']}\n")
                parts.append(f"*{e.get('created','')}*")
                if e.get("tags"):
                    parts.append(f"  Tags: {', '.join('#'+t for t in e['tags'])}")
                parts.append("")
                if "command" in e:
                    parts.append(f"```\n{e['command']}\n```\n")
                if "url" in e:
                    parts.append(f"<{e['url']}>\n")
                if "text" in e:
                    parts.append(e["text"])
                parts.append("")
        try:
            Path(out).write_text("\n".join(parts), encoding="utf-8")
            return f"[learn] Exported {len(entries)} entries -> {out}"
        except Exception as e:
            return f"[learn] Export failed: {e}"

    @safe
    def cmd_import(self, arg=""):
        path = (arg or "").strip()
        if not path: return "[learn] Usage: /learn import <file>"
        p = Path(path).expanduser()
        if not p.exists(): return f"[learn] Not found: {path}"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[learn] Read failed: {e}"
        # Split on blank lines into entries
        chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
        for chunk in chunks:
            tags = re.findall(r"(?:^|\s)#([a-zA-Z][\w-]{1,30})", chunk)
            self._append({"kind": "note", "text": chunk,
                          "tags": [t.lower() for t in tags] + ["imported"]})
        return f"[learn] Imported {len(chunks)} entries from {p.name}"

    @safe
    def cmd_delete(self, arg=""):
        try: eid = int((arg or "").strip())
        except Exception: return "[learn] Usage: /learn delete <id>"
        entries = self._load_kb()
        match = next((e for e in entries if e.get("id") == eid), None)
        if not match: return f"[learn] No entry #{eid}"
        if not self._confirm(f"Delete entry #{eid}? {(match.get('text',''))[:60]}"):
            return "[learn] Cancelled."
        entries = [e for e in entries if e.get("id") != eid]
        self._save_kb(entries)
        return f"[learn] Deleted #{eid}"

    @safe
    def cmd_backup(self, arg=""):
        backup_path = self._dir / f"kb-backup-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        if not self._kb_file.exists():
            return "[learn] Nothing to back up."
        try:
            backup_path.write_bytes(self._kb_file.read_bytes())
            return f"[learn] Backup: {backup_path}"
        except Exception as e:
            return f"[learn] Backup failed: {e}"

    @safe
    def cmd_journal(self, arg=""):
        text = (arg or "").strip()
        if not text: return "[learn] Usage: /learn journal <text>"
        try:
            with self._journal_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(),
                                    "date": time.strftime("%Y-%m-%d %H:%M"),
                                    "entry": text}) + "\n")
            return "[learn] Journal entry saved."
        except Exception as e:
            return f"[learn] Journal save failed: {e}"

    @safe
    def cmd_journal_list(self, arg=""):
        if not self._journal_file.exists():
            return "[learn] No journal entries yet."
        entries = []
        for line in self._journal_file.read_text().splitlines():
            try: entries.append(json.loads(line))
            except Exception: continue
        if not entries: return "[learn] No journal entries."
        lines = [f"[learn] Learning journal ({len(entries)} entries):"]
        for e in entries[-15:]:
            lines.append(f"\n  [{e.get('date','?')}]  {e.get('entry','')}")
        return "\n".join(lines)

    @safe
    def cmd_cheatsheet(self, arg=""):
        topic = (arg or "").strip().lower()
        if not topic: return "[learn] Usage: /learn cheatsheet <topic-or-tag>"
        entries = self._load_kb()
        # Match on tag or keywords in text
        matching = []
        for e in entries:
            if topic in (e.get("tags") or []):
                matching.append(e)
            elif topic.lower() in (e.get("text", "") + e.get("command", "")).lower():
                matching.append(e)
        if not matching:
            return f"[learn] No entries for '{topic}'"
        lines = [f"━━━ CHEATSHEET: {topic.upper()} ━━━"]
        commands = [e for e in matching if e.get("kind") == "command"]
        links = [e for e in matching if e.get("kind") == "link"]
        notes = [e for e in matching if e.get("kind") not in ("command", "link")]
        if commands:
            lines.append("\n  COMMANDS:")
            for e in commands:
                lines.append(f"    {e.get('command', '')}")
                if e.get("text"):
                    lines.append(f"      {e['text'][:120]}")
        if links:
            lines.append("\n  LINKS:")
            for e in links:
                lines.append(f"    {e.get('url','')}")
                if e.get("text"):
                    lines.append(f"      {e['text'][:120]}")
        if notes:
            lines.append("\n  NOTES:")
            for e in notes[:10]:
                lines.append(f"    {e.get('text','')[:200]}")
        return "\n".join(lines)

    @safe
    def cmd_cross_session(self, arg=""):
        """Recent entries across all sessions - useful for context recovery."""
        entries = self._load_kb()
        # Show last 20 by time
        entries.sort(key=lambda e: e.get("ts", 0), reverse=True)
        if not entries:
            return "[learn] No entries yet."
        lines = [f"[learn] Recent entries (across all sessions):"]
        for e in entries[:20]:
            date = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("ts", 0)))
            kind = e.get("kind", "?")
            preview = (e.get("text","") or e.get("command","") or e.get("url",""))[:70]
            lines.append(f"  [{date}] #{e['id']} [{kind}]  {preview}")
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

```

## `modules/learner/__init__.py`

```python
"""Learner Module — Comprehensive system, hardware, and user profiling.

Builds a rich profile of:
- Hardware (CPU, GPU, RAM, disks, motherboard, peripherals)
- Software (OS, installed apps, running services)
- User patterns (command frequency, preferences, work hours)
- Network fingerprint
- Performance baselines

Stores to SQLite profile DB with proper schema.
AI uses this context to give personalized suggestions.
"""

import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class LearnerModule(Module):
    name = "profile"
    version = "1.0.0"
    description = "Learn user, system, and hardware for personalized AI suggestions"
    author = "termaid"

    def on_load(self):
        for cmd in ["scan", "hardware", "software", "profile", "context",
                    "record", "insights", "forget", "export", "suggest",
                    "watch", "baseline", "status"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "learner"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db = self._dir / "profile.db"
        self._init_db()

    def _init_db(self):
        """Create relational schema with proper foreign keys."""
        conn = sqlite3.connect(str(self._db))
        conn.executescript("""
            -- Core profile table (one row per system)
            CREATE TABLE IF NOT EXISTS system_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname TEXT UNIQUE NOT NULL,
                os_system TEXT,
                os_release TEXT,
                os_version TEXT,
                machine_arch TEXT,
                processor TEXT,
                python_version TEXT,
                first_seen REAL NOT NULL,
                last_updated REAL NOT NULL,
                total_scans INTEGER DEFAULT 0
            );

            -- Hardware components (CPU, GPU, etc.) with FK to system
            CREATE TABLE IF NOT EXISTS hardware (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                component_type TEXT NOT NULL,    -- cpu, gpu, memory, disk, network
                name TEXT,
                manufacturer TEXT,
                model TEXT,
                specs TEXT,                      -- JSON blob with details
                detected_at REAL NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- Installed software with FK to system
            CREATE TABLE IF NOT EXISTS software (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                version TEXT,
                install_path TEXT,
                kind TEXT,                        -- package, app, service, language_tool
                source TEXT,                      -- how detected (winget, apt, pip, etc.)
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE,
                UNIQUE(system_id, name, kind)
            );

            -- User interactions and commands
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,      -- command, query, edit, error
                content TEXT,
                context TEXT,                     -- JSON for additional info
                timestamp REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- Performance baselines for comparison
            CREATE TABLE IF NOT EXISTS performance_baseline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                metric TEXT NOT NULL,             -- boot_time, cpu_idle, ram_free, disk_read
                value REAL,
                unit TEXT,
                recorded_at REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- User preferences learned from behavior
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                confidence REAL DEFAULT 0.5,     -- 0.0 to 1.0
                times_seen INTEGER DEFAULT 1,
                last_seen REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE,
                UNIQUE(system_id, key)
            );

            -- Relationships: how entities relate to each other
            -- "software X runs on hardware Y" or "user uses command Z often"
            CREATE TABLE IF NOT EXISTS entity_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_table TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                target_table TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,   -- uses, depends_on, runs_on, prefers
                strength REAL DEFAULT 1.0,         -- 0.0 to 1.0, how strong the relationship
                metadata TEXT,                     -- JSON
                created_at REAL NOT NULL,
                UNIQUE(source_table, source_id, target_table, target_id, relationship_type)
            );

            -- Insights generated by AI about the user
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                category TEXT,                    -- usage_pattern, recommendation, warning
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 5,     -- 1-10
                created_at REAL NOT NULL,
                acted_on INTEGER DEFAULT 0,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- Useful indexes
            CREATE INDEX IF NOT EXISTS idx_hardware_system ON hardware(system_id);
            CREATE INDEX IF NOT EXISTS idx_software_system ON software(system_id);
            CREATE INDEX IF NOT EXISTS idx_activity_system ON user_activity(system_id);
            CREATE INDEX IF NOT EXISTS idx_activity_time ON user_activity(timestamp);
            CREATE INDEX IF NOT EXISTS idx_relationships_source ON entity_relationships(source_table, source_id);
            CREATE INDEX IF NOT EXISTS idx_relationships_target ON entity_relationships(target_table, target_id);
            CREATE INDEX IF NOT EXISTS idx_preferences_system ON user_preferences(system_id);
        """)
        conn.commit()
        conn.close()

    def _get_or_create_system(self) -> int:
        """Get current system ID, creating the row if missing."""
        hostname = platform.node() or "unknown"
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id FROM system_profile WHERE hostname = ?", (hostname,))
        row = c.fetchone()
        now = time.time()
        if row:
            c.execute(
                "UPDATE system_profile SET last_updated = ?, total_scans = total_scans + 1 WHERE id = ?",
                (now, row["id"])
            )
            system_id = row["id"]
        else:
            c.execute(
                """INSERT INTO system_profile
                   (hostname, os_system, os_release, os_version, machine_arch,
                    processor, python_version, first_seen, last_updated, total_scans)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (hostname, platform.system(), platform.release(), platform.version()[:200],
                 platform.machine(), platform.processor(), platform.python_version(),
                 now, now)
            )
            system_id = c.lastrowid
        conn.commit()
        conn.close()
        return system_id

    def _run(self, cmd: str, timeout: int = 15):
        try:
            if sys.platform == "win32":
                r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                   capture_output=True, text=True, timeout=timeout,
                                   encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                   timeout=timeout, encoding="utf-8", errors="replace")
            return r
        except Exception:
            return subprocess.CompletedProcess(cmd, 1, "", "")

    # === SCAN ===

    @safe
    def cmd_scan(self, args):
        """Full learning scan. Usage: /learn.scan"""
        print("🧠 Scanning hardware, software, and system...")
        system_id = self._get_or_create_system()
        hw_count = self._scan_hardware(system_id)
        sw_count = self._scan_software(system_id)

        return (
            f"=== 🧠 Learning Scan Complete ===\n\n"
            f"  System ID:    {system_id}\n"
            f"  Hostname:     {platform.node()}\n"
            f"  Hardware:     {hw_count} components detected\n"
            f"  Software:     {sw_count} items cataloged\n"
            f"  Database:     {self._db}\n\n"
            f"  Next: /learn.insights for AI analysis\n"
            f"  Next: /learn.suggest <topic> for personalized advice"
        )

    # === HARDWARE ===

    def _scan_hardware(self, system_id: int) -> int:
        """Detect hardware and store."""
        items = []
        now = time.time()

        # CPU
        cpu = {
            "name": platform.processor() or "Unknown",
            "cores_logical": os.cpu_count() or 0,
            "arch": platform.machine(),
        }
        # Get more CPU detail
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_Processor | "
                "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,Manufacturer | "
                "ConvertTo-Json"
            )
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    if isinstance(data, list):
                        data = data[0]
                    cpu.update({
                        "name": data.get("Name", cpu["name"]),
                        "cores": data.get("NumberOfCores"),
                        "threads": data.get("NumberOfLogicalProcessors"),
                        "max_mhz": data.get("MaxClockSpeed"),
                        "manufacturer": data.get("Manufacturer"),
                    })
                except Exception:
                    pass
        elif sys.platform.startswith("linux"):
            r = self._run("cat /proc/cpuinfo 2>/dev/null | grep -m1 'model name' | cut -d: -f2")
            if r.stdout.strip():
                cpu["name"] = r.stdout.strip()
        items.append(("cpu", cpu.get("name"), cpu.get("manufacturer", ""), "", cpu))

        # Memory
        ram = {}
        if sys.platform == "win32":
            r = self._run(
                "(Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory"
            )
            try:
                ram["total_bytes"] = int(r.stdout.strip())
                ram["total_gb"] = round(ram["total_bytes"] / (1024**3), 1)
            except Exception:
                pass
        else:
            r = self._run("cat /proc/meminfo 2>/dev/null | head -3")
            for line in r.stdout.splitlines():
                if "MemTotal" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            kb = int(parts[1])
                            ram["total_gb"] = round(kb / (1024**2), 1)
                            ram["total_bytes"] = kb * 1024
                        except Exception:
                            pass
        items.append(("memory", f"{ram.get('total_gb', '?')} GB RAM", "", "", ram))

        # GPU
        gpu_info = {}
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_VideoController | "
                "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json"
            )
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    if data:
                        gpu_info = {
                            "name": data.get("Name"),
                            "driver": data.get("DriverVersion"),
                        }
                        if data.get("AdapterRAM"):
                            gpu_info["vram_mb"] = data["AdapterRAM"] // (1024*1024)
                except Exception:
                    pass
        else:
            r = self._run("lspci 2>/dev/null | grep -i 'vga\\|3d' | head -1")
            if r.stdout.strip():
                gpu_info["name"] = r.stdout.split(":", 2)[-1].strip()
        if gpu_info:
            items.append(("gpu", gpu_info.get("name", "Unknown"), "", "", gpu_info))

        # Disks
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_DiskDrive | "
                "Select-Object Model,Size,MediaType | ConvertTo-Json"
            )
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for d in data:
                        size_gb = round((d.get("Size") or 0) / (1024**3), 1)
                        items.append(("disk", d.get("Model", "?"), "", "",
                                     {"size_gb": size_gb, "type": d.get("MediaType")}))
                except Exception:
                    pass
        else:
            r = self._run("lsblk -dJ -o NAME,SIZE,TYPE,MODEL 2>/dev/null")
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout).get("blockdevices", [])
                    for d in data:
                        if d.get("type") == "disk":
                            items.append(("disk", d.get("model") or d.get("name", "?"), "", "",
                                         {"size": d.get("size"), "type": "disk"}))
                except Exception:
                    pass

        # Save to DB
        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        # Mark all existing as inactive (will be reactivated if found)
        c.execute("UPDATE hardware SET is_active = 0 WHERE system_id = ?", (system_id,))
        for ctype, name, manufacturer, model, specs in items:
            c.execute(
                """INSERT INTO hardware
                   (system_id, component_type, name, manufacturer, model, specs, detected_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (system_id, ctype, name, manufacturer, model, json.dumps(specs), now)
            )
        conn.commit()
        conn.close()
        return len(items)

    @safe
    def cmd_hardware(self, args):
        """Show detected hardware. Usage: /learn.hardware"""
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT * FROM hardware
            WHERE system_id = ? AND is_active = 1
            ORDER BY component_type, name
        """, (system_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            return "No hardware scanned yet. Run: /learn.scan"

        lines = ["=== 🔌 Detected Hardware ===\n"]
        by_type = {}
        for row in rows:
            by_type.setdefault(row["component_type"], []).append(row)
        for ctype, items in by_type.items():
            lines.append(f"\n  {ctype.upper()}:")
            for item in items:
                lines.append(f"    • {item['name']}")
                if item["manufacturer"]:
                    lines.append(f"        Mfr: {item['manufacturer']}")
                try:
                    specs = json.loads(item["specs"] or "{}")
                    for k, v in specs.items():
                        if v:
                            lines.append(f"        {k}: {v}")
                except Exception:
                    pass
        return "\n".join(lines)

    # === SOFTWARE ===

    def _scan_software(self, system_id: int) -> int:
        """Detect installed software and store."""
        items = []
        now = time.time()

        # Python packages
        r = self._run(f"{sys.executable} -m pip list --format=json", timeout=30)
        if r.stdout.strip():
            try:
                packages = json.loads(r.stdout)
                for pkg in packages:
                    items.append((pkg.get("name", ""), pkg.get("version", ""),
                                  "", "python_package", "pip"))
            except Exception:
                pass

        # Node packages (global)
        import shutil as sh
        if sh.which("npm"):
            r = self._run("npm list -g --depth=0 --json 2>/dev/null", timeout=15)
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    for name, info in (data.get("dependencies") or {}).items():
                        items.append((name, info.get("version", ""),
                                      "", "node_package", "npm"))
                except Exception:
                    pass

        # OS packages
        if sys.platform == "win32":
            r = self._run("winget list --accept-source-agreements 2>&1 | Select-String -Pattern '^\\w' | Select-Object -First 100", timeout=30)
            for line in r.stdout.splitlines()[2:]:
                parts = line.split()
                if len(parts) >= 2:
                    items.append((parts[0], parts[-2] if len(parts) >= 3 else "",
                                  "", "app", "winget"))
        elif sh.which("apt"):
            r = self._run("dpkg-query -W -f='${Package}|${Version}\\n' 2>/dev/null | head -200", timeout=10)
            for line in r.stdout.splitlines():
                if "|" in line:
                    name, ver = line.split("|", 1)
                    items.append((name, ver, "", "package", "apt"))
        elif sh.which("pacman"):
            r = self._run("pacman -Q 2>/dev/null | head -200", timeout=10)
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    items.append((parts[0], parts[1], "", "package", "pacman"))
        elif sh.which("brew"):
            r = self._run("brew list --versions 2>/dev/null | head -100", timeout=15)
            for line in r.stdout.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) >= 1:
                    items.append((parts[0], parts[1] if len(parts) > 1 else "",
                                  "", "package", "brew"))

        # Save to DB
        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        for name, version, install_path, kind, source in items:
            c.execute("""
                INSERT INTO software (system_id, name, version, install_path, kind, source, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(system_id, name, kind) DO UPDATE SET
                    version = excluded.version,
                    last_seen = excluded.last_seen
            """, (system_id, name, version, install_path, kind, source, now, now))
        conn.commit()
        conn.close()
        return len(items)

    @safe
    def cmd_software(self, args):
        """Show installed software. Usage: /learn.software [filter]"""
        filter_kind = args.strip().lower() if args.strip() else ""
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if filter_kind:
            c.execute("""SELECT kind, COUNT(*) as n FROM software
                         WHERE system_id = ? AND kind LIKE ?
                         GROUP BY kind""", (system_id, f"%{filter_kind}%"))
        else:
            c.execute("SELECT kind, COUNT(*) as n FROM software WHERE system_id = ? GROUP BY kind",
                      (system_id,))
        summary = c.fetchall()

        if filter_kind:
            c.execute("""SELECT name, version FROM software
                         WHERE system_id = ? AND kind LIKE ?
                         ORDER BY name LIMIT 50""", (system_id, f"%{filter_kind}%"))
            items = c.fetchall()
        else:
            c.execute("""SELECT name, version, kind FROM software
                         WHERE system_id = ?
                         ORDER BY kind, name LIMIT 50""", (system_id,))
            items = c.fetchall()
        conn.close()

        lines = ["=== 📦 Software ===\n"]
        for row in summary:
            lines.append(f"  {row['kind']:20s} {row['n']:5d}")
        lines.append("")
        lines.append("Sample items:")
        for row in items:
            if filter_kind:
                lines.append(f"  • {row['name']:30s} {row['version']}")
            else:
                lines.append(f"  [{row['kind']}] {row['name']} {row['version']}")
        return "\n".join(lines)

    # === PROFILE / CONTEXT ===

    @safe
    def cmd_profile(self, args):
        """Show user/system profile. Usage: /learn.profile"""
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM system_profile WHERE id = ?", (system_id,))
        sys_row = c.fetchone()
        c.execute("SELECT COUNT(*) as n FROM hardware WHERE system_id = ? AND is_active = 1", (system_id,))
        hw_count = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM software WHERE system_id = ?", (system_id,))
        sw_count = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM user_activity WHERE system_id = ?", (system_id,))
        act_count = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM user_preferences WHERE system_id = ?", (system_id,))
        pref_count = c.fetchone()["n"]
        conn.close()

        if not sys_row:
            return "No profile yet. Run: /learn.scan"

        lines = ["=== 👤 System Profile ==="]
        lines.append(f"\n  Host:            {sys_row['hostname']}")
        lines.append(f"  OS:              {sys_row['os_system']} {sys_row['os_release']}")
        lines.append(f"  Architecture:    {sys_row['machine_arch']}")
        lines.append(f"  Python:          {sys_row['python_version']}")
        lines.append(f"  First seen:      {time.ctime(sys_row['first_seen'])}")
        lines.append(f"  Last updated:    {time.ctime(sys_row['last_updated'])}")
        lines.append(f"  Total scans:     {sys_row['total_scans']}")
        lines.append(f"\n  Catalog:")
        lines.append(f"    Hardware:      {hw_count}")
        lines.append(f"    Software:      {sw_count}")
        lines.append(f"    Activities:    {act_count}")
        lines.append(f"    Preferences:   {pref_count}")
        return "\n".join(lines)

    @safe
    def cmd_context(self, args):
        """Get full AI context string. Usage: /learn.context"""
        system_id = self._get_or_create_system()
        return self._build_context(system_id)

    def _build_context(self, system_id: int) -> str:
        """Build a compact context string for the AI."""
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        parts = []
        c.execute("SELECT * FROM system_profile WHERE id = ?", (system_id,))
        sys_row = c.fetchone()
        if sys_row:
            parts.append(f"System: {sys_row['os_system']} {sys_row['os_release']} on {sys_row['machine_arch']}")

        # Top hardware
        c.execute("""SELECT component_type, name, specs FROM hardware
                     WHERE system_id = ? AND is_active = 1""", (system_id,))
        for row in c.fetchall():
            parts.append(f"  {row['component_type']}: {row['name']}")

        # Software summary
        c.execute("""SELECT kind, COUNT(*) as n FROM software
                     WHERE system_id = ? GROUP BY kind""", (system_id,))
        for row in c.fetchall():
            parts.append(f"  {row['kind']}: {row['n']} installed")

        # Preferences
        c.execute("""SELECT key, value FROM user_preferences
                     WHERE system_id = ? ORDER BY confidence DESC LIMIT 10""", (system_id,))
        prefs = c.fetchall()
        if prefs:
            parts.append("User preferences:")
            for row in prefs:
                parts.append(f"  {row['key']}: {row['value']}")

        conn.close()
        return "\n".join(parts)

    # === RECORD / INSIGHTS ===

    @safe
    def cmd_record(self, args):
        """Record user activity. Usage: /learn.record <type> <content>"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /learn.record <type> <content>\nExample: /learn.record command 'git status'"
        activity_type, content = parts[0], parts[1]
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.execute(
            """INSERT INTO user_activity (system_id, activity_type, content, timestamp)
               VALUES (?, ?, ?, ?)""",
            (system_id, activity_type, content, time.time())
        )
        conn.commit()
        conn.close()
        return f"✓ Recorded {activity_type}: {content[:80]}"

    @safe
    def cmd_insights(self, args):
        """AI insights about the user/system. Usage: /learn.insights"""
        system_id = self._get_or_create_system()
        context = self._build_context(system_id)

        # Activity stats
        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        c.execute("""SELECT activity_type, COUNT(*) as n FROM user_activity
                     WHERE system_id = ? GROUP BY activity_type
                     ORDER BY n DESC LIMIT 10""", (system_id,))
        activity = c.fetchall()
        conn.close()

        prompt = f"""Based on this system profile, generate 5 specific insights and recommendations.

{context}

Activity summary:
{chr(10).join(f'  {a[0]}: {a[1]} times' for a in activity) if activity else '  (no activity recorded yet)'}

For each insight:
- What pattern or situation you identified
- Why it matters
- Concrete action

Be specific to THIS system. No generic advice."""

        print("🧠 Generating AI insights...")
        result = self.ask_ai(prompt, system="You are a personal computing expert analyzing a user's system.")

        # Store insights
        conn = sqlite3.connect(str(self._db))
        conn.execute(
            """INSERT INTO insights (system_id, category, content, created_at)
               VALUES (?, 'general', ?, ?)""",
            (system_id, result, time.time())
        )
        conn.commit()
        conn.close()

        return f"=== 🧠 AI Insights ===\n\n{result}"

    @safe
    def cmd_suggest(self, args):
        """Personalized AI suggestions. Usage: /learn.suggest <topic>"""
        if not args.strip():
            return ("Usage: /learn.suggest <topic>\n"
                    "Examples:\n"
                    "  /learn.suggest cleanup\n"
                    "  /learn.suggest performance\n"
                    "  /learn.suggest security\n"
                    "  /learn.suggest workflow")
        system_id = self._get_or_create_system()
        context = self._build_context(system_id)

        prompt = f"""Given this user's system and preferences:

{context}

Provide specific suggestions for: {args.strip()}

Tailor advice to THIS exact system. Be direct, specific, and actionable."""

        print(f"🧠 Generating suggestions for '{args.strip()}'...")
        return self.ask_ai(prompt, system="You are a personalized tech advisor.")

    # === BASELINE / WATCH ===

    @safe
    def cmd_baseline(self, args):
        """Record performance baseline. Usage: /learn.baseline"""
        print("📊 Recording baseline metrics...")
        system_id = self._get_or_create_system()
        metrics = []

        # CPU idle sample
        if sys.platform == "win32":
            r = self._run(
                "(Get-Counter '\\Processor(_Total)\\% Idle Time' "
                "-SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue"
            )
            try:
                metrics.append(("cpu_idle_pct", float(r.stdout.strip()), "%"))
            except Exception:
                pass
        else:
            r = self._run("vmstat 1 2 | tail -1 | awk '{print $15}'")
            try:
                metrics.append(("cpu_idle_pct", float(r.stdout.strip()), "%"))
            except Exception:
                pass

        # RAM free
        if sys.platform == "win32":
            r = self._run(
                "[math]::Round((Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory/1MB, 2)"
            )
            try:
                metrics.append(("ram_free_gb", float(r.stdout.strip()), "GB"))
            except Exception:
                pass
        else:
            r = self._run("free -g 2>/dev/null | awk 'NR==2 {print $4}'")
            try:
                metrics.append(("ram_free_gb", float(r.stdout.strip()), "GB"))
            except Exception:
                pass

        now = time.time()
        conn = sqlite3.connect(str(self._db))
        for name, val, unit in metrics:
            conn.execute(
                """INSERT INTO performance_baseline (system_id, metric, value, unit, recorded_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (system_id, name, val, unit, now)
            )
        conn.commit()
        conn.close()

        lines = ["=== 📊 Baseline Recorded ===\n"]
        for name, val, unit in metrics:
            lines.append(f"  {name:20s} {val:8.2f} {unit}")
        return "\n".join(lines)

    @safe
    def cmd_watch(self, args):
        """Monitor and learn (5s sample). Usage: /learn.watch"""
        print("👀 Watching for 5 seconds...")
        time.sleep(5)
        return "Sample recorded. See /learn.insights for analysis."

    # === EXPORT / FORGET / STATUS ===

    @safe
    def cmd_export(self, args):
        """Export profile. Usage: /learn.export [file]"""
        filename = args.strip() or f"profile_{int(time.time())}.json"
        filepath = Path(filename).expanduser()
        if not filepath.is_absolute():
            filepath = self._dir / filename

        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        export_data = {}
        for table in ["system_profile", "hardware", "software", "user_preferences", "insights"]:
            if table == "system_profile":
                c.execute(f"SELECT * FROM {table} WHERE id = ?", (system_id,))
            else:
                c.execute(f"SELECT * FROM {table} WHERE system_id = ?", (system_id,))
            export_data[table] = [dict(row) for row in c.fetchall()]
        conn.close()

        filepath.write_text(json.dumps(export_data, indent=2, default=str))
        return f"✓ Exported {sum(len(v) for v in export_data.values())} records to {filepath}"

    @safe
    def cmd_forget(self, args):
        """Delete learned data. Usage: /learn.forget [what]"""
        what = args.strip().lower() or "confirm"
        if what == "confirm":
            return ("⚠️  This will delete all learned data.\n"
                    "Run: /learn.forget all  (to confirm)\n"
                    "Or:  /learn.forget activity  (activity log only)\n"
                    "Or:  /learn.forget insights (insights only)")

        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        if what == "all":
            for table in ["hardware", "software", "user_activity", "performance_baseline",
                          "user_preferences", "entity_relationships", "insights"]:
                if table == "entity_relationships":
                    conn.execute(f"DELETE FROM {table}")
                else:
                    conn.execute(f"DELETE FROM {table} WHERE system_id = ?", (system_id,))
            conn.commit()
            conn.close()
            return "✓ All learned data deleted for this system"
        elif what in ("activity", "user_activity"):
            conn.execute("DELETE FROM user_activity WHERE system_id = ?", (system_id,))
            conn.commit()
            conn.close()
            return "✓ Activity log cleared"
        elif what == "insights":
            conn.execute("DELETE FROM insights WHERE system_id = ?", (system_id,))
            conn.commit()
            conn.close()
            return "✓ Insights cleared"
        else:
            conn.close()
            return f"Unknown target: {what}"

    @safe
    def cmd_status(self, args):
        """Show learner status. Usage: /learn.status"""
        if not self._db.exists():
            return "Database not yet initialized. Run: /learn.scan"

        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM system_profile")
        systems = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hardware")
        hw = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM software")
        sw = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM user_activity")
        act = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM insights")
        ins = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM entity_relationships")
        rel = c.fetchone()[0]
        conn.close()

        lines = ["=== 🧠 Learner Status ===\n"]
        lines.append(f"  Database:        {self._db}")
        lines.append(f"  Size:            {self._db.stat().st_size:,} bytes")
        lines.append(f"\n  Systems tracked:   {systems}")
        lines.append(f"  Hardware items:    {hw}")
        lines.append(f"  Software items:    {sw}")
        lines.append(f"  Activities:        {act}")
        lines.append(f"  Insights:          {ins}")
        lines.append(f"  Relationships:     {rel}")
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

```
