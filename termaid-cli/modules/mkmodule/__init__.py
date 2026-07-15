"""MkModule Module — AI-assisted creation of your own TermAId modules. DANGEROUS tier.

Same risk class as /selfmod (writes Python that the backend will load and
execute with its own privileges on next restart), and reuses the exact
same discipline: draft first, write nothing until you say `confirm`,
`compile()`-validate syntax before it ever touches disk, back up anything
it would overwrite.

The flow is two steps, not one, on purpose:
  1. `draft` asks the AI to generate an implementation and writes it to a
     STAGING file under TermAId's own data dir — never directly into
     modules/. You can review it there, and edit it with any text editor
     you like before the next step; nothing about this tool is special
     about that file, it's just a plain .py file at a path this module
     tells you.
  2. `create` reads that staged file (whatever state you left it in,
     AI-drafted or hand-edited) and promotes it into modules/<name>/__init__.py.

A newly created module isn't in any policy.py tier, which means: it loads
automatically in local mode (the existing default-allow behavior for
anything not explicitly DANGEROUS) but stays blocked in server mode until
someone deliberately categorizes it — this module never edits policy.py
itself, same boundary /selfmod draws around the access-control engine.

Commands (~7):
  /mkmodule template [name]                  Print an annotated blank module template
  /mkmodule draft <name> <description>         AI drafts an implementation to a staging file
  /mkmodule view-draft <name>                    Show the current staged draft
  /mkmodule list-drafts                            List staged drafts not yet created
  /mkmodule create <name> confirm                    Promote a staged draft into modules/
  /mkmodule list-custom                                List modules created via this tool
  /mkmodule explain                                       How this module works
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

_TEMPLATE = '''"""{title} Module — {one_liner}.

Commands (~N):
  /{name} <command> <args>       Describe what it does
  /{name} explain                   How this module works
"""

from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class {classname}Module(Module):
    name = "{name}"
    version = "1.0.0"
    description = "{one_liner}"
    author = "termaid"

    def on_load(self):
        for cmd in ["explain"]:  # add your command names here
            self.register_command(cmd, getattr(self, f"cmd_{{cmd}}"))

    # For anything that reads/writes real files, add a data dir like this:
    #     from pathlib import Path
    #     import os, sys
    #     home = Path.home()
    #     if sys.platform == "win32":
    #         data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
    #     else:
    #         data_dir = home / ".termaid"
    #     self._dir = data_dir / "{name}"
    #     self._dir.mkdir(parents=True, exist_ok=True)

    # Destructive commands should require a literal "confirm" argument, e.g.:
    #     @safe
    #     def cmd_delete(self, arg=""):
    #         if (arg or "").strip().lower() != "confirm":
    #             return "[{name}] This deletes X. Re-run as: /{name} delete confirm"
    #         ...

    @safe
    def cmd_explain(self, arg=""):
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{{self.name}}] {{self.description}}", "", "Commands:"]
            for c in cmds:
                lines.append(f"  /{{self.name}} {{c}}")
            return "\\n".join(lines)
'''

_DRAFT_SYSTEM_PROMPT = """You write TermAId modules. Follow these conventions exactly — they aren't
style preferences, they're what makes the module loadable and safe:

1. One class per file, subclassing `from termaid.extensions.modules import Module`.
2. Class attributes: name, version ("1.0.0"), description, author = "termaid".
3. `on_load(self)` registers every command: `self.register_command(cmd_name, getattr(self, f"cmd_{cmd_name}"))`
   for each name in a list. Command names use hyphens in the registered string but
   underscores in the method name (e.g. "list-things" -> cmd_list_things).
4. Every command is `def cmd_<name>(self, arg="") -> str`, decorated with `@safe`
   (imported via `try: from _shared.error_helper import safe / except ImportError: def safe(fn): return fn`
   at the top of the file — always include this exact fallback).
5. ANY command that deletes, overwrites, or otherwise can't be undone must require
   a literal "confirm" argument before doing the real action, and its usage message
   must show the exact confirm syntax. Never use input() or any blocking prompt —
   this runs on a single-threaded async server shared by every connected user, and
   a blocking call freezes it for all of them, not just the caller.
6. Any subprocess call must use list-form args (["cmd", "arg1", "arg2"]), never
   shell=True and never an f-string built into a single shell command string,
   UNLESS the module's entire stated purpose is running an arbitrary raw command
   the user explicitly typed (rare — only do this if asked for literally that).
   Every subprocess call needs an explicit timeout= — never an unbounded wait.
7. If the module needs its own data directory, use:
   home = Path.home(); if sys.platform == "win32": data_dir = Path(os.environ.get("APPDATA", ...)) / "termaid"
   else: data_dir = home / ".termaid"; then a subdirectory named after the module.
8. Every module ends with a cmd_explain that tries `from _shared.explain import auto_explain`
   and falls back to listing registered commands if that import fails.
9. Docstring at the top of the file: one-line description, then a "Commands (~N):"
   block listing every command with its usage.
10. Default to no comments in the body; only comment a genuinely non-obvious
    constraint or workaround.

