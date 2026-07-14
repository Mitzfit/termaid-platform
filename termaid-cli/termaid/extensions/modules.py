"""
extensions/modules.py — the Module base class every CLI module subclasses.

Owns the contract every modules/<name>/__init__.py file already relies on:
  - class attributes: name, version, description, author
  - self.register_command(cmd, handler) called from on_load()
  - self.on_load() overridden by each module to register its commands
  - self.ai / self.ask_ai(prompt, system="") for AI-backed modules
  - self._commands: dict[str, Callable[[str], str]]

Reconstructed to match how every existing module file already calls these
(they were written against this contract; this file makes that contract real).

Author: Misfit
"""
from __future__ import annotations

from typing import Callable


class Module:
    """Base class for every CLI module.

    Subclasses set class-level `name`/`version`/`description`/`author`, then
    override `on_load()` to register commands via `self.register_command`.
    """

    name: str = ""
    version: str = "0.0.0"
    description: str = ""
    author: str = "termaid"

    def __init__(self) -> None:
        self._commands: dict[str, Callable[[str], str]] = {}
        self.ai = None  # set by ModuleManager.load() when an AI provider is configured

    def register_command(self, cmd_name: str, handler: Callable[[str], str]) -> None:
        """Register `handler(arg: str) -> str` under `cmd_name` (no module prefix)."""
        self._commands[cmd_name] = handler

    def on_load(self) -> None:
        """Override: register commands and set up any module-local state."""
        return None

    def ask_ai(self, prompt: str, system: str = "") -> str:
        """Blocking AI call via the configured provider client.

        Raises RuntimeError if no AI provider is configured for this deployment
        so the failure surfaces as a normal command error rather than a crash.
        """
        if self.ai is None:
            raise RuntimeError(f"{self.name}: no AI provider configured")
        resp = self.ai.chat(prompt, system=system)
        return getattr(resp, "text", str(resp))
