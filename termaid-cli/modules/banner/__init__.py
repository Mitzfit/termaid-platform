"""Banner Module — Dynamic rotating welcome banners with quotes.

Generates a login banner (ASCII wordmark + a rotating quote) and lets you
manage the quote list. `main.py`'s WebSocket handshake sends its own fixed
banner text independently of this module — call /banner show yourself to
get the richer version.

Commands (~9):
  /banner show               Full banner: wordmark + a quote
  /banner quote               Just a random quote
  /banner add-quote <text>    Add a custom quote
  /banner remove-quote <n>    Remove a quote by position (see /banner list-quotes)
  /banner list-quotes         List all quotes
  /banner random               Alias of /banner quote
  /banner wordmark              Just the ASCII wordmark, no quote
  /banner explain                How this module works
"""

import json
import os
import secrets
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_WORDMARK = r"""
 _____                 _    ___    _
|_   _|__ _ _ _ __ _ _\ \  / (_)__| |
  | |/ -_) '_/ _` | '  \ \/ /| / _` |
  |_|\___|_| \__,_|_|_|_\__/ |_\__,_|
"""

_DEFAULT_QUOTES = [
    "The terminal is the last honest UI.",
    "Automate the boring parts; think about the rest.",
    "A command you don't have to remember is a command you'll actually use.",
    "Small, composable tools beat one giant one.",
    "Ship the thing that works, then make it nice.",
]


class BannerModule(Module):
    name = "banner"
    version = "1.0.0"
    description = "Dynamic rotating welcome banners with quotes"
    author = "termaid"

    def on_load(self):
        for cmd in ["show", "quote", "add-quote", "remove-quote",
                    "list-quotes", "random", "wordmark", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "banner"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "quotes.json"
        if not self._file.exists():
            self._file.write_text(json.dumps(_DEFAULT_QUOTES, indent=2))

    def _load(self) -> list:
        try:
            return json.loads(self._file.read_text())
        except Exception:
            return list(_DEFAULT_QUOTES)

    def _save(self, quotes: list) -> None:
        self._file.write_text(json.dumps(quotes, indent=2))

    @safe
    def cmd_show(self, arg=""):
        """Full banner: wordmark + a quote"""
        quotes = self._load()
        quote = secrets.choice(quotes) if quotes else "(no quotes yet)"
        return f"{_WORDMARK}\n  \"{quote}\""

    @safe
    def cmd_quote(self, arg=""):
        """Just a random quote"""
        quotes = self._load()
        if not quotes:
            return "[banner] No quotes yet. /banner add-quote <text>"
        return secrets.choice(quotes)

    @safe
    def cmd_add_quote(self, arg=""):
        """Add a custom quote"""
        text = (arg or "").strip()
        if not text:
            return "[banner] Usage: /banner add-quote <text>"
        quotes = self._load()
        quotes.append(text)
        self._save(quotes)
        return f"[banner] Added quote #{len(quotes)}"

    @safe
    def cmd_remove_quote(self, arg=""):
        """Remove a quote by position"""
        try:
            idx = int((arg or "").strip())
        except Exception:
            return "[banner] Usage: /banner remove-quote <position>"
        quotes = self._load()
        if not (1 <= idx <= len(quotes)):
            return f"[banner] No quote at position {idx}. See /banner list-quotes"
        removed = quotes.pop(idx - 1)
        self._save(quotes)
        return f"[banner] Removed: {removed}"

    @safe
    def cmd_list_quotes(self, arg=""):
        """List all quotes"""
        quotes = self._load()
        if not quotes:
            return "[banner] No quotes yet."
        lines = [f"[banner] {len(quotes)} quote(s):"]
        for i, q in enumerate(quotes, 1):
            lines.append(f"  {i}. {q}")
        return "\n".join(lines)

    @safe
    def cmd_random(self, arg=""):
        """Alias of /banner quote"""
        return self.cmd_quote(arg)

    @safe
    def cmd_wordmark(self, arg=""):
        """Just the ASCII wordmark, no quote"""
        return _WORDMARK

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
