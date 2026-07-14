"""Regex Module — Regex testing, debugging, and a small saved-pattern library.

Commands (~11):
  /regex test <pattern> <text>      Does the pattern match? Show all matches.
  /regex replace <pattern> <repl> <text>   re.sub
  /regex extract <pattern> <text>   All matches + named/numbered groups
  /regex findall <pattern> <text>   Alias of extract, flat list only
  /regex split <pattern> <text>     re.split
  /regex groups <pattern> <text>    Group breakdown for the first match
  /regex validate <pattern>         Is this a syntactically valid regex?
  /regex save <name> <pattern>      Save a pattern to the local library
  /regex list                       List saved patterns
  /regex cheatsheet                 Quick regex syntax reference
  /regex explain                    How this module works
"""

import json
import os
import re
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class RegexModule(Module):
    name = "regex"
    version = "1.0.0"
    description = "Regex testing, debugging, and library with AI assistance"
    author = "termaid"

    def on_load(self):
        for cmd in ["test", "replace", "extract", "findall", "split",
                    "groups", "validate", "save", "list", "cheatsheet", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "regex"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lib_file = self._dir / "library.json"

    def _load_lib(self) -> dict:
        if self._lib_file.exists():
            try:
                return json.loads(self._lib_file.read_text())
            except Exception:
                pass
        return {}

    def _save_lib(self, lib: dict) -> None:
        self._lib_file.write_text(json.dumps(lib, indent=2))

    @safe
    def cmd_test(self, arg=""):
        """Does the pattern match? Show all matches."""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[regex] Usage: /regex test <pattern> <text>"
        pattern, text = parts
        try:
            matches = list(re.finditer(pattern, text))
        except re.error as e:
            return f"[regex] Invalid pattern: {e}"
        if not matches:
            return "[regex] No match."
        lines = [f"[regex] {len(matches)} match(es):"]
        for m in matches[:20]:
            lines.append(f"  [{m.start()}:{m.end()}] '{m.group(0)}'")
        return "\n".join(lines)

    @safe
    def cmd_replace(self, arg=""):
        """re.sub: /regex replace <pattern> <repl> <text>"""
        parts = (arg or "").split(None, 2)
        if len(parts) != 3:
            return "[regex] Usage: /regex replace <pattern> <replacement> <text>"
        pattern, repl, text = parts
        try:
            return re.sub(pattern, repl, text)
        except re.error as e:
            return f"[regex] Invalid pattern: {e}"

    @safe
    def cmd_extract(self, arg=""):
        """All matches + named/numbered groups: /regex extract <pattern> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[regex] Usage: /regex extract <pattern> <text>"
        pattern, text = parts
        try:
            matches = list(re.finditer(pattern, text))
        except re.error as e:
            return f"[regex] Invalid pattern: {e}"
        if not matches:
            return "[regex] No matches."
        lines = [f"[regex] {len(matches)} match(es):"]
        for i, m in enumerate(matches[:20], 1):
            lines.append(f"  #{i}: '{m.group(0)}'")
            if m.groups():
                for gi, g in enumerate(m.groups(), 1):
                    lines.append(f"       group {gi}: {g!r}")
            if m.groupdict():
                for name, val in m.groupdict().items():
                    lines.append(f"       {name}: {val!r}")
        return "\n".join(lines)

    @safe
    def cmd_findall(self, arg=""):
        """Alias of extract, flat list only: /regex findall <pattern> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[regex] Usage: /regex findall <pattern> <text>"
        pattern, text = parts
        try:
            hits = re.findall(pattern, text)
        except re.error as e:
            return f"[regex] Invalid pattern: {e}"
        if not hits:
            return "[regex] No matches."
        return "\n".join(str(h) for h in hits)

    @safe
    def cmd_split(self, arg=""):
        """re.split: /regex split <pattern> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[regex] Usage: /regex split <pattern> <text>"
        pattern, text = parts
        try:
            pieces = re.split(pattern, text)
        except re.error as e:
            return f"[regex] Invalid pattern: {e}"
        return "\n".join(f"  [{i}] {p!r}" for i, p in enumerate(pieces))

    @safe
    def cmd_groups(self, arg=""):
        """Group breakdown for the first match: /regex groups <pattern> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[regex] Usage: /regex groups <pattern> <text>"
        pattern, text = parts
        try:
            m = re.search(pattern, text)
        except re.error as e:
            return f"[regex] Invalid pattern: {e}"
        if not m:
            return "[regex] No match."
        lines = [f"[regex] Full match: {m.group(0)!r}"]
        for i, g in enumerate(m.groups(), 1):
            lines.append(f"  group {i}: {g!r}")
        for name, val in m.groupdict().items():
            lines.append(f"  {name}: {val!r}")
        return "\n".join(lines)

    @safe
    def cmd_validate(self, arg=""):
        """Is this a syntactically valid regex?"""
        pattern = arg or ""
        if not pattern:
            return "[regex] Usage: /regex validate <pattern>"
        try:
            re.compile(pattern)
            return f"[regex] Valid: {pattern!r}"
        except re.error as e:
            return f"[regex] Invalid: {e}"

    @safe
    def cmd_save(self, arg=""):
        """Save a pattern to the local library: /regex save <name> <pattern>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[regex] Usage: /regex save <name> <pattern>"
        name, pattern = parts
        try:
            re.compile(pattern)
        except re.error as e:
            return f"[regex] Not saved — invalid pattern: {e}"
        lib = self._load_lib()
        lib[name] = pattern
        self._save_lib(lib)
        return f"[regex] Saved '{name}' -> {pattern!r}"

    @safe
    def cmd_list(self, arg=""):
        """List saved patterns"""
        lib = self._load_lib()
        if not lib:
            return "[regex] No saved patterns yet. /regex save <name> <pattern>"
        lines = [f"[regex] {len(lib)} saved pattern(s):"]
        for name, pattern in sorted(lib.items()):
            lines.append(f"  {name:<20s} {pattern}")
        return "\n".join(lines)

    @safe
    def cmd_cheatsheet(self, arg=""):
        """Quick regex syntax reference"""
        return (
            "[regex] Quick reference:\n"
            "  .        any character            \\d       digit\n"
            "  \\w       word character            \\s       whitespace\n"
            "  ^  $     start / end of string      *  +  ?  quantifiers (0+, 1+, 0-1)\n"
            "  {n,m}    n to m repeats              [...]    character class\n"
            "  (...)    capturing group             (?:...)  non-capturing group\n"
            "  (?P<n>..) named group                |        alternation\n"
            "  \\b       word boundary               (?=...)  lookahead"
        )

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
