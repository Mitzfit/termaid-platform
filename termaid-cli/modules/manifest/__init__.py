"""Manifest Module — Verify module command manifests vs docstrings.

Every module's docstring documents a "Commands (N):" list like:
    /modname foo <arg>     Description
This module reads that documented list, diffs it against what the module
ACTUALLY registers at runtime (by importing + instantiating it standalone,
same technique /qa uses), and flags any mismatch. This is exactly the check
that caught the learner.explain / netscan.explain dead-command bug during
manual review — now it's a runnable command instead of something you have to
remember to do by hand.

Commands (~6):
  /manifest check <module>      Diff docs vs registered commands for one module
  /manifest check-all              Same, across every module
  /manifest explain                  How this module works
"""

import importlib
import inspect
import re
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class ManifestModule(Module):
    name = "manifest"
    version = "1.0.0"
    description = "Verify module command manifests vs docstrings"
    author = "termaid"

    def on_load(self):
        for cmd in ["check", "check-all", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        self._modules_dir = Path(__file__).resolve().parent.parent

    def _discover(self) -> list[str]:
        if not self._modules_dir.is_dir():
            return []
        return sorted(
            e.name for e in self._modules_dir.iterdir()
            if e.is_dir() and not e.name.startswith(("_", ".")) and (e / "__init__.py").exists()
        )

    def _documented_commands(self, text: str) -> set[str]:
        """Parse '/modname cmd-name ...  description' lines from the docstring."""
        doc_match = re.match(r'^"""(.*?)"""', text, re.S)
        if not doc_match:
            return set()
        found = set()
        # A real command-table row looks like "/mod cmd [<arg>]   description" or
        # "/mod cmd" at end of line — the multi-space gap (or EOL) before the
        # description is what distinguishes a table row from an ordinary sentence
        # like "...same source /markets uses)", which continues with a single space.
        row_re = re.compile(r"^\s*/\S+\s+([\w-]+)(?:\s+[<\[][^>\]]*[>\]])*(?:\s{2,}\S|\s*$)")
        for line in doc_match.group(1).splitlines():
            m = row_re.match(line)
            if m:
                found.add(m.group(1))
        return found

    def _registered_commands(self, folder: str) -> tuple[set[str], str]:
        """Import + instantiate standalone (no AI, no engine) and read _commands."""
        try:
            mod = importlib.import_module(f"modules.{folder}")
            cls = None
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, Module) and obj is not Module and obj.__module__ == mod.__name__:
                    cls = obj
                    break
            if cls is None:
                return set(), "no Module subclass found"
            instance = cls()
            instance.on_load()
            return set(instance._commands.keys()), ""
        except Exception as e:
            return set(), f"{type(e).__name__}: {e}"

    def _check_one(self, folder: str) -> str:
        init_py = self._modules_dir / folder / "__init__.py"
        try:
            text = init_py.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[manifest] {folder}: could not read file: {e}"

        documented = self._documented_commands(text)
        registered, err = self._registered_commands(folder)
        if err:
            return f"[manifest] {folder}: FAILED to instantiate — {err}"

        undocumented = registered - documented  # registered but not in the docstring table
        unregistered = documented - registered  # documented but not actually registered (the real bug class)

        if not undocumented and not unregistered:
            return f"[manifest] {folder}: OK ({len(registered)} command(s), docs match)"

        lines = [f"[manifest] {folder}: MISMATCH"]
        if unregistered:
            lines.append(f"  documented but NOT registered (dead in docs, or truly broken): {sorted(unregistered)}")
        if undocumented:
            lines.append(f"  registered but not listed in the docstring table: {sorted(undocumented)}")
        return "\n".join(lines)

    @safe
    def cmd_check(self, arg=""):
        """Diff docs vs registered commands for one module"""
        folder = (arg or "").strip()
        if not folder:
            return "[manifest] Usage: /manifest check <module-folder-name>"
        if folder not in self._discover():
            return f"[manifest] No module folder named '{folder}'"
        return self._check_one(folder)

    @safe
    def cmd_check_all(self, arg=""):
        """Same, across every module"""
        folders = self._discover()
        results = [self._check_one(f) for f in folders]
        mismatches = [r for r in results if "MISMATCH" in r or "FAILED" in r]
        header = f"[manifest] Checked {len(folders)} module(s): {len(folders) - len(mismatches)} OK, {len(mismatches)} with issues"
        if not mismatches:
            return header
        return header + "\n\n" + "\n".join(mismatches)

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
