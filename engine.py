"""
engine.py — Headless wrapper around TermAId's existing module system,
now policy-aware.

Loads modules ONCE at startup, but only the ones the deployment policy permits
(see policy.py). Each command stays a simple `handler(arg: str) -> str`, so the
web layer changes nothing inside your `termaid/` package or `modules/`.

Proven against the real package: 120 modules discovered, 1948 commands.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from .policy import allowed_modules, AI_MODULES, SAFE_MODULES, SYSTEM_MODULES, DANGEROUS_MODULES


class Engine:
    def __init__(
        self,
        termaid_root: str | Path,
        mode: str = "server",
        ai_provider: Optional[str] = None,
        extra_allow: Optional[set[str]] = None,
        extra_deny: Optional[set[str]] = None,
    ):
        self.root = Path(termaid_root).resolve()
        self.modules_dir = self.root / "modules"
        self.mode = mode
        self.ai_provider = ai_provider
        self.extra_allow = extra_allow or set()
        self.extra_deny = extra_deny or set()

        self._cmds: dict = {}      # "mod.cmd" -> (module_instance, handler)
        self._native: dict = {}    # "mod.cmd" -> (module_name, handler(arg)->str)
        self._meta: dict = {}      # module name -> {version, description, commands, category}
        self._blocked: dict = {}   # module name -> reason
        self._ai = None

        for p in (str(self.root), str(self.modules_dir)):
            if p not in sys.path:
                sys.path.insert(0, p)

    # ------------------------------------------------------------------ #
    def _category(self, name: str) -> str:
        if name in DANGEROUS_MODULES:
            return "dangerous"
        if name in SYSTEM_MODULES:
            return "system"
        if name in AI_MODULES:
            return "ai"
        if name in SAFE_MODULES:
            return "safe"
        return "uncategorised"

    def _build_ai(self):
        if not self.ai_provider:
            return None
        try:
            from termaid.providers import get_provider  # type: ignore
            return get_provider(self.ai_provider)
        except Exception as e:  # pragma: no cover
            print(f"[engine] AI provider '{self.ai_provider}' unavailable: {e}")
            return None

    def load_all(self) -> dict:
        from termaid.extensions import ModuleManager  # type: ignore
        import termaid.extensions  # noqa: F401

        self._ai = self._build_ai()
        mm = ModuleManager(self.modules_dir)
        discovered = mm.discover()

        permitted, blocked = allowed_modules(
            discovered, self.mode, self.extra_allow, self.extra_deny
        )
        self._blocked = blocked

        ok, failed = [], []
        for name in sorted(permitted):
            info = mm.load(name, ai=self._ai)
            if info.enabled:
                ok.append(name)
                self._meta[info.name] = {
                    "version": info.version,
                    "description": info.description,
                    "commands": info.commands,
                    "category": self._category(name),
                }
            else:
                failed.append({"name": name, "error": info.error[:200]})

        self._cmds = mm.get_all_commands()
        self._mm = mm
        return {
            "mode": self.mode,
            "discovered": len(discovered),
            "loaded": len(ok),
            "blocked": len(blocked),
            "failed": len(failed),
            "commands": len(self._cmds),
            "failures": failed,
        }

    # ------------------------------------------------------------------ #
    def register_native(self, name: str, handler, *, module: str, description: str = "") -> None:
        """Register a non-Python-module command (e.g. Rust-backed).
        `handler` has the same shape as module commands: (arg: str) -> str."""
        self._native[name] = (module, handler)
        self._meta.setdefault(module, {
            "version": "native", "description": description,
            "commands": [], "category": "native",
        })
        sub = name.split(".", 1)[1] if "." in name else name
        if sub not in self._meta[module]["commands"]:
            self._meta[module]["commands"].append(sub)

    def commands(self) -> list[str]:
        return sorted(set(self._cmds) | set(self._native))

    def modules(self) -> dict:
        return self._meta

    def blocked(self) -> dict:
        return self._blocked

    def has_ai(self) -> bool:
        return self._ai is not None

    def execute(self, line: str) -> dict:
        start = time.perf_counter()
        line = (line or "").strip().lstrip("/")
        if not line:
            return {"ok": False, "output": "empty command", "ms": 0.0}

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # Native (Rust-backed) commands take precedence and share the str shape.
        nat = self._native.get(cmd)
        if nat is not None:
            mod_name, handler = nat
            try:
                out = handler(arg)
                return {"ok": True, "module": mod_name, "command": cmd,
                        "output": str(out) if out is not None else "",
                        "ms": round((time.perf_counter() - start) * 1000, 2)}
            except Exception as e:
                return {"ok": False, "module": mod_name, "command": cmd,
                        "output": f"error: {e}",
                        "ms": round((time.perf_counter() - start) * 1000, 2)}

        entry = self._cmds.get(cmd)
        if entry is None:
            ms = round((time.perf_counter() - start) * 1000, 2)
            # Helpful: was it blocked by policy rather than nonexistent?
            mod_name = cmd.split(".", 1)[0]
            if mod_name in self._blocked:
                return {"ok": False, "command": cmd,
                        "output": f"'{mod_name}' is disabled here: {self._blocked[mod_name]}",
                        "ms": ms}
            return {"ok": False, "command": cmd,
                    "output": f"unknown command: {cmd}", "ms": ms}

        module, handler = entry
        try:
            out = handler(arg)
            return {
                "ok": True, "module": module.name, "command": cmd,
                "output": str(out) if out is not None else "",
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }
        except Exception as e:
            return {
                "ok": False, "module": module.name, "command": cmd,
                "output": f"error: {e}",
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }
