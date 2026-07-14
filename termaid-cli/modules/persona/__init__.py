"""Persona Module — AI identity and communication style.

Manages named "persona" configs (a short identity blurb + tone + verbosity)
and compiles them into a system-prompt string other AI-backed modules can
pass to self.ask_ai(prompt, system=persona.compile()). This module does not
automatically wire itself into every AI call — pass its compiled prompt
explicitly, or read it from cmd_prompt() and forward it yourself.

Commands (~10):
  /persona create <name> <description>   Define a persona
  /persona set <name>                     Activate a persona
  /persona show [name]                    Show a persona (default: active)
  /persona list                           List all personas
  /persona delete <name>                  Delete a persona
  /persona tone <tone>                     Set the active persona's tone
  /persona verbosity <concise|normal|detailed>   Set active verbosity
  /persona prompt                          Render the active persona as a system prompt
  /persona default                         Reset to the built-in default persona
  /persona explain                         How this module works
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


_DEFAULT_PERSONA = {
    "name": "default",
    "description": "You are TermAId, a terminal-native assistant. Be correct, "
                    "direct, and useful; don't pad answers with filler.",
    "tone": "neutral",
    "verbosity": "concise",
}

_VALID_VERBOSITY = {"concise", "normal", "detailed"}


class PersonaModule(Module):
    name = "persona"
    version = "1.0.0"
    description = "AI identity and communication style"
    author = "termaid"

    def on_load(self):
        for cmd in ["create", "set", "show", "list", "delete",
                    "tone", "verbosity", "prompt", "default", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "persona"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "personas.json"
        if not self._file.exists():
            self._save_all({"default": _DEFAULT_PERSONA}, active="default")

    def _load(self) -> tuple[dict, str]:
        try:
            data = json.loads(self._file.read_text())
            return data.get("personas", {"default": _DEFAULT_PERSONA}), data.get("active", "default")
        except Exception:
            return {"default": _DEFAULT_PERSONA}, "default"

    def _save_all(self, personas: dict, active: str) -> None:
        self._file.write_text(json.dumps({"personas": personas, "active": active}, indent=2))

    def _compile(self, persona: dict) -> str:
        verbosity_line = {
            "concise": "Answer in as few words as carry the meaning.",
            "normal": "Answer at a normal, conversational length.",
            "detailed": "Explain thoroughly, including relevant context.",
        }.get(persona.get("verbosity", "concise"), "")
        tone = persona.get("tone", "neutral")
        return (f"{persona.get('description', '')}\n"
                f"Tone: {tone}. {verbosity_line}")

    @safe
    def cmd_create(self, arg=""):
        """Define a persona: /persona create <name> <description>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[persona] Usage: /persona create <name> <description>"
        name, description = parts
        personas, active = self._load()
        personas[name] = {"name": name, "description": description,
                          "tone": "neutral", "verbosity": "concise"}
        self._save_all(personas, active)
        return f"[persona] Created '{name}'. Activate with /persona set {name}"

    @safe
    def cmd_set(self, arg=""):
        """Activate a persona"""
        name = (arg or "").strip()
        if not name:
            return "[persona] Usage: /persona set <name>"
        personas, active = self._load()
        if name not in personas:
            return f"[persona] No persona named '{name}'. See /persona list"
        self._save_all(personas, name)
        return f"[persona] Active persona: {name}"

    @safe
    def cmd_show(self, arg=""):
        """Show a persona (default: active)"""
        personas, active = self._load()
        name = (arg or "").strip() or active
        if name not in personas:
            return f"[persona] No persona named '{name}'"
        p = personas[name]
        lines = [f"[persona] {name}{' (active)' if name == active else ''}:"]
        lines.append(f"  description: {p.get('description', '')}")
        lines.append(f"  tone:        {p.get('tone', 'neutral')}")
        lines.append(f"  verbosity:   {p.get('verbosity', 'concise')}")
        return "\n".join(lines)

    @safe
    def cmd_list(self, arg=""):
        """List all personas"""
        personas, active = self._load()
        lines = [f"[persona] {len(personas)} persona(s):"]
        for name in sorted(personas):
            marker = " (active)" if name == active else ""
            lines.append(f"  {name}{marker}")
        return "\n".join(lines)

    @safe
    def cmd_delete(self, arg=""):
        """Delete a persona"""
        name = (arg or "").strip()
        if not name:
            return "[persona] Usage: /persona delete <name>"
        if name == "default":
            return "[persona] Cannot delete the built-in 'default' persona"
        personas, active = self._load()
        if name not in personas:
            return f"[persona] No persona named '{name}'"
        del personas[name]
        if active == name:
            active = "default"
        self._save_all(personas, active)
        return f"[persona] Deleted '{name}'"

    @safe
    def cmd_tone(self, arg=""):
        """Set the active persona's tone"""
        tone = (arg or "").strip()
        if not tone:
            return "[persona] Usage: /persona tone <tone-description>"
        personas, active = self._load()
        personas[active]["tone"] = tone
        self._save_all(personas, active)
        return f"[persona] '{active}' tone set to: {tone}"

    @safe
    def cmd_verbosity(self, arg=""):
        """Set active verbosity: concise|normal|detailed"""
        v = (arg or "").strip().lower()
        if v not in _VALID_VERBOSITY:
            return f"[persona] Usage: /persona verbosity <{'|'.join(_VALID_VERBOSITY)}>"
        personas, active = self._load()
        personas[active]["verbosity"] = v
        self._save_all(personas, active)
        return f"[persona] '{active}' verbosity set to: {v}"

    @safe
    def cmd_prompt(self, arg=""):
        """Render the active persona as a system prompt"""
        personas, active = self._load()
        return f"[persona] Compiled system prompt for '{active}':\n\n{self._compile(personas[active])}"

    @safe
    def cmd_default(self, arg=""):
        """Reset to the built-in default persona"""
        personas, _ = self._load()
        personas["default"] = _DEFAULT_PERSONA
        self._save_all(personas, "default")
        return "[persona] Active persona reset to 'default'"

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
