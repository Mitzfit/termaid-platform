"""Proj Module — Minimal project scaffolding.

Creates a small starter layout for a handful of common project shapes
(a README, .gitignore, and the one or two files each ecosystem expects
to see first) — not a full framework generator. Refuses to write into a
non-empty directory so it can never clobber existing work.

Commands (~3):
  /proj templates          List available template names
  /proj new <type> <path>     Scaffold a new project of that type
  /proj explain                 How this module works
"""

from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TEMPLATES = {
    "python": {
        "README.md": "# {name}\n\nDescribe your project here.\n",
        ".gitignore": "__pycache__/\n*.pyc\n.venv/\n.env\n",
        "main.py": "def main():\n    print(\"Hello from {name}\")\n\n\nif __name__ == \"__main__\":\n    main()\n",
        "requirements.txt": "",
    },
    "node": {
        "README.md": "# {name}\n\nDescribe your project here.\n",
        ".gitignore": "node_modules/\n.env\ndist/\n",
        "package.json": '{{\n  "name": "{name}",\n  "version": "0.1.0",\n  "main": "index.js"\n}}\n',
        "index.js": "console.log(\"Hello from {name}\");\n",
    },
    "empty": {
        "README.md": "# {name}\n\nDescribe your project here.\n",
        ".gitignore": "",
    },
}


class ProjModule(Module):
    name = "proj"
    version = "1.0.0"
    description = "Minimal project scaffolding"
    author = "termaid"

    def on_load(self):
        for cmd in ["templates", "new", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_templates(self, arg=""):
        """List available template names"""
        lines = ["[proj] Templates:"]
        for name, files in _TEMPLATES.items():
            lines.append(f"  {name:10s} ({len(files)} file(s): {', '.join(files.keys())})")
        return "\n".join(lines)

    @safe
    def cmd_new(self, arg=""):
        """Scaffold a new project of that type: /proj new <type> <path>"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[proj] Usage: /proj new <type> <path>\n" + self.cmd_templates("")
        ptype, path = parts[0], parts[1]
        if ptype not in _TEMPLATES:
            return f"[proj] Unknown template '{ptype}'. See /proj templates"
        target = Path(path).expanduser().resolve()
        if target.exists() and any(target.iterdir()):
            return f"[proj] Refusing to scaffold into non-empty directory: {target}"
        target.mkdir(parents=True, exist_ok=True)
        name = target.name
        for filename, content in _TEMPLATES[ptype].items():
            (target / filename).write_text(content.format(name=name), encoding="utf-8")
        return f"[proj] Created '{ptype}' project at {target} ({len(_TEMPLATES[ptype])} file(s))"

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
