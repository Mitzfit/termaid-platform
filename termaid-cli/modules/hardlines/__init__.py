"""Hardlines Module — Edit the codebase's baseline hardline safety strings. DANGEROUS tier.

Built with real write access, as explicitly requested. This is distinct
from /aiconfig's per-profile hardlines (already freely editable JSON data
any operator can already change): this edits the actual SOURCE CODE
constants that seed those defaults — `brain/__init__.py`'s `_IDENTITY`
string and `aiconfig/__init__.py`'s `_DEFAULT_PROFILE["hardlines"]` list —
the floor every profile starts from before any per-profile customization.

Uses the same discipline as /selfmod (which this reuses for the actual
write): automatic backup before every change, `compile()` syntax
validation before committing, and a confirm gate. Restart the backend to
load a change — modules load once at startup, so nothing here takes
effect retroactively on an already-running process.

Commands (~4):
  /hardlines list                       Current baseline hardline strings
  /hardlines set-identity <text> confirm  Replace brain's base identity string
  /hardlines add <text> confirm             Add an aiconfig default-profile hardline
  /hardlines remove <index> confirm           Remove an aiconfig default-profile hardline by index
  /hardlines explain                              How this module works
"""

import ast
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

_IDENTITY_RE = re.compile(r'(_IDENTITY\s*=\s*)((?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|\((?:[^()]|\n)*\)))',
                          re.M)
_HARDLINES_RE = re.compile(r'("hardlines":\s*)(\[[^\]]*\])', re.S)


class HardlinesModule(Module):
    name = "hardlines"
    version = "1.0.0"
    description = "Edit the codebase's baseline hardline safety strings"
    author = "termaid"

    def on_load(self):
        for cmd in ["list", "set-identity", "add", "remove", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        self._modules_dir = Path(__file__).resolve().parent.parent
        self._brain_file = self._modules_dir / "brain" / "__init__.py"
        self._aiconfig_file = self._modules_dir / "aiconfig" / "__init__.py"

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._backup_dir = data_dir / "hardlines_backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _backup(self, label: str, path: Path) -> Path:
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup_path = self._backup_dir / f"{label}__{ts}.py"
        backup_path.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        return backup_path

    def _current_identity(self):
        if not self._brain_file.is_file():
            return None
        text = self._brain_file.read_text(encoding="utf-8", errors="replace")
        m = _IDENTITY_RE.search(text)
        if not m:
            return None
        try:
            return ast.literal_eval(m.group(2))
        except Exception:
            return m.group(2)

    def _current_aiconfig_hardlines(self):
        if not self._aiconfig_file.is_file():
            return None
        text = self._aiconfig_file.read_text(encoding="utf-8", errors="replace")
        m = _HARDLINES_RE.search(text)
        if not m:
            return None
        try:
            return ast.literal_eval(m.group(2))
        except Exception:
            return None

    @safe
    def cmd_list(self, arg=""):
        """Current baseline hardline strings"""
        lines = ["[hardlines] Baseline strings:"]
        identity = self._current_identity()
        lines.append(f"  brain._IDENTITY: {identity!r}" if identity is not None
                     else "  brain._IDENTITY: (not found — brain/__init__.py may have changed shape)")
        hardlines = self._current_aiconfig_hardlines()
        if hardlines is not None:
            lines.append(f"  aiconfig default-profile hardlines ({len(hardlines)}):")
            for i, h in enumerate(hardlines, 1):
                lines.append(f"    {i}. {h}")
        else:
            lines.append("  aiconfig default-profile hardlines: (not found)")
        return "\n".join(lines)

    @safe
    def cmd_set_identity(self, arg=""):
        """Replace brain's base identity string (confirms): /hardlines set-identity <text> confirm"""
        text = (arg or "").rstrip()
        if not text.lower().endswith("confirm"):
            return "[hardlines] This changes the floor every persona/profile builds on. Re-run as: /hardlines set-identity <text> confirm"
        new_identity = text[:-len("confirm")].rstrip()
        if not new_identity:
            return "[hardlines] Usage: /hardlines set-identity <text> confirm"
        if not self._brain_file.is_file():
            return "[hardlines] brain/__init__.py not found."
        source = self._brain_file.read_text(encoding="utf-8", errors="replace")
        replacement = f'_IDENTITY = {new_identity!r}'
        new_source, n = _IDENTITY_RE.subn(lambda m: replacement, source, count=1)
        if n == 0:
            return "[hardlines] Could not find _IDENTITY in brain/__init__.py — its shape may have changed."
        try:
            compile(new_source, str(self._brain_file), "exec")
        except SyntaxError as e:
            return f"[hardlines] Refusing to write — result has a syntax error: {e}"
        self._backup("brain_identity", self._brain_file)
        self._brain_file.write_text(new_source, encoding="utf-8")
        return "[hardlines] brain._IDENTITY updated. Restart the backend to load it."

    @safe
    def cmd_add(self, arg=""):
        """Add an aiconfig default-profile hardline (confirms): /hardlines add <text> confirm"""
        text = (arg or "").rstrip()
        if not text.lower().endswith("confirm"):
            return "[hardlines] Re-run as: /hardlines add <text> confirm"
        new_line = text[:-len("confirm")].rstrip()
        if not new_line:
            return "[hardlines] Usage: /hardlines add <text> confirm"
        hardlines = self._current_aiconfig_hardlines()
        if hardlines is None:
            return "[hardlines] Could not read aiconfig's default-profile hardlines list."
        hardlines.append(new_line)
        return self._write_aiconfig_hardlines(hardlines)

    @safe
    def cmd_remove(self, arg=""):
        """Remove an aiconfig default-profile hardline by index (confirms): /hardlines remove <index> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm" or not parts[0].isdigit():
            return "[hardlines] Usage: /hardlines remove <index> confirm (see /hardlines list for indices)"
        idx = int(parts[0]) - 1
        hardlines = self._current_aiconfig_hardlines()
        if hardlines is None:
            return "[hardlines] Could not read aiconfig's default-profile hardlines list."
        if idx < 0 or idx >= len(hardlines):
            return f"[hardlines] No hardline #{parts[0]}"
        removed = hardlines.pop(idx)
        result = self._write_aiconfig_hardlines(hardlines)
        return f"{result}\n  Removed: {removed}"

    def _write_aiconfig_hardlines(self, hardlines: list) -> str:
        source = self._aiconfig_file.read_text(encoding="utf-8", errors="replace")
        replacement_list = "[" + ", ".join(repr(h) for h in hardlines) + "]"
        new_source, n = _HARDLINES_RE.subn(lambda m: m.group(1) + replacement_list, source, count=1)
        if n == 0:
            return "[hardlines] Could not find the hardlines list in aiconfig/__init__.py."
        try:
            compile(new_source, str(self._aiconfig_file), "exec")
        except SyntaxError as e:
            return f"[hardlines] Refusing to write — result has a syntax error: {e}"
        self._backup("aiconfig_hardlines", self._aiconfig_file)
        self._aiconfig_file.write_text(new_source, encoding="utf-8")
        return f"[hardlines] aiconfig default-profile hardlines updated ({len(hardlines)} total). Restart the backend to load it."

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
