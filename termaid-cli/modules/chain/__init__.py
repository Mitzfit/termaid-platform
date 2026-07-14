"""Chain Module — Sequence multiple TermAId commands.

A module has no handle back into the command dispatcher (only the engine
that loaded it does), so /chain can't actually re-execute the steps it
stores. It manages named sequences and hands you the ordered list to run —
real execute-a-chain support would need to live in the engine/REPL layer,
which is worth doing later if this proves useful.

Commands (~10):
  /chain create <name>              Start a new (empty) chain
  /chain add-step <name> <command>   Append a step
  /chain remove-step <name> <n>       Remove step n (1-based)
  /chain list                          List all chains
  /chain show <name>                   Show a chain's steps in order
  /chain delete <name>                  Delete a chain
  /chain run <name>                     Print the steps to run, in order (not executed)
  /chain export                          Export all chains to JSON
  /chain import <path>                   Import chains from JSON
  /chain explain                          How this module works
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


class ChainModule(Module):
    name = "chain"
    version = "1.0.0"
    description = "Sequence multiple TermAId commands"
    author = "termaid"

    def on_load(self):
        for cmd in ["create", "add-step", "remove-step", "list", "show",
                    "delete", "run", "export", "import", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "chain"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "chains.json"

    def _load(self) -> dict:
        if self._file.exists():
            try:
                return json.loads(self._file.read_text())
            except Exception:
                pass
        return {}

    def _save(self, chains: dict) -> None:
        self._file.write_text(json.dumps(chains, indent=2))

    @safe
    def cmd_create(self, arg=""):
        """Start a new (empty) chain"""
        name = (arg or "").strip()
        if not name:
            return "[chain] Usage: /chain create <name>"
        chains = self._load()
        if name in chains:
            return f"[chain] '{name}' already exists. /chain show {name}"
        chains[name] = []
        self._save(chains)
        return f"[chain] Created empty chain '{name}'. /chain add-step {name} <command>"

    @safe
    def cmd_add_step(self, arg=""):
        """Append a step: /chain add-step <name> <command>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[chain] Usage: /chain add-step <name> <command>"
        name, command = parts
        chains = self._load()
        if name not in chains:
            return f"[chain] No chain named '{name}'. /chain create {name}"
        chains[name].append(command)
        self._save(chains)
        return f"[chain] '{name}' step {len(chains[name])}: {command}"

    @safe
    def cmd_remove_step(self, arg=""):
        """Remove step n (1-based): /chain remove-step <name> <n>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[chain] Usage: /chain remove-step <name> <step-number>"
        name, n_s = parts
        chains = self._load()
        if name not in chains:
            return f"[chain] No chain named '{name}'"
        try:
            n = int(n_s)
        except Exception:
            return "[chain] Step number must be an integer"
        steps = chains[name]
        if not (1 <= n <= len(steps)):
            return f"[chain] '{name}' has no step {n}"
        removed = steps.pop(n - 1)
        self._save(chains)
        return f"[chain] Removed step {n} from '{name}': {removed}"

    @safe
    def cmd_list(self, arg=""):
        """List all chains"""
        chains = self._load()
        if not chains:
            return "[chain] No chains yet. /chain create <name>"
        lines = [f"[chain] {len(chains)} chain(s):"]
        for name, steps in sorted(chains.items()):
            lines.append(f"  {name:<15s} ({len(steps)} step(s))")
        return "\n".join(lines)

    @safe
    def cmd_show(self, arg=""):
        """Show a chain's steps in order"""
        name = (arg or "").strip()
        if not name:
            return "[chain] Usage: /chain show <name>"
        chains = self._load()
        if name not in chains:
            return f"[chain] No chain named '{name}'"
        steps = chains[name]
        if not steps:
            return f"[chain] '{name}' has no steps yet."
        lines = [f"[chain] '{name}':"]
        for i, s in enumerate(steps, 1):
            lines.append(f"  {i}. {s}")
        return "\n".join(lines)

    @safe
    def cmd_delete(self, arg=""):
        """Delete a chain"""
        name = (arg or "").strip()
        if not name:
            return "[chain] Usage: /chain delete <name>"
        chains = self._load()
        if name not in chains:
            return f"[chain] No chain named '{name}'"
        del chains[name]
        self._save(chains)
        return f"[chain] Deleted '{name}'"

    @safe
    def cmd_run(self, arg=""):
        """Print the steps to run, in order (this module cannot execute them itself)"""
        name = (arg or "").strip()
        if not name:
            return "[chain] Usage: /chain run <name>"
        chains = self._load()
        if name not in chains:
            return f"[chain] No chain named '{name}'"
        steps = chains[name]
        if not steps:
            return f"[chain] '{name}' has no steps yet."
        lines = [f"[chain] Run these {len(steps)} step(s) in order (not auto-executed):"]
        for i, s in enumerate(steps, 1):
            lines.append(f"  {i}. {s}")
        return "\n".join(lines)

    @safe
    def cmd_export(self, arg=""):
        """Export all chains to JSON"""
        path = (arg or "").strip() or str(self._dir / "chains-export.json")
        Path(path).expanduser().write_text(json.dumps(self._load(), indent=2))
        return f"[chain] Exported to {path}"

    @safe
    def cmd_import(self, arg=""):
        """Import chains from JSON"""
        path = (arg or "").strip()
        if not path:
            return "[chain] Usage: /chain import <path>"
        try:
            incoming = json.loads(Path(path).expanduser().read_text())
        except Exception as e:
            return f"[chain] Cannot read: {e}"
        if not isinstance(incoming, dict):
            return "[chain] File must contain a JSON object of name -> [steps]"
        chains = self._load()
        chains.update(incoming)
        self._save(chains)
        return f"[chain] Imported {len(incoming)} chain(s)"

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
