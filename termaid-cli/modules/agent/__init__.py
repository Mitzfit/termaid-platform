"""Agent Module — AI middleman: auto-detect problems, propose fixes.

Give it an error message, a symptom description, or a log excerpt; it asks
the AI to diagnose and propose a fix. It never applies anything itself — no
module has a path back into the shell/filesystem beyond what it owns — it
only proposes text, which you review and act on yourself.

Commands (~9):
  /agent diagnose <text>      Diagnose a problem/error description
  /agent fix <text>            Propose a fix for a problem/error description
  /agent review <command>      Ask the AI to sanity-check a command before you run it
  /agent history                Recent diagnoses/fixes (this session)
  /agent clear-history          Clear the session history
  /agent confidence              Show the confidence note from the last response
  /agent explain                 How this module works
"""

from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class AgentModule(Module):
    name = "agent"
    version = "1.0.0"
    description = "AI middleman: auto-detect problems, propose fixes"
    author = "termaid"

    def on_load(self):
        for cmd in ["diagnose", "fix", "review", "history",
                    "clear-history", "confidence", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        self._history: list[dict] = []

    def _require_ai(self):
        if not self.ai:
            return ("[agent] No AI provider configured.\n"
                    "  Set AI_PROVIDER (and its API key) in .env, then restart.")
        return None

    @safe
    def cmd_diagnose(self, arg=""):
        """Diagnose a problem/error description"""
        err = self._require_ai()
        if err:
            return err
        text = arg or ""
        if not text:
            return "[agent] Usage: /agent diagnose <error text or symptom description>"
        try:
            result = self.ask_ai(
                text,
                system=("You are a diagnostic assistant. Given an error message or "
                        "symptom description, identify the MOST LIKELY root cause in "
                        "1-3 sentences. If genuinely uncertain, say so explicitly rather "
                        "than guessing confidently."),
            )
        except Exception as e:
            return f"[agent] AI error: {e}"
        self._history.append({"kind": "diagnose", "input": text, "output": result})
        return f"[agent] {result}"

    @safe
    def cmd_fix(self, arg=""):
        """Propose a fix for a problem/error description (never applied automatically)"""
        err = self._require_ai()
        if err:
            return err
        text = arg or ""
        if not text:
            return "[agent] Usage: /agent fix <error text or symptom description>"
        try:
            result = self.ask_ai(
                text,
                system=("You propose fixes for described problems. Give the smallest "
                        "concrete fix that addresses the root cause, as numbered steps. "
                        "Never claim you applied it — you only propose; the user decides."),
            )
        except Exception as e:
            return f"[agent] AI error: {e}"
        self._history.append({"kind": "fix", "input": text, "output": result})
        return f"[agent] Proposed fix (not applied):\n\n{result}"

    @safe
    def cmd_review(self, arg=""):
        """Ask the AI to sanity-check a command before you run it"""
        err = self._require_ai()
        if err:
            return err
        command = arg or ""
        if not command:
            return "[agent] Usage: /agent review <command to sanity-check>"
        try:
            result = self.ask_ai(
                command,
                system=("Review this shell/CLI command for anything risky or destructive "
                        "(deletion, overwrite, privilege escalation, irreversible network "
                        "actions). If it looks safe, say so plainly. If risky, say exactly "
                        "what could go wrong."),
            )
        except Exception as e:
            return f"[agent] AI error: {e}"
        self._history.append({"kind": "review", "input": command, "output": result})
        return f"[agent] {result}"

    @safe
    def cmd_history(self, arg=""):
        """Recent diagnoses/fixes (this session)"""
        if not self._history:
            return "[agent] No activity this session."
        lines = [f"[agent] {len(self._history)} entr{'y' if len(self._history) == 1 else 'ies'} this session:"]
        for h in self._history[-20:]:
            lines.append(f"  [{h['kind']}] {h['input'][:60]}")
        return "\n".join(lines)

    @safe
    def cmd_clear_history(self, arg=""):
        """Clear the session history"""
        n = len(self._history)
        self._history.clear()
        return f"[agent] Cleared {n} entr{'y' if n == 1 else 'ies'}."

    @safe
    def cmd_confidence(self, arg=""):
        """Show the confidence note from the last response"""
        if not self._history:
            return "[agent] No previous response to assess."
        last = self._history[-1]
        return (f"[agent] Last {last['kind']} was based on a single AI call with no "
                f"external verification — treat it as a strong hint, not ground truth.")

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
