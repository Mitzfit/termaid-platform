"""
bridge.py — the seam between TermAId's existing engine and the web layer.

TermAId already has everything a backend needs:
  - ModuleManager loads the 121 modules from /modules
  - get_all_commands() -> {"mod.cmd": (module, handler)}
  - every handler(arg_string) -> str
  - AIClient.chat(message) -> ChatResponse for non-slash input

This module wires that engine up *once* and exposes three plain
functions the API can call. No module is rewritten; we drive the same
code the REPL drives.
"""
from __future__ import annotations

import sys
import io
import contextlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# --- Locate the TermAId project root -----------------------------------------
# Layout:  <root>/termaid/  and  <root>/modules/  are siblings.
# Override with the TERMAID_ROOT env var if you move things around.
import os

_ROOT = Path(os.environ.get("TERMAID_ROOT", "")) if os.environ.get("TERMAID_ROOT") else None
if _ROOT is None:
    # Walk up from this file looking for a dir that has both termaid/ and modules/
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        if (parent / "termaid").is_dir() and (parent / "modules").is_dir():
            _ROOT = parent
            break
if _ROOT is None:
    raise RuntimeError(
        "Could not find the TermAId project root (a folder containing both "
        "'termaid/' and 'modules/'). Set TERMAID_ROOT to point at it."
    )

ROOT = _ROOT
MODULES_DIR = ROOT / "modules"
sys.path.insert(0, str(ROOT))

from termaid.extensions import ModuleManager  # noqa: E402

try:
    from termaid.providers import get_provider  # noqa: E402
except Exception:  # pragma: no cover - providers optional at boot
    get_provider = None


@dataclass
class ExecResult:
    ok: bool
    output: str
    kind: str  # "command" | "chat" | "error"
    command: str = ""


class Engine:
    """Loads modules once and dispatches commands / chat."""

    def __init__(self, ai_provider: str = "gemini-flash"):
        self.mm = ModuleManager(MODULES_DIR)
        self.ai_provider = ai_provider
        self._ai = None
        self.load_errors: dict[str, str] = {}
        self._load_all()

    # -- module loading -------------------------------------------------------
    def _load_all(self) -> None:
        for name in self.mm.discover():
            info = self.mm.load(name, ai=None)
            if info.error:
                # ModuleManager already swallowed the traceback into .error
                self.load_errors[name] = info.error.splitlines()[0][:200]

    def commands(self) -> dict:
        """{'mod.cmd': (module, handler)} — the live dispatch table."""
        return self.mm.get_all_commands()

    def catalog(self) -> list[dict]:
        """Serializable list of every command for the frontend palette."""
        out = []
        for full, (mod, _handler) in sorted(self.commands().items()):
            modname, _, sub = full.partition(".")
            out.append({
                "command": full,
                "module": modname,
                "sub": sub,
                "description": getattr(mod, "description", "") or "",
            })
        return out

    def modules_info(self) -> list[dict]:
        info = []
        for m in self.mm.list_info():
            info.append({
                "name": getattr(m, "display_label", m.name),
                "version": getattr(m, "version", ""),
                "enabled": getattr(m, "enabled", False),
                "commands": len(getattr(m, "commands", []) or []),
                "error": (m.error.splitlines()[0][:160] if getattr(m, "error", "") else ""),
            })
        return info

    # -- AI (non-slash input) -------------------------------------------------
    def _ai_client(self):
        if self._ai is None and get_provider is not None:
            try:
                self._ai = get_provider(self.ai_provider)
            except Exception:
                self._ai = False  # mark as unavailable
        return self._ai or None

    # -- dispatch -------------------------------------------------------------
    def execute(self, line: str) -> ExecResult:
        line = (line or "").strip()
        if not line:
            return ExecResult(True, "", "command")

        if not line.startswith("/"):
            return self._chat(line)

        # /mod.cmd arg...   OR   /mod cmd arg...
        parts = line[1:].split(maxsplit=1)
        head = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""
        cmds = self.commands()

        target = None
        if head in cmds:
            target = head
        elif "." not in head and arg:
            # rewrite "/mod sub rest" -> "mod.sub rest"
            sub_parts = arg.split(maxsplit=1)
            candidate = f"{head}.{sub_parts[0].lower()}"
            if candidate in cmds:
                target = candidate
                arg = sub_parts[1] if len(sub_parts) > 1 else ""

        if target is None:
            # list subcommands if the user typed a bare module name
            subs = sorted(c for c in cmds if c.startswith(head + "."))
            if subs:
                listing = "\n".join(f"  /{c}" for c in subs[:40])
                return ExecResult(True, f"[{head}] subcommands:\n{listing}", "command", head)
            return ExecResult(False, f"Unknown command: /{head}", "error", head)

        mod, handler = cmds[target]
        # Some modules print to stdout instead of returning; capture both.
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                result = handler(arg)
            captured = buf.getvalue()
            text = ""
            if result:
                text = str(result)
            if captured.strip():
                text = (text + "\n" + captured).strip() if text else captured.rstrip()
            return ExecResult(True, text, "command", target)
        except Exception as e:  # never let a module crash the request
            return ExecResult(False, f"Module error in /{target}: {e}", "error", target)

    def _chat(self, message: str) -> ExecResult:
        client = self._ai_client()
        if client is None:
            return ExecResult(
                False,
                "AI chat is unavailable: no provider key set. Export a key "
                "(e.g. GEMINI_API_KEY) or use a /command instead.",
                "error",
            )
        try:
            resp = client.chat(message)
            return ExecResult(True, getattr(resp, "text", str(resp)), "chat")
        except Exception as e:
            return ExecResult(False, f"AI error: {e}", "error")


# A single shared engine instance for the whole process.
_engine: Optional[Engine] = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine
