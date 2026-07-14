"""
extensions/__init__.py — ModuleManager: discovers, loads, and dispatches the
CLI module system that backend/engine.py wraps.

Contract (already assumed by engine.py, bridge.py, and every modules/<name>/
__init__.py file):
  - discover() -> list[str]                      folder names under modules/
  - load(name, ai=None) -> ModuleInfo             import + instantiate + on_load()
  - get_all_commands() -> {"mod.cmd": (module, handler)}
  - list_info() -> list[ModuleInfo]

The module identifier used for dispatch/policy/meta is always the FOLDER name
(e.g. "netscan", "learner"), even where a module's class-level `name` differs
(e.g. netscan's class is internally `net`) — ModuleManager overrides
`instance.name` to the folder name at load time so policy.py, engine.py, and
the "mod.cmd" dispatch key stay consistent with each other.

Author: Misfit
"""
from __future__ import annotations

import importlib
import inspect
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .modules import Module


@dataclass
class ModuleInfo:
    """What the engine/catalog/API need to know about one loaded (or failed) module."""

    name: str
    version: str = ""
    description: str = ""
    commands: list[str] = field(default_factory=list)
    enabled: bool = False
    error: str = ""


class ModuleManager:
    """Discovers and loads modules from a `modules/` directory, folder-by-folder."""

    def __init__(self, modules_dir: str | Path):
        self.modules_dir = Path(modules_dir)
        self._loaded: dict[str, Module] = {}
        self._infos: dict[str, ModuleInfo] = {}

    def discover(self) -> list[str]:
        """Return every subfolder of modules_dir that looks like a module."""
        if not self.modules_dir.is_dir():
            return []
        names = []
        for entry in sorted(self.modules_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue
            if (entry / "__init__.py").exists():
                names.append(entry.name)
        return names

    def _find_module_class(self, mod) -> type[Module] | None:
        """Find the single Module subclass defined IN this file (not imported)."""
        for _, obj in inspect.getmembers(mod, inspect.isclass):
            if issubclass(obj, Module) and obj is not Module and obj.__module__ == mod.__name__:
                return obj
        return None

    def load(self, name: str, ai=None) -> ModuleInfo:
        """Import modules.<name>, instantiate its Module subclass, call on_load().

        Never raises: any failure is captured into ModuleInfo.error so one bad
        module can't take down the whole engine at startup.
        """
        try:
            mod = importlib.import_module(f"modules.{name}")
            cls = self._find_module_class(mod)
            if cls is None:
                raise ImportError(f"no Module subclass found in modules.{name}")

            instance = cls()
            instance.name = name  # canonicalize to the folder name (see module docstring)
            instance.ai = ai
            instance.on_load()

            info = ModuleInfo(
                name=name,
                version=getattr(instance, "version", "0.0.0"),
                description=getattr(instance, "description", ""),
                commands=sorted(instance._commands.keys()),
                enabled=True,
            )
            self._loaded[name] = instance
        except Exception as e:  # noqa: BLE001 — startup must survive a broken module
            info = ModuleInfo(
                name=name,
                enabled=False,
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
            )
        self._infos[name] = info
        return info

    def get_all_commands(self) -> dict[str, tuple[Module, Callable[[str], str]]]:
        """{'mod.cmd': (module_instance, handler)} across every loaded module."""
        out: dict[str, tuple[Module, Callable[[str], str]]] = {}
        for name, instance in self._loaded.items():
            for cmd, handler in instance._commands.items():
                out[f"{name}.{cmd}"] = (instance, handler)
        return out

    def list_info(self) -> list[ModuleInfo]:
        return list(self._infos.values())
