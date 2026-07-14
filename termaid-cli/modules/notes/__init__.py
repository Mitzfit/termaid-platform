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
        """Delete a note: /notes delete <id-or-title> confirm"""
        parts = (arg or "").rsplit(None, 1)
        if len(parts) == 2 and parts[1].lower() == "confirm":
            target, confirmed = parts[0], True
        else:
            target, confirmed = arg, False
        p = self._resolve(target)
        if not p:
            return f"[notes] Not found: {target}"
        if not confirmed:
            return f"[notes] Delete '{p.name}' — re-run as: /notes delete {target} confirm"
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
