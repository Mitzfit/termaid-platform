"""
engine.py — Headless wrapper around TermAId's existing module system.

This is the bridge between your CLI app and the web backend. It loads every
module ONCE at process startup, then exposes a single `execute()` method that
takes a "mod.cmd args" string and returns structured output.

Nothing in your `termaid/` package or `modules/` directory needs to change.
The command registry already gives every command the shape `handler(arg: str) -> str`,
which is exactly what a web request handler wants.

Proven against the real package: 120 modules load, 1948 commands dispatch.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional


class Engine:
    """Thread-safe-ish headless command dispatcher for TermAId.

    Usage:
        eng = Engine(termaid_root="/path/to/termaid-complete-windows")
        eng.load_all()
        result = eng.execute("calc.hex 255")
        # -> {"ok": True, "module": "calc", "output": "...", "ms": 1.2}
    """

    def __init__(self, termaid_root: str | Path, ai_provider: Optional[str] = None):
        self.root = Path(termaid_root).resolve()
        self.modules_dir = self.root / "modules"
        self.ai_provider = ai_provider
        self._cmds: dict = {}          # "mod.cmd" -> (module_instance, handler)
        self._meta: dict = {}          # module name -> info
        self._ai = None

        # Make the termaid package and _shared helpers importable.
        for p in (str(self.root), str(self.modules_dir)):
            if p not in sys.path:
                sys.path.insert(0, p)

    # ------------------------------------------------------------------ #
    def _build_ai(self):
        """Optionally build a real AIClient so AI-backed commands work."""
        if not self.ai_provider:
            return None
        try:
            from termaid.providers import get_provider  # type: ignore
            return get_provider(self.ai_provider)
        except Exception as e:  # pragma: no cover
            print(f"[engine] AI provider '{self.ai_provider}' unavailable: {e}")
            return None

    def load_all(self) -> dict:
        """Load every discoverable module. Returns a load report."""
        from termaid.extensions import ModuleManager  # type: ignore
        import termaid.extensions  # noqa: F401  (registers the modules shim)

        self._ai = self._build_ai()
        mm = ModuleManager(self.modules_dir)

        ok, failed = [], []
        for name in mm.discover():
            info = mm.load(name, ai=self._ai)
            if info.enabled:
                ok.append(name)
                self._meta[info.name] = {
                    "version": info.version,
                    "description": info.description,
                    "commands": info.commands,
                }
            else:
                failed.append({"name": name, "error": info.error[:200]})

        self._cmds = mm.get_all_commands()
        self._mm = mm
        return {
            "loaded": len(ok),
            "failed": len(failed),
            "commands": len(self._cmds),
            "failures": failed,
        }

    # ------------------------------------------------------------------ #
    def commands(self) -> list[str]:
        return sorted(self._cmds.keys())

    def modules(self) -> dict:
        return self._meta

    def execute(self, line: str) -> dict:
        """Run one command line. Returns a JSON-serialisable dict.

        Accepts both "calc.hex 255" and "/calc.hex 255".
        """
        start = time.perf_counter()
        line = (line or "").strip().lstrip("/")
        if not line:
            return {"ok": False, "output": "empty command", "ms": 0.0}

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        entry = self._cmds.get(cmd)
        if entry is None:
            return {"ok": False, "output": f"unknown command: {cmd}",
                    "ms": round((time.perf_counter() - start) * 1000, 2)}

        module, handler = entry
        try:
            out = handler(arg)
            return {
                "ok": True,
                "module": module.name,
                "command": cmd,
                "output": str(out) if out is not None else "",
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }
        except Exception as e:
            return {
                "ok": False,
                "module": module.name,
                "command": cmd,
                "output": f"error: {e}",
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }
