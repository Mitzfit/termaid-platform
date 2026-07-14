"""Improve Module — AI-assisted source code review (review only, never applies).

Reads a file from disk and asks the AI to review it. This module NEVER
writes back to the file — it only returns text. Applying any suggested
change is a deliberate, separate step you take yourself (e.g. with your
editor), by design: no module has a safe, reviewed path to silently mutate
files on disk.

Commands (~7):
  /improve review <path>       Ask the AI to review a file, output suggestions only
  /improve security <path>       Ask the AI to review a file specifically for security issues
  /improve diff-only <path>       Ask the AI to propose ONLY a minimal unified diff (still just text)
  /improve history                 Recent reviews (this session, paths only)
  /improve explain                   How this module works
"""

from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_MAX_BYTES = 50_000


class ImproveModule(Module):
    name = "improve"
    version = "1.0.0"
    description = "AI-assisted source code improvement (review + apply with consent)"
    author = "termaid"

    def on_load(self):
        for cmd in ["review", "security", "diff-only", "history", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        self._history: list[str] = []

    def _read_file(self, path_s: str) -> tuple[str, str]:
        """Returns (content, error). error is '' on success."""
        p = Path(path_s).expanduser()
        if not p.exists():
            return "", f"File not found: {p}"
        if not p.is_file():
            return "", f"Not a file: {p}"
        if p.stat().st_size > _MAX_BYTES:
            return "", f"File too large ({p.stat().st_size} bytes, limit {_MAX_BYTES})"
        try:
            return p.read_text(encoding="utf-8", errors="replace"), ""
        except Exception as e:
            return "", f"Read failed: {e}"

    @safe
    def cmd_review(self, arg=""):
        """Ask the AI to review a file, output suggestions only (never applied)"""
        if not self.ai:
            return "[improve] No AI provider configured."
        path_s = (arg or "").strip()
        if not path_s:
            return "[improve] Usage: /improve review <path>"
        content, err = self._read_file(path_s)
        if err:
            return f"[improve] {err}"
        try:
            result = self.ask_ai(
                content,
                system=("Review this source file. Point out real bugs, correctness issues, "
                        "and clear simplification opportunities. Skip style nitpicks. Be "
                        "specific (line-level where possible). If it looks fine, say so."),
            )
        except Exception as e:
            return f"[improve] AI error: {e}"
        self._history.append(path_s)
        return f"[improve] Review of {path_s} (suggestions only, nothing applied):\n\n{result}"

    @safe
    def cmd_security(self, arg=""):
        """Ask the AI to review a file specifically for security issues"""
        if not self.ai:
            return "[improve] No AI provider configured."
        path_s = (arg or "").strip()
        if not path_s:
            return "[improve] Usage: /improve security <path>"
        content, err = self._read_file(path_s)
        if err:
            return f"[improve] {err}"
        try:
            result = self.ask_ai(
                content,
                system=("Review this source file for security issues ONLY: injection, "
                        "auth/authz gaps, secret handling, unsafe deserialization, path "
                        "traversal, SSRF. Cite the specific line/pattern for each finding."),
            )
        except Exception as e:
            return f"[improve] AI error: {e}"
        self._history.append(path_s)
        return f"[improve] Security review of {path_s}:\n\n{result}"

    @safe
    def cmd_diff_only(self, arg=""):
        """Ask the AI to propose ONLY a minimal unified diff (still just text, not applied)"""
        if not self.ai:
            return "[improve] No AI provider configured."
        path_s = (arg or "").strip()
        if not path_s:
            return "[improve] Usage: /improve diff-only <path>"
        content, err = self._read_file(path_s)
        if err:
            return f"[improve] {err}"
        try:
            result = self.ask_ai(
                content,
                system=("Propose the SMALLEST fix for the single most important issue in this "
                        "file, as a unified diff only (--- / +++ / @@ hunks). No prose."),
            )
        except Exception as e:
            return f"[improve] AI error: {e}"
        self._history.append(path_s)
        return f"[improve] Proposed diff for {path_s} (not applied — copy/apply yourself):\n\n{result}"

    @safe
    def cmd_history(self, arg=""):
        """Recent reviews (this session, paths only)"""
        if not self._history:
            return "[improve] No reviews this session."
        return "[improve] Reviewed this session:\n" + "\n".join(f"  {p}" for p in self._history[-20:])

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
