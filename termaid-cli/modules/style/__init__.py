"""Style Module — Customize TermAId colors, themes, prompt, banner style.

Stores a color/theme config as JSON (a palette of named roles: background,
foreground, accent, success, error, muted, etc). This backend doesn't render
a terminal itself, so /style doesn't repaint anything directly — it's a
config store a UI (or another module, like /memory's `_theme()` helper) can
read to pick colors consistently.

Commands (~12):
  /style set <role> <hex>       Set one color role, e.g. /style set accent #39D353
  /style get [role]              Show one role or the whole active theme
  /style presets                 List built-in presets
  /style preset <name>           Activate a built-in preset
  /style reset                   Reset to the default preset
  /style prompt <text>           Set the prompt string (supports {user}, {cwd})
  /style export                  Export the active theme to JSON
  /style import <path>           Import a theme from JSON
  /style list-themes             List saved custom themes
  /style save <name>             Save the active theme under a name
  /style load <name>              Load a saved custom theme
  /style explain                  How this module works
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


_PRESETS = {
    "dark": {
        "background": "#0B0E14", "foreground": "#C9D1D9", "accent": "#39D353",
        "accent2": "#58A6FF", "success": "#00FF87", "error": "#F85149", "muted": "#6B7280",
    },
    "light": {
        "background": "#FFFFFF", "foreground": "#1F2328", "accent": "#0969DA",
        "accent2": "#8250DF", "success": "#1A7F37", "error": "#D1242F", "muted": "#6E7781",
    },
    "solarized": {
        "background": "#002B36", "foreground": "#839496", "accent": "#268BD2",
        "accent2": "#2AA198", "success": "#859900", "error": "#DC322F", "muted": "#586E75",
    },
}

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class StyleModule(Module):
    name = "style"
    version = "1.0.0"
    description = "Customize TermAId colors, themes, prompt, banner style"
    author = "termaid"

    def on_load(self):
        for cmd in ["set", "get", "presets", "preset", "reset", "prompt",
                    "export", "import", "list-themes", "save", "load", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "style"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._active_file = self._dir / "active.json"
        self._themes_file = self._dir / "themes.json"
        if not self._active_file.exists():
            self._write_active({**_PRESETS["dark"], "prompt": "{user}@termaid:{cwd}$ "})

    def _read_active(self) -> dict:
        try:
            return json.loads(self._active_file.read_text())
        except Exception:
            return {**_PRESETS["dark"], "prompt": "{user}@termaid:{cwd}$ "}

    def _write_active(self, data: dict) -> None:
        self._active_file.write_text(json.dumps(data, indent=2))

    def _read_themes(self) -> dict:
        if self._themes_file.exists():
            try:
                return json.loads(self._themes_file.read_text())
            except Exception:
                pass
        return {}

    @safe
    def cmd_set(self, arg=""):
        """Set one color role: /style set <role> <#hex>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[style] Usage: /style set <role> <#rrggbb>"
        role, hexval = parts
        if not _HEX_RE.match(hexval):
            return "[style] Color must be a 6-digit hex value, e.g. #39D353"
        active = self._read_active()
        active[role] = hexval
        self._write_active(active)
        return f"[style] Set {role} = {hexval}"

    @safe
    def cmd_get(self, arg=""):
        """Show one role or the whole active theme"""
        active = self._read_active()
        role = (arg or "").strip()
        if role:
            if role not in active:
                return f"[style] No role named '{role}'"
            return f"[style] {role} = {active[role]}"
        lines = ["[style] Active theme:"]
        for k, v in active.items():
            lines.append(f"  {k:<12s} {v}")
        return "\n".join(lines)

    @safe
    def cmd_presets(self, arg=""):
        """List built-in presets"""
        return "[style] Built-in presets: " + ", ".join(_PRESETS.keys())

    @safe
    def cmd_preset(self, arg=""):
        """Activate a built-in preset"""
        name = (arg or "").strip().lower()
        if name not in _PRESETS:
            return f"[style] Unknown preset '{name}'. Available: {', '.join(_PRESETS)}"
        active = self._read_active()
        prompt = active.get("prompt", "{user}@termaid:{cwd}$ ")
        self._write_active({**_PRESETS[name], "prompt": prompt})
        return f"[style] Activated preset '{name}'"

    @safe
    def cmd_reset(self, arg=""):
        """Reset to the default preset"""
        self._write_active({**_PRESETS["dark"], "prompt": "{user}@termaid:{cwd}$ "})
        return "[style] Reset to default (dark) theme"

    @safe
    def cmd_prompt(self, arg=""):
        """Set the prompt string (supports {user}, {cwd})"""
        text = arg or ""
        if not text:
            active = self._read_active()
            return f"[style] Current prompt: {active.get('prompt', '(none)')!r}"
        active = self._read_active()
        active["prompt"] = text
        self._write_active(active)
        return f"[style] Prompt set to {text!r}"

    @safe
    def cmd_export(self, arg=""):
        """Export the active theme to JSON"""
        path = (arg or "").strip() or str(self._dir / "theme-export.json")
        Path(path).expanduser().write_text(json.dumps(self._read_active(), indent=2))
        return f"[style] Exported to {path}"

    @safe
    def cmd_import(self, arg=""):
        """Import a theme from JSON"""
        path = (arg or "").strip()
        if not path:
            return "[style] Usage: /style import <path>"
        try:
            data = json.loads(Path(path).expanduser().read_text())
        except Exception as e:
            return f"[style] Cannot read: {e}"
        self._write_active(data)
        return f"[style] Imported theme from {path}"

    @safe
    def cmd_list_themes(self, arg=""):
        """List saved custom themes"""
        themes = self._read_themes()
        if not themes:
            return "[style] No saved custom themes. /style save <name>"
        return "[style] Saved themes: " + ", ".join(sorted(themes.keys()))

    @safe
    def cmd_save(self, arg=""):
        """Save the active theme under a name"""
        name = (arg or "").strip()
        if not name:
            return "[style] Usage: /style save <name>"
        themes = self._read_themes()
        themes[name] = self._read_active()
        self._themes_file.write_text(json.dumps(themes, indent=2))
        return f"[style] Saved active theme as '{name}'"

    @safe
    def cmd_load(self, arg=""):
        """Load a saved custom theme"""
        name = (arg or "").strip()
        if not name:
            return "[style] Usage: /style load <name>"
        themes = self._read_themes()
        if name not in themes:
            return f"[style] No saved theme named '{name}'"
        self._write_active(themes[name])
        return f"[style] Loaded theme '{name}'"

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
