"""Rules Module — Restrictions and instructions for AI behavior.

Stores two lists: "instructions" (positive guidance the AI should follow) and
"restrictions" (things it must never do). /brain and /aiconfig both read this
same on-disk file as one of their layers, so rules set here flow into any AI
call that composes its system prompt through them.

Commands (~11):
  /rules add-instruction <text>     Add a positive instruction
  /rules add-restriction <text>       Add a restriction (a "must not")
  /rules list                            List all rules
  /rules remove <id>                       Remove a rule by ID
  /rules toggle <id>                         Enable/disable a rule
  /rules clear                                 Remove all (confirms)
  /rules compile                                 Render as a directive block
  /rules explain                                   How this module works
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


class RulesModule(Module):
    name = "rules"
    version = "1.0.0"
    description = "Restrictions and instructions for AI behavior"
    author = "termaid"

    def on_load(self):
        for cmd in ["add-instruction", "add-restriction", "list", "remove",
                    "toggle", "clear", "compile", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "rules"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "rules.json"
        if not self._file.exists():
            self._save({"instructions": [], "restrictions": []})

    def _load(self) -> dict:
        try:
            data = json.loads(self._file.read_text())
            data.setdefault("instructions", [])
            data.setdefault("restrictions", [])
            return data
        except Exception:
            return {"instructions": [], "restrictions": []}

    def _save(self, data: dict) -> None:
        self._file.write_text(json.dumps(data, indent=2))

    def _next_id(self, data: dict) -> int:
        all_ids = [r.get("id", 0) for r in data["instructions"] + data["restrictions"]]
        return max(all_ids, default=0) + 1

    @safe
    def cmd_add_instruction(self, arg=""):
        """Add a positive instruction"""
        text = (arg or "").strip()
        if not text:
            return "[rules] Usage: /rules add-instruction <text>"
        data = self._load()
        rid = self._next_id(data)
        data["instructions"].append({"id": rid, "text": text, "enabled": True,
                                    "created": time.strftime("%Y-%m-%d %H:%M:%S")})
        self._save(data)
        return f"[rules] Added instruction [{rid}]: {text}"

    @safe
    def cmd_add_restriction(self, arg=""):
        """Add a restriction (a 'must not')"""
        text = (arg or "").strip()
        if not text:
            return "[rules] Usage: /rules add-restriction <text>"
        data = self._load()
        rid = self._next_id(data)
        data["restrictions"].append({"id": rid, "text": text, "enabled": True,
                                    "created": time.strftime("%Y-%m-%d %H:%M:%S")})
        self._save(data)
        return f"[rules] Added restriction [{rid}]: {text}"

    @safe
    def cmd_list(self, arg=""):
        """List all rules"""
        data = self._load()
        if not data["instructions"] and not data["restrictions"]:
            return "[rules] No rules yet. /rules add-instruction or /rules add-restriction"
        lines = ["[rules]"]
        if data["instructions"]:
            lines.append("  Instructions:")
            for r in data["instructions"]:
                mark = "x" if r.get("enabled", True) else " "
                lines.append(f"    [{mark}] [{r['id']:>3d}] {r['text']}")
        if data["restrictions"]:
            lines.append("  Restrictions:")
            for r in data["restrictions"]:
                mark = "x" if r.get("enabled", True) else " "
                lines.append(f"    [{mark}] [{r['id']:>3d}] MUST NOT: {r['text']}")
        return "\n".join(lines)

    @safe
    def cmd_remove(self, arg=""):
        """Remove a rule by ID"""
        try:
            rid = int((arg or "").strip())
        except Exception:
            return "[rules] Usage: /rules remove <id>"
        data = self._load()
        for key in ("instructions", "restrictions"):
            before = len(data[key])
            data[key] = [r for r in data[key] if r.get("id") != rid]
            if len(data[key]) != before:
                self._save(data)
                return f"[rules] Removed [{rid}]"
        return f"[rules] No rule [{rid}]"

    @safe
    def cmd_toggle(self, arg=""):
        """Enable/disable a rule"""
        try:
            rid = int((arg or "").strip())
        except Exception:
            return "[rules] Usage: /rules toggle <id>"
        data = self._load()
        for key in ("instructions", "restrictions"):
            for r in data[key]:
                if r.get("id") == rid:
                    r["enabled"] = not r.get("enabled", True)
                    self._save(data)
                    return f"[rules] [{rid}] {'enabled' if r['enabled'] else 'disabled'}"
        return f"[rules] No rule [{rid}]"

    @safe
    def cmd_clear(self, arg=""):
        """Remove all (confirms)"""
        if (arg or "").strip().lower() != "confirm":
            return "[rules] This removes ALL rules. Re-run as: /rules clear confirm"
        self._save({"instructions": [], "restrictions": []})
        return "[rules] Cleared all rules."

    @safe
    def cmd_compile(self, arg=""):
        """Render as a directive block"""
        data = self._load()
        lines = []
        enabled_instr = [r["text"] for r in data["instructions"] if r.get("enabled", True)]
        enabled_restr = [r["text"] for r in data["restrictions"] if r.get("enabled", True)]
        if enabled_instr:
            lines.append("INSTRUCTIONS:\n" + "\n".join(f"- {t}" for t in enabled_instr))
        if enabled_restr:
            lines.append("RESTRICTIONS:\n" + "\n".join(f"- MUST NOT: {t}" for t in enabled_restr))
        return "\n\n".join(lines) if lines else "[rules] No enabled rules to compile."

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
