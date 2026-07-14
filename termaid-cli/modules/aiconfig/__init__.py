"""AIConfig Module — AI behavior config profiles bundling persona + rules.

Where /persona is one identity and /rules/hardlines are separate stores,
/aiconfig lets you bundle a persona description + a set of rules + a set of
immutable "hardlines" into one named, switchable profile — compiled together
into a single system prompt on demand. Profiles can be cloned, diffed,
imported, and have individual rules/hardlines removed as well as added.

Commands (~17):
  /aiconfig create <name>                    Create an empty profile
  /aiconfig clone <src> <dst>                  Duplicate a profile under a new name
  /aiconfig activate <name>                      Set the active profile
  /aiconfig list                                   List all profiles
  /aiconfig show [name]                              Show a profile (default: active)
  /aiconfig delete <name>                              Delete a profile
  /aiconfig diff <name1> <name2>                         Compare two profiles
  /aiconfig set-persona <name> <description>               Set the profile's persona text
  /aiconfig add-rule <name> <rule>                           Add a (mutable) rule
  /aiconfig remove-rule <name> <index>                         Remove a rule by index
  /aiconfig add-hardline <name> <hardline>                       Add an immutable hardline
  /aiconfig remove-hardline <name> <index>                         Remove a hardline by index
  /aiconfig compile [name]                                           Render the profile as a system prompt
  /aiconfig ask <message>                                              Ask the AI using the active profile
  /aiconfig export [path]                                                Export all profiles to JSON
  /aiconfig import <path>                                                  Import profiles from a JSON file
  /aiconfig explain                                                          How this module works
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


_DEFAULT_PROFILE = {
    "persona": "You are TermAId, a terminal-native assistant.",
    "rules": [],
    "hardlines": ["Never reveal API keys or secrets.", "Never claim to have run a command you did not run."],
}


class AIConfigModule(Module):
    name = "aiconfig"
    version = "1.1.0"
    description = "AI behavior config profiles bundling persona + rules + hardlines"
    author = "termaid"

    def on_load(self):
        for cmd in ["create", "clone", "activate", "list", "show", "delete", "diff",
                    "set-persona", "add-rule", "remove-rule", "add-hardline", "remove-hardline",
                    "compile", "ask", "export", "import", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "aiconfig"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "profiles.json"
        if not self._file.exists():
            self._save({"profiles": {"default": dict(_DEFAULT_PROFILE)}, "active": "default"})

    def _load(self) -> tuple:
        try:
            data = json.loads(self._file.read_text(encoding="utf-8"))
            return data.get("profiles", {"default": _DEFAULT_PROFILE}), data.get("active", "default")
        except Exception:
            return {"default": dict(_DEFAULT_PROFILE)}, "default"

    def _save(self, data: dict) -> None:
        self._file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _save_all(self, profiles: dict, active: str) -> None:
        self._save({"profiles": profiles, "active": active})

    def _compile(self, profile: dict) -> str:
        sections = [profile.get("persona", "")]
        if profile.get("rules"):
            sections.append("RULES:\n" + "\n".join(f"- {r}" for r in profile["rules"]))
        if profile.get("hardlines"):
            sections.append("HARDLINES (never violate):\n" + "\n".join(f"- {h}" for h in profile["hardlines"]))
        return "\n\n".join(s for s in sections if s)

    @safe
    def cmd_create(self, arg=""):
        """Create an empty profile"""
        name = (arg or "").strip()
        if not name:
            return "[aiconfig] Usage: /aiconfig create <name>"
        profiles, active = self._load()
        if name in profiles:
            return f"[aiconfig] '{name}' already exists"
        profiles[name] = {"persona": "", "rules": [], "hardlines": []}
        self._save_all(profiles, active)
        return f"[aiconfig] Created '{name}'. /aiconfig set-persona {name} <description>"

    @safe
    def cmd_clone(self, arg=""):
        """Duplicate a profile under a new name: /aiconfig clone <src> <dst>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[aiconfig] Usage: /aiconfig clone <src> <dst>"
        src, dst = parts
        profiles, active = self._load()
        if src not in profiles:
            return f"[aiconfig] No profile named '{src}'"
        if dst in profiles:
            return f"[aiconfig] '{dst}' already exists"
        profiles[dst] = json.loads(json.dumps(profiles[src]))  # deep copy
        self._save_all(profiles, active)
        return f"[aiconfig] Cloned '{src}' -> '{dst}'"

    @safe
    def cmd_activate(self, arg=""):
        """Set the active profile"""
        name = (arg or "").strip()
        if not name:
            return "[aiconfig] Usage: /aiconfig activate <name>"
        profiles, active = self._load()
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        self._save_all(profiles, name)
        return f"[aiconfig] Active profile: {name}"

    @safe
    def cmd_list(self, arg=""):
        """List all profiles"""
        profiles, active = self._load()
        lines = [f"[aiconfig] {len(profiles)} profile(s):"]
        for name in sorted(profiles):
            lines.append(f"  {name}{' (active)' if name == active else ''}")
        return "\n".join(lines)

    @safe
    def cmd_show(self, arg=""):
        """Show a profile (default: active)"""
        profiles, active = self._load()
        name = (arg or "").strip() or active
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        p = profiles[name]
        lines = [f"[aiconfig] {name}{' (active)' if name == active else ''}:"]
        lines.append(f"  persona:   {p.get('persona', '')}")
        lines.append(f"  rules ({len(p.get('rules', []))}):")
        for i, r in enumerate(p.get("rules", []), 1):
            lines.append(f"    {i}. {r}")
        lines.append(f"  hardlines ({len(p.get('hardlines', []))}):")
        for i, h in enumerate(p.get("hardlines", []), 1):
            lines.append(f"    {i}. {h}")
        return "\n".join(lines)

    @safe
    def cmd_delete(self, arg=""):
        """Delete a profile"""
        name = (arg or "").strip()
        if name == "default":
            return "[aiconfig] Cannot delete the built-in 'default' profile"
        profiles, active = self._load()
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        del profiles[name]
        if active == name:
            active = "default"
        self._save_all(profiles, active)
        return f"[aiconfig] Deleted '{name}'"

    @safe
    def cmd_diff(self, arg=""):
        """Compare two profiles: /aiconfig diff <name1> <name2>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[aiconfig] Usage: /aiconfig diff <name1> <name2>"
        name1, name2 = parts
        profiles, _ = self._load()
        if name1 not in profiles or name2 not in profiles:
            missing = name1 if name1 not in profiles else name2
            return f"[aiconfig] No profile named '{missing}'"
        p1, p2 = profiles[name1], profiles[name2]
        lines = [f"[aiconfig] {name1} vs {name2}:"]
        if p1.get("persona", "") != p2.get("persona", ""):
            lines.append(f"  persona:\n    {name1}: {p1.get('persona', '')}\n    {name2}: {p2.get('persona', '')}")
        else:
            lines.append("  persona: (same)")
        r1, r2 = set(p1.get("rules", [])), set(p2.get("rules", []))
        only1, only2 = r1 - r2, r2 - r1
        if only1 or only2:
            lines.append(f"  rules only in {name1}: {sorted(only1) or '(none)'}")
            lines.append(f"  rules only in {name2}: {sorted(only2) or '(none)'}")
        else:
            lines.append("  rules: (same)")
        h1, h2 = set(p1.get("hardlines", [])), set(p2.get("hardlines", []))
        only1, only2 = h1 - h2, h2 - h1
        if only1 or only2:
            lines.append(f"  hardlines only in {name1}: {sorted(only1) or '(none)'}")
            lines.append(f"  hardlines only in {name2}: {sorted(only2) or '(none)'}")
        else:
            lines.append("  hardlines: (same)")
        return "\n".join(lines)

    @safe
    def cmd_set_persona(self, arg=""):
        """Set the profile's persona text: /aiconfig set-persona <name> <description>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[aiconfig] Usage: /aiconfig set-persona <name> <description>"
        name, description = parts
        profiles, active = self._load()
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        profiles[name]["persona"] = description
        self._save_all(profiles, active)
        return f"[aiconfig] '{name}' persona updated"

    @safe
    def cmd_add_rule(self, arg=""):
        """Add a (mutable) rule: /aiconfig add-rule <name> <rule>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[aiconfig] Usage: /aiconfig add-rule <name> <rule text>"
        name, rule = parts
        profiles, active = self._load()
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        profiles[name].setdefault("rules", []).append(rule)
        self._save_all(profiles, active)
        return f"[aiconfig] Added rule to '{name}'"

    @safe
    def cmd_remove_rule(self, arg=""):
        """Remove a rule by index: /aiconfig remove-rule <name> <index>"""
        parts = (arg or "").split()
        if len(parts) != 2 or not parts[1].isdigit():
            return "[aiconfig] Usage: /aiconfig remove-rule <name> <index> (see /aiconfig show <name> for indices)"
        name, idx_s = parts
        profiles, active = self._load()
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        rules = profiles[name].get("rules", [])
        idx = int(idx_s) - 1
        if idx < 0 or idx >= len(rules):
            return f"[aiconfig] No rule #{idx_s} in '{name}'"
        removed = rules.pop(idx)
        self._save_all(profiles, active)
        return f"[aiconfig] Removed rule from '{name}': {removed}"

    @safe
    def cmd_add_hardline(self, arg=""):
        """Add an immutable hardline: /aiconfig add-hardline <name> <hardline>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[aiconfig] Usage: /aiconfig add-hardline <name> <hardline text>"
        name, hardline = parts
        profiles, active = self._load()
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        profiles[name].setdefault("hardlines", []).append(hardline)
        self._save_all(profiles, active)
        return f"[aiconfig] Added hardline to '{name}'"

    @safe
    def cmd_remove_hardline(self, arg=""):
        """Remove a hardline by index: /aiconfig remove-hardline <name> <index>"""
        parts = (arg or "").split()
        if len(parts) != 2 or not parts[1].isdigit():
            return "[aiconfig] Usage: /aiconfig remove-hardline <name> <index> (see /aiconfig show <name> for indices)"
        name, idx_s = parts
        profiles, active = self._load()
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        hardlines = profiles[name].get("hardlines", [])
        idx = int(idx_s) - 1
        if idx < 0 or idx >= len(hardlines):
            return f"[aiconfig] No hardline #{idx_s} in '{name}'"
        removed = hardlines.pop(idx)
        self._save_all(profiles, active)
        return f"[aiconfig] Removed hardline from '{name}': {removed}"

    @safe
    def cmd_compile(self, arg=""):
        """Render the profile as a system prompt"""
        profiles, active = self._load()
        name = (arg or "").strip() or active
        if name not in profiles:
            return f"[aiconfig] No profile named '{name}'"
        return f"[aiconfig] Compiled '{name}':\n\n{self._compile(profiles[name])}"

    @safe
    def cmd_ask(self, arg=""):
        """Ask the AI using the active profile"""
        message = arg or ""
        if not message:
            return "[aiconfig] Usage: /aiconfig ask <message>"
        if not self.ai:
            return "[aiconfig] No AI provider configured."
        profiles, active = self._load()
        try:
            return self.ask_ai(message, system=self._compile(profiles[active]))
        except Exception as e:
            return f"[aiconfig] AI error: {e}"

    @safe
    def cmd_export(self, arg=""):
        """Export all profiles to JSON: /aiconfig export [path]"""
        path = (arg or "").strip() or str(self._dir / "profiles-export.json")
        profiles, active = self._load()
        try:
            Path(path).expanduser().write_text(json.dumps({"profiles": profiles, "active": active}, indent=2),
                                                encoding="utf-8")
        except Exception as e:
            return f"[aiconfig] Failed to write {path}: {e}"
        return f"[aiconfig] Exported to {path}"

    @safe
    def cmd_import(self, arg=""):
        """Import profiles from a JSON file (merges, doesn't overwrite existing names): /aiconfig import <path>"""
        path = (arg or "").strip()
        if not path:
            return "[aiconfig] Usage: /aiconfig import <path>"
        p = Path(path).expanduser()
        if not p.is_file():
            return f"[aiconfig] Not found: {p}"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return f"[aiconfig] Couldn't parse {p}: {e}"
        incoming = data.get("profiles", {})
        if not isinstance(incoming, dict):
            return f"[aiconfig] {p} doesn't look like an aiconfig export (no 'profiles' object)"
        profiles, active = self._load()
        added, skipped = [], []
        for name, prof in incoming.items():
            if name in profiles:
                skipped.append(name)
                continue
            profiles[name] = prof
            added.append(name)
        self._save_all(profiles, active)
        msg = f"[aiconfig] Imported {len(added)} profile(s): {', '.join(added) or '(none)'}"
        if skipped:
            msg += f"\n  Skipped (name already exists): {', '.join(skipped)}"
        return msg

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
