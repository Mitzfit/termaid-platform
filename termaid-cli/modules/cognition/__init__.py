"""Cognition Module — Configure how the AI reasons: depth, planning, self-check, verbosity.

Where /persona is WHO the AI is and /brain composes WHAT it knows, /cognition
is HOW it thinks: does it plan before answering, does it double-check itself,
how thorough should it be. Compiles to a short directive block another module
can prepend to its own system prompt (see /cognition compile), or pass
straight to self.ask_ai as the system= argument.

Every field change is logged to a persisted history so you can see what was
tuned and when. Beyond the 3 built-in presets (fast/careful/creative) you can
save your own combinations as named custom presets.

Note: this module doesn't expose a "temperature" knob — self.ask_ai(prompt,
system=) only accepts a system prompt, there's no temperature/model override
plumbed through to the AI provider, and a knob that silently did nothing
would be worse than no knob at all.

Commands (~18):
  /cognition depth <shallow|normal|deep>       How much analysis before answering
  /cognition planning <on|off>                  Require an explicit plan first
  /cognition self-check <on|off>                Require a self-review step
  /cognition verbosity <concise|normal|detailed>  Response length target
  /cognition creativity <low|medium|high>       How much to favor novel vs. safe answers
  /cognition show                                Current reasoning config
  /cognition compile                             Render config as a directive block
  /cognition preset <name>                       Apply a built-in or custom preset
  /cognition presets                              List built-in AND custom presets
  /cognition save-preset <name>                    Save the current config as a custom preset
  /cognition delete-preset <name>                    Delete a custom preset
  /cognition compare <preset1> <preset2>               Diff two presets field by field
  /cognition history [n]                                 Recent config changes (default 20)
  /cognition ask <message>                                 Ask the AI using this config as system prompt
  /cognition reset                                           Reset to defaults
  /cognition explain                                          How this module works
"""

import json
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_DEFAULTS = {
    "depth": "normal", "planning": False, "self_check": False,
    "verbosity": "normal", "creativity": "medium",
}

_BUILTIN_PRESETS = {
    "fast": {"depth": "shallow", "planning": False, "self_check": False,
             "verbosity": "concise", "creativity": "low"},
    "careful": {"depth": "deep", "planning": True, "self_check": True,
                "verbosity": "detailed", "creativity": "low"},
    "creative": {"depth": "normal", "planning": False, "self_check": False,
                 "verbosity": "normal", "creativity": "high"},
}

_VALID = {
    "depth": {"shallow", "normal", "deep"},
    "verbosity": {"concise", "normal", "detailed"},
    "creativity": {"low", "medium", "high"},
}


