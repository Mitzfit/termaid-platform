"""Errors Module — Error log inspection, analysis, and fix suggestions.

Paste an error/traceback and this either matches it against a small built-in
table of common Python exceptions (works with no AI configured), or — if an
AI provider is set — asks for a specific diagnosis. It doesn't read any log
file automatically; there's no single canonical "the log" in this deployment
(the platform backend, the CLI, and each module all handle their own).

Commands (~7):
  /errors analyze <error text>     Diagnose an error (AI if configured, pattern match otherwise)
  /errors common                     List common error patterns this module recognizes offline
  /errors history                       Recent analyses (this session)
  /errors explain                         How this module works
"""

import re
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_KNOWN_PATTERNS = [
    (re.compile(r"ModuleNotFoundError: No module named '([\w.]+)'"),
     lambda m: f"Package '{m.group(1)}' isn't installed. Try: pip install {m.group(1).split('.')[0]}"),
    (re.compile(r"IndentationError"),
     lambda m: "Mixed tabs/spaces or a missing colon/indent — check the line just above the one reported."),
    (re.compile(r"ConnectionRefusedError|Connection refused"),
     lambda m: "Nothing is listening on that host:port — is the target service actually running?"),
    (re.compile(r"PermissionError|Permission denied"),
     lambda m: "The process doesn't have rights to that file/port. Check ownership/permissions, or elevate if that's genuinely required."),
    (re.compile(r"IndexError: list index out of range"),
     lambda m: "Code indexed past the end of a list — likely an empty-input edge case wasn't handled."),
    (re.compile(r"KeyError: '?([\w.-]+)'?"),
     lambda m: f"Dict lookup for key '{m.group(1)}' failed — it's either missing or misspelled at that point."),
    (re.compile(r"AttributeError: '(\w+)' object has no attribute '(\w+)'"),
     lambda m: f"A {m.group(1)} instance doesn't have '{m.group(2)}' — likely a typo, or the object is the wrong type here."),
    (re.compile(r"TimeoutError|timed out"),
     lambda m: "A network call exceeded its timeout — check connectivity, or the timeout may just be too short for this operation."),
    (re.compile(r"json\.decoder\.JSONDecodeError|Expecting value"),
     lambda m: "The response wasn't valid JSON — likely an HTML error page or empty body where JSON was expected."),
]


class ErrorsModule(Module):
    name = "errors"
    version = "1.0.0"
    description = "Error log inspection, analysis, and fix suggestions"
    author = "termaid"

    def on_load(self):
        for cmd in ["analyze", "common", "history", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        self._history: list[str] = []

    @safe
    def cmd_analyze(self, arg=""):
        """Diagnose an error (AI if configured, pattern match otherwise)"""
        text = arg or ""
        if not text:
            return "[errors] Usage: /errors analyze <error text or traceback>"

        matches = []
        for pattern, advice in _KNOWN_PATTERNS:
            m = pattern.search(text)
            if m:
                matches.append(advice(m))

        if self.ai:
            try:
                ai_result = self.ask_ai(
                    text,
                    system=("Diagnose this error/traceback. State the root cause in 1-2 "
                            "sentences, then the smallest fix. If genuinely ambiguous, say so."),
                )
            except Exception as e:
                ai_result = f"(AI error: {e})"
            self._history.append(text[:80])
            lines = [f"[errors] AI diagnosis:\n{ai_result}"]
            if matches:
                lines.append("\n[errors] Also matched known pattern(s):")
                lines += [f"  - {m}" for m in matches]
            return "\n".join(lines)

        self._history.append(text[:80])
        if matches:
            return "[errors] Matched known pattern(s) (no AI configured):\n" + "\n".join(f"  - {m}" for m in matches)
        return ("[errors] No AI configured and no built-in pattern matched. "
                "See /errors common for what this module recognizes offline.")

    @safe
    def cmd_common(self, arg=""):
        """List common error patterns this module recognizes offline"""
        lines = ["[errors] Recognized offline (no AI needed):"]
        for pattern, _ in _KNOWN_PATTERNS:
            lines.append(f"  {pattern.pattern}")
        return "\n".join(lines)

    @safe
    def cmd_history(self, arg=""):
        """Recent analyses (this session)"""
        if not self._history:
            return "[errors] No analyses this session."
        return "[errors] Analyzed this session:\n" + "\n".join(f"  {h}" for h in self._history[-20:])

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
