"""QA Module — Universal tester across all modules.

/qa selftest dynamically imports every module in modules/ (the same
discovery approach /catalog and /smart use), instantiates it standalone, runs
its on_load() and cmd_explain(), and reports pass/fail — a real cross-module
smoke test, not just a static file scan. A module can freely import another
module's class for this (they're just Python modules in the same package);
it just never gets AI-wired or registered by that temporary instance.

Commands (~6):
  /qa selftest             Import + instantiate + on_load() + explain() every module
  /qa check <mod>            Self-test a single module by folder name
  /qa coverage                 What fraction of modules pass selftest
  /qa stats                     Command/module counts (delegates to a live scan)
  /qa explain                    How this module works
"""

import importlib
import inspect
import traceback
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class QAModule(Module):
    name = "qa"
    version = "1.0.0"
    description = "Universal tester + configurator + improver across all modules"
    author = "termaid"

    def on_load(self):
        for cmd in ["selftest", "check", "coverage", "stats", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        self._modules_dir = Path(__file__).resolve().parent.parent

    def _discover(self) -> list[str]:
        if not self._modules_dir.is_dir():
            return []
        return sorted(
            e.name for e in self._modules_dir.iterdir()
            if e.is_dir() and not e.name.startswith(("_", ".")) and (e / "__init__.py").exists()
        )

    def _test_one(self, folder: str) -> tuple[bool, str]:
        """Import, instantiate, on_load(), cmd_explain() a module standalone.
        Returns (ok, message)."""
        try:
            mod = importlib.import_module(f"modules.{folder}")
            cls = None
            for _, obj in inspect.getmembers(mod, inspect.isclass):
                if issubclass(obj, Module) and obj is not Module and obj.__module__ == mod.__name__:
                    cls = obj
                    break
            if cls is None:
                return False, "no Module subclass found"
            instance = cls()
            instance.name = folder
            instance.on_load()
            n_commands = len(instance._commands)
            explain_out = instance.cmd_explain("") if "explain" in instance._commands else "(no explain)"
            return True, f"{n_commands} command(s) registered; explain() OK ({len(explain_out)} chars)"
        except Exception as e:
            return False, f"{type(e).__name__}: {e}"

    @safe
    def cmd_selftest(self, arg=""):
        """Import + instantiate + on_load() + explain() every module"""
        folders = self._discover()
        results = [(f, *self._test_one(f)) for f in folders]
        passed = sum(1 for _, ok, _ in results if ok)
        lines = [f"[qa] Self-test: {passed}/{len(results)} module(s) passed"]
        for folder, ok, msg in results:
            lines.append(f"  {'PASS' if ok else 'FAIL'}  {folder:<12s} {msg}")
        return "\n".join(lines)

    @safe
    def cmd_check(self, arg=""):
        """Self-test a single module by folder name"""
        folder = (arg or "").strip()
        if not folder:
            return "[qa] Usage: /qa check <module-folder-name>"
        if folder not in self._discover():
            return f"[qa] No module folder named '{folder}'"
        ok, msg = self._test_one(folder)
        return f"[qa] {folder}: {'PASS' if ok else 'FAIL'} — {msg}"

    @safe
    def cmd_coverage(self, arg=""):
        """What fraction of modules pass selftest"""
        folders = self._discover()
        results = [self._test_one(f) for f in folders]
        passed = sum(1 for ok, _ in results if ok)
        pct = (passed / len(results) * 100) if results else 0.0
        return f"[qa] {passed}/{len(results)} module(s) pass self-test ({pct:.0f}%)"

    @safe
    def cmd_stats(self, arg=""):
        """Command/module counts (live scan, same method /catalog uses)"""
        folders = self._discover()
        return f"[qa] {len(folders)} module folder(s) discovered under {self._modules_dir}"

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