class CognitionModule(Module):
    name = "cognition"
    version = "1.1.0"
    description = "Configure how the AI reasons: depth, planning, self-check, verbosity"
    author = "termaid"

    def on_load(self):
        cmds = ["depth", "planning", "self-check", "verbosity", "creativity",
                "show", "compile", "preset", "presets", "save-preset", "delete-preset",
                "compare", "history", "ask", "reset", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "cognition"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "config.json"
        self._custom_presets_file = self._dir / "custom_presets.json"
        self._history_file = self._dir / "history.jsonl"
        if not self._file.exists():
            self._save(dict(_DEFAULTS))

    # ------------------------------------------------------------------ #
    def _load(self) -> dict:
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except Exception:
            return dict(_DEFAULTS)

    def _save(self, cfg: dict) -> None:
        self._file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def _load_custom_presets(self) -> dict:
        if self._custom_presets_file.exists():
            try:
                return json.loads(self._custom_presets_file.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_custom_presets(self, presets: dict) -> None:
        self._custom_presets_file.write_text(json.dumps(presets, indent=2), encoding="utf-8")

    def _all_presets(self) -> dict:
        merged = dict(_BUILTIN_PRESETS)
        merged.update(self._load_custom_presets())
        return merged

    def _log_change(self, field: str, value) -> None:
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "field": field, "value": value}
        with self._history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _set_field(self, field: str, value: str, valid: set | None = None):
        if valid and value not in valid:
            return f"[cognition] Must be one of: {', '.join(sorted(valid))}"
        cfg = self._load()
        cfg[field] = value
        self._save(cfg)
        self._log_change(field, value)
        return f"[cognition] {field} = {value}"

    # ------------------------------------------------------------------ #
    @safe
    def cmd_depth(self, arg=""):
        """How much analysis before answering: shallow|normal|deep"""
        v = (arg or "").strip().lower()
        if not v:
            return f"[cognition] depth = {self._load().get('depth')}"
        return self._set_field("depth", v, _VALID["depth"])

    @safe
    def cmd_planning(self, arg=""):
        """Require an explicit plan first: on|off"""
        v = (arg or "").strip().lower()
        if v not in ("on", "off"):
            return "[cognition] Usage: /cognition planning <on|off>"
        cfg = self._load()
        cfg["planning"] = (v == "on")
        self._save(cfg)
        self._log_change("planning", v == "on")
        return f"[cognition] planning = {v}"

    @safe
    def cmd_self_check(self, arg=""):
        """Require a self-review step: on|off"""
        v = (arg or "").strip().lower()
        if v not in ("on", "off"):
            return "[cognition] Usage: /cognition self-check <on|off>"
        cfg = self._load()
        cfg["self_check"] = (v == "on")
        self._save(cfg)
        self._log_change("self_check", v == "on")
        return f"[cognition] self-check = {v}"

    @safe
    def cmd_verbosity(self, arg=""):
        """Response length target: concise|normal|detailed"""
        v = (arg or "").strip().lower()
        if not v:
            return f"[cognition] verbosity = {self._load().get('verbosity')}"
        return self._set_field("verbosity", v, _VALID["verbosity"])

    @safe
    def cmd_creativity(self, arg=""):
        """How much to favor novel vs. safe answers: low|medium|high"""
        v = (arg or "").strip().lower()
        if not v:
            return f"[cognition] creativity = {self._load().get('creativity')}"
        return self._set_field("creativity", v, _VALID["creativity"])

    @safe
    def cmd_show(self, arg=""):
        """Current reasoning config"""
        cfg = self._load()
        lines = ["[cognition] Current config:"]
        for k, v in cfg.items():
            lines.append(f"  {k:<12s} {v}")
        return "\n".join(lines)

    def _compile_from(self, cfg: dict) -> str:
        directives = [f"Reasoning depth: {cfg.get('depth', 'normal')}."]
        if cfg.get("planning"):
            directives.append("Sketch a brief plan before answering.")
        if cfg.get("self_check"):
            directives.append("Review your answer for errors before finalizing it.")
        directives.append(f"Response length: {cfg.get('verbosity', 'normal')}.")
        directives.append(f"Creativity: {cfg.get('creativity', 'medium')} "
                          "(low = stick to well-established answers; high = consider novel approaches).")
        return "\n".join(directives)

    @safe
    def cmd_compile(self, arg=""):
        """Render config as a directive block"""
        return self._compile_from(self._load())

    @safe
    def cmd_preset(self, arg=""):
        """Apply a built-in or custom preset: /cognition preset <name>"""
        name = (arg or "").strip().lower()
        presets = self._all_presets()
        if name not in presets:
            return f"[cognition] Unknown preset '{name}'. See /cognition presets"
        self._save(dict(presets[name]))
        self._log_change("preset", name)
        return f"[cognition] Applied preset '{name}'"

    @safe
    def cmd_presets(self, arg=""):
        """List built-in AND custom presets"""
        custom = self._load_custom_presets()
        lines = [f"[cognition] Built-in: {', '.join(_BUILTIN_PRESETS.keys())}"]
        if custom:
            lines.append(f"[cognition] Custom:   {', '.join(sorted(custom.keys()))}")
        else:
            lines.append("[cognition] Custom:   (none — /cognition save-preset <name>)")
        return "\n".join(lines)

    @safe
    def cmd_save_preset(self, arg=""):
        """Save the current config as a custom preset: /cognition save-preset <name>"""
        name = (arg or "").strip().lower()
        if not name:
            return "[cognition] Usage: /cognition save-preset <name>"
        if name in _BUILTIN_PRESETS:
            return f"[cognition] '{name}' is a built-in preset name — choose another."
        presets = self._load_custom_presets()
        presets[name] = self._load()
        self._save_custom_presets(presets)
        return f"[cognition] Saved current config as custom preset '{name}'"

    @safe
    def cmd_delete_preset(self, arg=""):
        """Delete a custom preset: /cognition delete-preset <name>"""
        name = (arg or "").strip().lower()
        presets = self._load_custom_presets()
        if name not in presets:
            return f"[cognition] No custom preset named '{name}' (built-in presets can't be deleted)"
        del presets[name]
        self._save_custom_presets(presets)
        return f"[cognition] Deleted custom preset '{name}'"

    @safe
    def cmd_compare(self, arg=""):
        """Diff two presets field by field: /cognition compare <preset1> <preset2>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[cognition] Usage: /cognition compare <preset1> <preset2>"
        presets = self._all_presets()
        a, b = parts
        if a not in presets or b not in presets:
            missing = a if a not in presets else b
            return f"[cognition] Unknown preset '{missing}'. See /cognition presets"
        cfg_a, cfg_b = presets[a], presets[b]
        fields = sorted(set(cfg_a) | set(cfg_b))
        lines = [f"[cognition] {a} vs {b}:"]
        for f in fields:
            va, vb = cfg_a.get(f, "?"), cfg_b.get(f, "?")
            marker = " " if va == vb else "!"
            lines.append(f"  {marker} {f:<12s} {va!s:<10s} vs {vb!s}")
        return "\n".join(lines)

    @safe
    def cmd_history(self, arg=""):
        """Recent config changes (default 20): /cognition history [n]"""
        s = (arg or "").strip()
        try:
            limit = int(s) if s else 20
        except ValueError:
            limit = 20
        if not self._history_file.exists():
            return "[cognition] No changes recorded yet."
        lines_raw = self._history_file.read_text(encoding="utf-8").splitlines()[-limit:]
        entries = []
        for l in lines_raw:
            if l.strip():
                try:
                    entries.append(json.loads(l))
                except Exception:
                    continue
        if not entries:
            return "[cognition] No changes recorded yet."
        lines = [f"[cognition] Last {len(entries)} change(s):"]
        for e in entries:
            lines.append(f"  [{e.get('at', '?')}] {e.get('field', '?')} = {e.get('value', '?')}")
        return "\n".join(lines)

    @safe
    def cmd_ask(self, arg=""):
        """Ask the AI using this config as system prompt"""
        message = arg or ""
        if not message:
            return "[cognition] Usage: /cognition ask <message>"
        if not self.ai:
            return "[cognition] No AI provider configured."
        try:
            return self.ask_ai(message, system=self._compile_from(self._load()))
        except Exception as e:
            return f"[cognition] AI error: {e}"

    @safe
    def cmd_reset(self, arg=""):
        """Reset to defaults"""
        self._save(dict(_DEFAULTS))
        self._log_change("reset", "defaults")
        return "[cognition] Reset to defaults"

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