Output ONLY the complete Python file content for modules/<name>/__init__.py,
nothing else — no markdown fences, no explanation before or after."""


class MkModuleModule(Module):
    name = "mkmodule"
    version = "1.0.0"
    description = "AI-assisted creation of your own TermAId modules"
    author = "termaid"

    def on_load(self):
        for cmd in ["template", "draft", "view-draft", "list-drafts", "create", "list-custom", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._drafts_dir = data_dir / "mkmodule_drafts"
        self._drafts_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = data_dir / "mkmodule_registry.json"
        self._modules_dir = Path(__file__).resolve().parent.parent

    def _safe_name(self, name: str) -> bool:
        return name.isidentifier() and not name.startswith("_")

    def _load_registry(self) -> dict:
        if self._registry_path.exists():
            try:
                return json.loads(self._registry_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_registry(self, reg: dict) -> None:
        self._registry_path.write_text(json.dumps(reg, indent=2), encoding="utf-8")

    @safe
    def cmd_template(self, arg=""):
        """Print an annotated blank module template: /mkmodule template [name]"""
        name = (arg or "mycommand").strip() or "mycommand"
        if not self._safe_name(name):
            return "[mkmodule] Name must be a valid Python identifier (letters, digits, underscore, not starting with a digit)."
        classname = "".join(part.capitalize() for part in name.split("_"))
        filled = _TEMPLATE.format(title=name.capitalize(), one_liner="Describe what this module does",
                                  name=name, classname=classname)
        return f"[mkmodule] Template for '{name}':\n\n{filled}"

    @safe
    def cmd_draft(self, arg=""):
        """AI drafts an implementation to a staging file: /mkmodule draft <name> <description>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[mkmodule] Usage: /mkmodule draft <name> <description of what it should do>"
        name, description = parts
        if not self._safe_name(name):
            return "[mkmodule] Name must be a valid Python identifier (letters, digits, underscore, not starting with a digit)."
        if not self.ai:
            return ("[mkmodule] No AI provider configured, so I can't draft one for you — "
                    "see /mkmodule template for a blank starting point you can fill in by hand instead.")
        try:
            code = self.ask_ai(
                f"Write a TermAId module named '{name}' that does the following: {description}",
                system=_DRAFT_SYSTEM_PROMPT,
            )
        except Exception as e:
            return f"[mkmodule] AI error: {e}"
        code = code.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            code = "\n".join(lines[1:-1]) if lines[-1].strip().startswith("```") else "\n".join(lines[1:])
        draft_path = self._drafts_dir / f"{name}.py"
        draft_path.write_text(code, encoding="utf-8")
        try:
            compile(code, str(draft_path), "exec")
            syntax_note = "syntax OK"
        except SyntaxError as e:
            syntax_note = f"SYNTAX ERROR at line {e.lineno}: {e.msg} — review before creating"
        return (f"[mkmodule] Drafted '{name}' -> {draft_path} ({syntax_note})\n\n"
                f"Review it (edit the file directly with any editor if you want changes), then:\n"
                f"  /mkmodule view-draft {name}\n"
                f"  /mkmodule create {name} confirm")

    @safe
    def cmd_view_draft(self, arg=""):
        """Show the current staged draft: /mkmodule view-draft <name>"""
        name = (arg or "").strip()
        if not name:
            return "[mkmodule] Usage: /mkmodule view-draft <name>"
        draft_path = self._drafts_dir / f"{name}.py"
        if not draft_path.is_file():
            return f"[mkmodule] No draft named '{name}'. See /mkmodule list-drafts"
        return f"[mkmodule] {draft_path}:\n\n{draft_path.read_text(encoding='utf-8', errors='replace')}"

    @safe
    def cmd_list_drafts(self, arg=""):
        """List staged drafts not yet created"""
        drafts = sorted(self._drafts_dir.glob("*.py"))
        if not drafts:
            return "[mkmodule] No drafts yet. /mkmodule draft <name> <description>"
        lines = [f"[mkmodule] {len(drafts)} draft(s):"]
        for p in drafts:
            lines.append(f"  {p.stem:20s} {p.stat().st_size:,} bytes")
        return "\n".join(lines)

    @safe
    def cmd_create(self, arg=""):
        """Promote a staged draft into modules/ (confirms): /mkmodule create <name> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[mkmodule] Usage: /mkmodule create <name> confirm"
        name = parts[0]
        if not self._safe_name(name):
            return "[mkmodule] Name must be a valid Python identifier."
        draft_path = self._drafts_dir / f"{name}.py"
        if not draft_path.is_file():
            return f"[mkmodule] No draft named '{name}'. /mkmodule draft {name} <description> first."

        code = draft_path.read_text(encoding="utf-8", errors="replace")
        try:
            compile(code, f"{name}/__init__.py", "exec")
        except SyntaxError as e:
            return f"[mkmodule] Refusing to create — draft has a syntax error at line {e.lineno}: {e.msg}"

        registry = self._load_registry()
        target_dir = self._modules_dir / name
        target = target_dir / "__init__.py"
        if target.is_file() and name not in registry:
            return (f"[mkmodule] '{name}' already exists as a built-in module and wasn't created by "
                    f"this tool — refusing to overwrite it. Pick a different name.")

        backup_note = ""
        if target.is_file():
            backup_dir = self._drafts_dir / "_backups"
            backup_dir.mkdir(exist_ok=True)
            backup_path = backup_dir / f"{name}__{time.strftime('%Y%m%d-%H%M%S')}.py"
            backup_path.write_text(target.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
            backup_note = f" (previous version backed up to {backup_path.name})"

        target_dir.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        registry[name] = {"created": time.strftime("%Y-%m-%d %H:%M:%S")}
        self._save_registry(registry)
        return (f"[mkmodule] Created modules/{name}/__init__.py{backup_note}. "
                f"Restart the backend to load it — it isn't in any policy.py tier, so it loads "
                f"automatically in local mode but stays blocked in server mode until categorized there.")

    @safe
    def cmd_list_custom(self, arg=""):
        """List modules created via this tool"""
        registry = self._load_registry()
        if not registry:
            return "[mkmodule] No custom modules created yet."
        lines = [f"[mkmodule] {len(registry)} custom module(s):"]
        for name, info in sorted(registry.items()):
            exists = "" if (self._modules_dir / name / "__init__.py").is_file() else "  (files missing)"
            lines.append(f"  {name:20s} created {info.get('created', '?')}{exists}")
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
