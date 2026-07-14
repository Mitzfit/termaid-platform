"""Router Module — Command-string parse diagnostic.

Mirrors the engine's exact parsing rule (`backend/engine.py:execute`):
strip a leading '/', split on the first whitespace into cmd/arg, lower-
case cmd. A module has no handle back into the live command registry
(same limitation /chain documents), so this can't say whether a parsed
command actually exists — it shows you how the *text* would be split,
and separately whether it matches a saved /aliases shortcut, which is
plain data this module can read directly.

Commands (~2):
  /router parse <input>       Show how the raw input would be tokenized
  /router explain                 How this module works
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


class RouterModule(Module):
    name = "router"
    version = "1.0.0"
    description = "Command-string parse diagnostic"
    author = "termaid"

    def on_load(self):
        for cmd in ["parse", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._aliases_file = data_dir / "aliases" / "aliases.json"

    def _aliases(self) -> dict:
        if self._aliases_file.exists():
            try:
                return json.loads(self._aliases_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    @safe
    def cmd_parse(self, arg=""):
        """Show how the raw input would be tokenized: /router parse <input>"""
        raw = arg or ""
        if not raw.strip():
            return "[router] Usage: /router parse <input>"
        line = raw.strip().lstrip("/")
        if not line:
            return "[router] Parsed as: empty command (engine returns 'empty command')"
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        cmd_arg = parts[1] if len(parts) > 1 else ""

        lines = [f"[router] Input:  {raw!r}",
                f"  After stripping leading '/': {line!r}",
                f"  cmd:  {cmd!r}",
                f"  arg:  {cmd_arg!r}"]

        if "." in cmd:
            mod, sub = cmd.split(".", 1)
            lines.append(f"  Would route to module '{mod}', command '{sub}' (if registered)")
        else:
            lines.append(f"  No '.' in cmd — only matches if '{cmd}' is a native/top-level alias")

        aliases = self._aliases()
        if cmd in aliases:
            lines.append(f"  Matches an /aliases shortcut -> {aliases[cmd]}")

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
