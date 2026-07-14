"""Brain Module — Layered system prompt orchestrator: where TermAId thinks.

Composes a system prompt from independent layers before handing a message to
the AI provider:
  identity  — a fixed base description of TermAId
  persona   — read from the /persona module's on-disk config (if present)
  rules     — read from the /rules module's on-disk config (if present)
  memory    — the N most recent enabled facts from /memory
  lessons   — the N most recent enabled patterns from /lessons
  catalog   — names of every installed module (lightweight capability awareness)
  context   — notes from the most recent completed /session
  custom    — ad-hoc text snippets you add yourself, for one-off context

Modules don't hold a reference to each other or to the engine, so this reads
the SAME on-disk JSON those other modules already write, rather than
depending on them being loaded in the same process. Any layer's source data
can be absent — brain degrades to fewer layers, never errors. A character
budget keeps the compiled prompt from growing unbounded: when over budget,
the oldest memory/lesson entries are trimmed first, not silently truncated
mid-sentence.

Commands (~18):
  /brain think <message>       Full pipeline: compile layers, ask the AI, return the answer
  /brain prompt                  Show the compiled system prompt without calling the AI
  /brain prompt-for <layer>        Preview one layer's rendered content in isolation
  /brain layers                     Show which layers are currently enabled
  /brain enable <layer>               Enable a layer
  /brain disable <layer>                Disable a layer
  /brain depth <n>                       How many memory/lesson entries to include (default 10)
  /brain budget <chars>                    Max compiled-prompt size before trimming (default 8000)
  /brain add-custom <text>                   Add an ad-hoc custom layer entry
  /brain remove-custom <index>                 Remove a custom layer entry by index
  /brain list-custom                             List custom layer entries
  /brain status                                    Persona/profile, memory/lesson counts, AI availability
  /brain history [n]                                 Recent /brain think exchanges (persisted, default 20)
  /brain history-clear confirm                         Clear persisted think history
  /brain export <path>                                   Write the compiled prompt to a file
  /brain reset                                             Reset layer toggles, depth, budget to defaults
  /brain explain                                             How this module works
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


_IDENTITY = ("You are TermAId, a terminal-native AI assistant. Be correct before "
             "you are brief; never invent commands, flags, or facts.")

_ALL_LAYERS = ("persona", "rules", "memory", "lessons", "catalog", "context", "custom")
_DEFAULT_BUDGET = 8000
_DEFAULT_DEPTH = 10


def _termaid_data_dir() -> Path:
    home = Path.home()
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
    return home / ".termaid"


class BrainModule(Module):
    name = "brain"
    version = "1.1.0"
    description = "Layered system prompt orchestrator — the AI's brain"
    author = "termaid"

    def on_load(self):
        for cmd in ["think", "prompt", "prompt-for", "layers", "enable", "disable",
                    "depth", "budget", "add-custom", "remove-custom", "list-custom",
                    "status", "history", "history-clear", "export", "reset", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        self._data_dir = _termaid_data_dir()
        self._dir = self._data_dir / "brain"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._dir / "config.json"
        self._history_file = self._dir / "history.jsonl"
        self._custom_file = self._dir / "custom_layers.json"
        if not self._config_file.exists():
            self._save_config({"enabled": list(_ALL_LAYERS[:5]), "depth": _DEFAULT_DEPTH,
                                "budget": _DEFAULT_BUDGET})

    # ------------------------------------------------------------------ #
    # persistence helpers
    def _load_config(self) -> dict:
        try:
            cfg = json.loads(self._config_file.read_text(encoding="utf-8"))
        except Exception:
            cfg = {}
        cfg.setdefault("enabled", list(_ALL_LAYERS[:5]))
        cfg.setdefault("depth", _DEFAULT_DEPTH)
        cfg.setdefault("budget", _DEFAULT_BUDGET)
        return cfg

    def _save_config(self, cfg: dict) -> None:
        self._config_file.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

    def _read_json(self, *parts: str, default=None):
        p = self._data_dir.joinpath(*parts)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
        return default

    def _load_custom(self) -> list:
        if self._custom_file.exists():
            try:
                return json.loads(self._custom_file.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_custom(self, items: list) -> None:
        self._custom_file.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _append_history(self, question: str, answer: str) -> None:
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "q": question[:200], "a": answer[:400]}
        with self._history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _read_history(self, limit: int) -> list:
        if not self._history_file.exists():
            return []
        try:
            lines = self._history_file.read_text(encoding="utf-8").splitlines()
        except Exception:
            return []
        out = []
        for line in lines[-limit:]:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
        return out

    # ------------------------------------------------------------------ #
    # layers
    def _persona_layer(self) -> str:
        data = self._read_json("persona", "personas.json", default=None)
        if not data:
            return ""
        active = data.get("active", "default")
        p = data.get("personas", {}).get(active)
        if not p:
            return ""
        return f"PERSONA: {p.get('description', '')} (tone: {p.get('tone', 'neutral')})"

    def _rules_layer(self) -> str:
        data = self._read_json("rules", "rules.json", default=None)
        if not data:
            return ""
        lines = []
        for r in data.get("instructions", []):
            if r.get("enabled", True):
                lines.append(f"- {r.get('text', '')}")
        for r in data.get("restrictions", []):
            if r.get("enabled", True):
                lines.append(f"- MUST NOT: {r.get('text', '')}")
        return "RULES:\n" + "\n".join(lines) if lines else ""

    def _memory_layer(self, depth: int) -> list:
        """Returns individual fact lines (newest last) so the budget trimmer can drop from the front."""
        data = self._read_json("memory", "memories.json", default=None)
        if not data:
            return []
        facts = [f["text"] for f in data.get("facts", []) if f.get("enabled", True)]
        return facts[-depth:] if depth else []

    def _lessons_layer(self, depth: int) -> list:
        path = self._data_dir / "lessons" / "lessons.jsonl"
        if not path.exists():
            return []
        try:
            lines = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
        except Exception:
            return []
        active = [l["text"] for l in lines if l.get("enabled", True)]
        return active[-depth:] if depth else []

    def _catalog_layer(self) -> str:
        try:
            import modules
            modules_dir = Path(modules.__file__).parent
            names = sorted(p.name for p in modules_dir.iterdir()
                            if p.is_dir() and not p.name.startswith("_") and p.name != "__pycache__")
        except Exception:
            return ""
        if not names:
            return ""
        return "AVAILABLE MODULES: " + ", ".join(names)

    def _context_layer(self) -> str:
        sessions = self._read_json("session", "sessions.json", default=None)
        if not sessions:
            return ""
        try:
            last = sessions[-1]
        except Exception:
            return ""
        notes = last.get("notes", [])
        if not notes:
            return ""
        lines = [f"- {n.get('text', '')}" for n in notes[-5:]]
        return f"RECENT SESSION ('{last.get('label', '?')}'):\n" + "\n".join(lines)

    def _custom_layer(self) -> str:
        items = self._load_custom()
        if not items:
            return ""
        return "NOTES:\n" + "\n".join(f"- {t}" for t in items)

    def _render_layer(self, layer: str, depth: int) -> str:
        if layer == "persona":
            return self._persona_layer()
        if layer == "rules":
            return self._rules_layer()
        if layer == "memory":
            facts = self._memory_layer(depth)
            return "KNOWN FACTS:\n" + "\n".join(f"- {f}" for f in facts) if facts else ""
        if layer == "lessons":
            lessons = self._lessons_layer(depth)
            return "LEARNED PATTERNS:\n" + "\n".join(f"- {l}" for l in lessons) if lessons else ""
        if layer == "catalog":
            return self._catalog_layer()
        if layer == "context":
            return self._context_layer()
        if layer == "custom":
            return self._custom_layer()
        return ""

    def _compile(self) -> str:
        cfg = self._load_config()
        enabled = [l for l in _ALL_LAYERS if l in set(cfg.get("enabled", []))]
        depth = cfg.get("depth", _DEFAULT_DEPTH)
        budget = cfg.get("budget", _DEFAULT_BUDGET)

        sections = [_IDENTITY]
        for layer in enabled:
            rendered = self._render_layer(layer, depth)
            if rendered:
                sections.append(rendered)

        compiled = "\n\n".join(sections)
        if len(compiled) <= budget:
            return compiled

        # Over budget: shrink memory/lessons depth progressively before giving up and hard-trimming.
        for shrink_depth in range(depth - 1, -1, -1):
            sections = [_IDENTITY]
            for layer in enabled:
                rendered = self._render_layer(layer, shrink_depth) if layer in ("memory", "lessons") \
                    else self._render_layer(layer, depth)
                if rendered:
                    sections.append(rendered)
            compiled = "\n\n".join(sections)
            if len(compiled) <= budget:
                return compiled
        return compiled[:budget] + "\n... (truncated to fit budget)"

    # ------------------------------------------------------------------ #
    @safe
    def cmd_think(self, arg=""):
        """Full pipeline: compile layers, ask the AI, return the answer"""
        message = arg or ""
        if not message:
            return "[brain] Usage: /brain think <message>"
        if not self.ai:
            return ("[brain] No AI provider configured.\n"
                    "  Set AI_PROVIDER (and its API key) in .env, then restart.")
        system = self._compile()
        try:
            result = self.ask_ai(message, system=system)
        except Exception as e:
            return f"[brain] AI error: {e}"
        self._append_history(message, result)
        return result

    @safe
    def cmd_prompt(self, arg=""):
        """Show the compiled system prompt without calling the AI"""
        compiled = self._compile()
        return f"[brain] Compiled system prompt ({len(compiled)} chars):\n\n{compiled}"

    @safe
    def cmd_prompt_for(self, arg=""):
        """Preview one layer's rendered content in isolation: /brain prompt-for <layer>"""
        layer = (arg or "").strip().lower()
        if layer not in _ALL_LAYERS:
            return f"[brain] Usage: /brain prompt-for <{'|'.join(_ALL_LAYERS)}>"
        depth = self._load_config().get("depth", _DEFAULT_DEPTH)
        rendered = self._render_layer(layer, depth)
        return f"[brain] Layer '{layer}':\n{rendered}" if rendered else f"[brain] Layer '{layer}' has no content right now."

    @safe
    def cmd_layers(self, arg=""):
        """Show which layers are currently enabled"""
        cfg = self._load_config()
        enabled = set(cfg.get("enabled", []))
        lines = ["[brain] Layers:"]
        for layer in _ALL_LAYERS:
            lines.append(f"  [{'x' if layer in enabled else ' '}] {layer}")
        lines.append(f"  depth:  {cfg.get('depth', _DEFAULT_DEPTH)}")
        lines.append(f"  budget: {cfg.get('budget', _DEFAULT_BUDGET)} chars")
        return "\n".join(lines)

    @safe
    def cmd_enable(self, arg=""):
        """Enable a layer"""
        layer = (arg or "").strip().lower()
        if layer not in _ALL_LAYERS:
            return f"[brain] Usage: /brain enable <{'|'.join(_ALL_LAYERS)}>"
        cfg = self._load_config()
        enabled = set(cfg.get("enabled", []))
        enabled.add(layer)
        cfg["enabled"] = sorted(enabled)
        self._save_config(cfg)
        return f"[brain] Enabled layer: {layer}"

    @safe
    def cmd_disable(self, arg=""):
        """Disable a layer"""
        layer = (arg or "").strip().lower()
        if layer not in _ALL_LAYERS:
            return f"[brain] Usage: /brain disable <{'|'.join(_ALL_LAYERS)}>"
        cfg = self._load_config()
        enabled = set(cfg.get("enabled", []))
        enabled.discard(layer)
        cfg["enabled"] = sorted(enabled)
        self._save_config(cfg)
        return f"[brain] Disabled layer: {layer}"

    @safe
    def cmd_depth(self, arg=""):
        """How many memory/lesson entries to include (default 10)"""
        s = (arg or "").strip()
        if not s:
            return f"[brain] Current depth: {self._load_config().get('depth', _DEFAULT_DEPTH)}"
        try:
            n = int(s)
        except Exception:
            return "[brain] Depth must be an integer"
        cfg = self._load_config()
        cfg["depth"] = max(0, n)
        self._save_config(cfg)
        return f"[brain] Depth set to {cfg['depth']}"

    @safe
    def cmd_budget(self, arg=""):
        """Max compiled-prompt size before trimming (default 8000): /brain budget [chars]"""
        s = (arg or "").strip()
        if not s:
            return f"[brain] Current budget: {self._load_config().get('budget', _DEFAULT_BUDGET)} chars"
        try:
            n = int(s)
        except Exception:
            return "[brain] Budget must be an integer (character count)"
        if n < 500:
            return "[brain] Budget must be at least 500 chars — the identity layer alone needs room."
        cfg = self._load_config()
        cfg["budget"] = n
        self._save_config(cfg)
        return f"[brain] Budget set to {n} chars"

    @safe
    def cmd_add_custom(self, arg=""):
        """Add an ad-hoc custom layer entry: /brain add-custom <text>"""
        text = (arg or "").strip()
        if not text:
            return "[brain] Usage: /brain add-custom <text>"
        items = self._load_custom()
        items.append(text)
        self._save_custom(items)
        return f"[brain] Added custom entry #{len(items)}. Enable the 'custom' layer with /brain enable custom"

    @safe
    def cmd_remove_custom(self, arg=""):
        """Remove a custom layer entry by index: /brain remove-custom <index>"""
        s = (arg or "").strip()
        if not s.isdigit():
            return "[brain] Usage: /brain remove-custom <index> (see /brain list-custom for indices)"
        idx = int(s) - 1
        items = self._load_custom()
        if idx < 0 or idx >= len(items):
            return f"[brain] No custom entry #{s}"
        removed = items.pop(idx)
        self._save_custom(items)
        return f"[brain] Removed custom entry: {removed[:80]}"

    @safe
    def cmd_list_custom(self, arg=""):
        """List custom layer entries"""
        items = self._load_custom()
        if not items:
            return "[brain] No custom entries. /brain add-custom <text>"
        lines = [f"[brain] {len(items)} custom entry(ies):"]
        for i, text in enumerate(items, 1):
            lines.append(f"  {i}. {text}")
        return "\n".join(lines)

    @safe
    def cmd_status(self, arg=""):
        """Persona/profile, memory/lesson counts, AI availability"""
        persona_data = self._read_json("persona", "personas.json", default={})
        active_persona = persona_data.get("active", "(none)") if persona_data else "(none)"
        memory_data = self._read_json("memory", "memories.json", default={})
        memory_count = len(memory_data.get("facts", [])) if memory_data else 0
        lessons_path = self._data_dir / "lessons" / "lessons.jsonl"
        lesson_count = 0
        if lessons_path.exists():
            lesson_count = len([l for l in lessons_path.read_text(encoding="utf-8").splitlines() if l.strip()])
        aiconfig_data = self._read_json("aiconfig", "profiles.json", default={})
        active_profile = aiconfig_data.get("active", "(none)") if aiconfig_data else "(none)"
        custom_count = len(self._load_custom())
        history_count = len(self._read_history(10_000_000))

        lines = ["[brain] Status:"]
        lines.append(f"  AI provider:   {'configured' if self.ai else 'NOT configured'}")
        lines.append(f"  AI profile:    {active_profile}")
        lines.append(f"  Persona:       {active_persona}")
        lines.append(f"  Memories:      {memory_count}")
        lines.append(f"  Lessons:       {lesson_count}")
        lines.append(f"  Custom layers: {custom_count}")
        lines.append(f"  Think history: {history_count} exchange(s) recorded")
        return "\n".join(lines)

    @safe
    def cmd_history(self, arg=""):
        """Recent /brain think exchanges (persisted, default 20): /brain history [n]"""
        s = (arg or "").strip()
        try:
            limit = int(s) if s else 20
        except ValueError:
            limit = 20
        entries = self._read_history(limit)
        if not entries:
            return "[brain] No exchanges recorded yet."
        lines = [f"[brain] Last {len(entries)} exchange(s):"]
        for e in entries:
            lines.append(f"  [{e.get('at', '?')}] Q: {e.get('q', '')} -> A: {e.get('a', '')}")
        return "\n".join(lines)

    @safe
    def cmd_history_clear(self, arg=""):
        """Clear persisted think history (confirms): /brain history-clear confirm"""
        if (arg or "").strip().lower() != "confirm":
            return "[brain] Re-run as: /brain history-clear confirm"
        n = len(self._read_history(10_000_000))
        if self._history_file.exists():
            self._history_file.unlink()
        return f"[brain] Cleared {n} recorded exchange(s)"

    @safe
    def cmd_export(self, arg=""):
        """Write the compiled prompt to a file: /brain export <path>"""
        path = (arg or "").strip()
        if not path:
            return "[brain] Usage: /brain export <path>"
        try:
            Path(path).expanduser().write_text(self._compile(), encoding="utf-8")
        except Exception as e:
            return f"[brain] Failed to write {path}: {e}"
        return f"[brain] Exported compiled prompt to {path}"

    @safe
    def cmd_reset(self, arg=""):
        """Reset layer toggles, depth, budget to defaults"""
        self._save_config({"enabled": list(_ALL_LAYERS[:5]), "depth": _DEFAULT_DEPTH, "budget": _DEFAULT_BUDGET})
        return "[brain] Reset to defaults (persona/rules/memory/lessons/catalog enabled, depth=10, budget=8000)"

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
