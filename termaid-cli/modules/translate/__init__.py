"""Translate Module — Translation via configured AI (no separate API key).

Uses whatever AI provider the engine is configured with (self.ask_ai), so
there's no separate translation-API key to manage. Requires an AI provider to
be configured; without one, commands say so clearly instead of failing oddly.

Commands (~7):
  /translate to <lang> <text>     Translate text into <lang>
  /translate from <lang> <text>   Translate FROM <lang> into your default
  /translate detect <text>        Guess the source language
  /translate default <lang>       Set your default target language
  /translate languages            List a few common language names/codes
  /translate history               Recent translations (this session)
  /translate explain               How this module works
"""

import os
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_COMMON_LANGUAGES = [
    "English", "Spanish", "French", "German", "Italian", "Portuguese",
    "Dutch", "Russian", "Japanese", "Korean", "Mandarin Chinese", "Arabic",
    "Hindi", "Turkish", "Polish", "Vietnamese", "Swedish", "Greek",
]


class TranslateModule(Module):
    name = "translate"
    version = "1.0.0"
    description = "Translation via configured AI (no separate API key)"
    author = "termaid"

    def on_load(self):
        for cmd in ["to", "from", "detect", "default", "languages", "history", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "translate"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._dir / "config.json"
        self._default_lang = self._load_default()
        self._history: list[str] = []

    def _load_default(self) -> str:
        import json
        if self._config_file.exists():
            try:
                return json.loads(self._config_file.read_text()).get("default_lang", "English")
            except Exception:
                pass
        return "English"

    def _save_default(self, lang: str) -> None:
        import json
        self._config_file.write_text(json.dumps({"default_lang": lang}, indent=2))

    def _require_ai(self):
        if not self.ai:
            return ("[translate] No AI provider configured.\n"
                    "  Set AI_PROVIDER (and its API key) in .env, then restart.")
        return None

    @safe
    def cmd_to(self, arg=""):
        """Translate text into <lang>: /translate to <lang> <text>"""
        err = self._require_ai()
        if err:
            return err
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[translate] Usage: /translate to <language> <text>"
        lang, text = parts
        try:
            result = self.ask_ai(
                text,
                system=(f"Translate the user's message into {lang}. "
                        "Reply with ONLY the translation, nothing else."),
            )
        except Exception as e:
            return f"[translate] AI error: {e}"
        self._history.append(f"-> {lang}: {text[:60]} => {result[:60]}")
        return f"[translate] {result}"

    @safe
    def cmd_from(self, arg=""):
        """Translate FROM <lang> into your default: /translate from <lang> <text>"""
        err = self._require_ai()
        if err:
            return err
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[translate] Usage: /translate from <language> <text>"
        lang, text = parts
        try:
            result = self.ask_ai(
                text,
                system=(f"The following text is in {lang}. Translate it into "
                        f"{self._default_lang}. Reply with ONLY the translation."),
            )
        except Exception as e:
            return f"[translate] AI error: {e}"
        self._history.append(f"{lang} ->: {text[:60]} => {result[:60]}")
        return f"[translate] {result}"

    @safe
    def cmd_detect(self, arg=""):
        """Guess the source language: /translate detect <text>"""
        err = self._require_ai()
        if err:
            return err
        text = arg or ""
        if not text:
            return "[translate] Usage: /translate detect <text>"
        try:
            result = self.ask_ai(
                text,
                system="Identify the language of this text. Reply with ONLY the language name.",
            )
        except Exception as e:
            return f"[translate] AI error: {e}"
        return f"[translate] Detected language: {result.strip()}"

    @safe
    def cmd_default(self, arg=""):
        """Set your default target language: /translate default <lang>"""
        lang = (arg or "").strip()
        if not lang:
            return f"[translate] Current default: {self._default_lang}"
        self._default_lang = lang
        self._save_default(lang)
        return f"[translate] Default target language set to '{lang}'"

    @safe
    def cmd_languages(self, arg=""):
        """List a few common language names"""
        return "[translate] Common languages:\n" + "\n".join(f"  - {l}" for l in _COMMON_LANGUAGES)

    @safe
    def cmd_history(self, arg=""):
        """Recent translations (this session only)"""
        if not self._history:
            return "[translate] No translations this session."
        lines = [f"[translate] {len(self._history)} this session:"]
        for h in self._history[-20:]:
            lines.append(f"  {h}")
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
