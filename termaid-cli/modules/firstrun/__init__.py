"""FirstRun Module — First-run setup checklist. DANGEROUS tier.

A module has no handle back into the command dispatcher (same limitation
documented in /chain), so this can't actually execute the setup steps for
you — it tracks whether first-run has been marked complete and hands you
the concrete checklist of commands to run yourself, in order. Classified
DANGEROUS not because checking a flag is risky, but because a first-run
wizard is exactly the kind of thing that could otherwise be tempting to
build as auto-executing, and this codebase's whole discipline this session
has been: nothing destructive or configuration-changing runs without an
explicit, separate, human-typed command.

Commands (~2):
  /firstrun status         Has first-run setup been completed?
  /firstrun run               Show the checklist and mark it complete
  /firstrun explain               How this module works
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

_CHECKLIST = (
    "First-run checklist (run each yourself, in order):\n"
    "  1. /doctor check              — confirm the tools TermAId's modules lean on are installed\n"
    "  2. /autoconfig detect          — see what defaults would be set, then /autoconfig apply confirm\n"
    "  3. /persona list                — pick a persona, or /persona create <name> for your own\n"
    "  4. /aiconfig list                 — set up an AI behavior profile if you'll use AI features\n"
    "  5. /security audit                  — know your starting security posture\n"
    "  6. /catalog modules                    — see everything else that's available"
)


class FirstRunModule(Module):
    name = "firstrun"
    version = "1.0.0"
    description = "First-run setup checklist"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "run", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._marker = data_dir / "firstrun_done.json"

    @safe
    def cmd_status(self, arg=""):
        """Has first-run setup been completed?"""
        if not self._marker.exists():
            return "[firstrun] Not yet completed. Run /firstrun run to see the checklist."
        try:
            data = json.loads(self._marker.read_text(encoding="utf-8"))
            return f"[firstrun] Completed at {data.get('completed_at', '?')}."
        except Exception:
            return "[firstrun] Marked complete (details unreadable)."

    @safe
    def cmd_run(self, arg=""):
        """Show the checklist and mark it complete"""
        self._marker.write_text(json.dumps({"completed_at": time.strftime("%Y-%m-%d %H:%M:%S")}, indent=2),
                                encoding="utf-8")
        return f"[firstrun] {_CHECKLIST}\n\nMarked complete — re-run any step anytime, this just tracks that you've seen the list."

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
