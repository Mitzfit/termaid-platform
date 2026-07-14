"""Assistant Module — Proactive AI guidance with tutorials and quick-start help.

Answers general questions via the configured AI provider, and ships a small
set of canned (offline, no-AI-required) tutorials/tips about using TermAId
itself, so new users get something useful even with no AI provider set up.
Ask exchanges persist to disk (mirroring /brain's history pattern) so you
can look back at what you've asked; feedback you leave is saved to its own
file for later review rather than just vanishing into the response.

Commands (~11):
  /assistant ask <question>     General AI Q&A
  /assistant tutorial <topic>    AI-generated walkthrough for a topic
  /assistant tutorials             List built-in tutorial topics
  /assistant quickstart              Canned quick-start guide (no AI needed)
  /assistant tip                      A random usage tip (no AI needed)
  /assistant search <query>            Search built-in tips + tutorial topics
  /assistant whatsnew                    What changed recently (reads HISTORY.md if present)
  /assistant history [n]                    Recent /assistant ask exchanges (default 20)
  /assistant feedback <text>                   Leave feedback, saved for later review
  /assistant explain                             How this module works
"""

import json
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_QUICKSTART = (
    "TermAId quickstart:\n"
    "  1. Type a command as <module>.<command> <args>, e.g. calc.hex 255\n"
    "  2. /catalog modules lists everything available; /catalog search <text> finds a command\n"
    "  3. /smart suggest <mod.cmd> fixes a typo if you're not sure of the exact name\n"
    "  4. /brain think <message> talks to the AI (needs AI_PROVIDER configured)\n"
    "  5. /aliases and /chain let you save shortcuts and sequences for later"
)

_TIPS = [
    "Use /catalog search <text> when you can't remember an exact command name.",
    "/smart suggest fixes typos by fuzzy-matching against every real command.",
    "/aliases add <name> <command> is faster than retyping a long command every time.",
    "/brain layers shows which context (persona/rules/memory/lessons) feeds the AI.",
    "/cognition preset careful makes the AI plan and self-check before answering.",
]

_TUTORIAL_TOPICS = ["memory", "aliases", "chains", "personas", "brain-layers", "cognition-presets"]


class AssistantModule(Module):
    name = "assistant"
    version = "1.1.0"
    description = "Proactive AI guidance with tutorials and admin-aware mode"
    author = "termaid"

    def on_load(self):
        for cmd in ["ask", "tutorial", "tutorials", "quickstart", "tip",
                    "search", "whatsnew", "history", "feedback", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        self._tip_idx = 0

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "assistant"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._history_file = self._dir / "history.jsonl"
        self._feedback_file = self._dir / "feedback.jsonl"

    def _append_history(self, question: str, answer: str) -> None:
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "q": question[:200], "a": answer[:400]}
        with self._history_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    @safe
    def cmd_ask(self, arg=""):
        """General AI Q&A"""
        if not self.ai:
            return "[assistant] No AI provider configured. See /assistant quickstart for offline help."
        question = arg or ""
        if not question:
            return "[assistant] Usage: /assistant ask <question>"
        try:
            answer = self.ask_ai(question, system="You are TermAId's help assistant. Be concise and concrete.")
        except Exception as e:
            return f"[assistant] AI error: {e}"
        self._append_history(question, answer)
        return answer

    @safe
    def cmd_tutorial(self, arg=""):
        """AI-generated walkthrough for a topic"""
        topic = (arg or "").strip()
        if not topic:
            return "[assistant] Usage: /assistant tutorial <topic>. See /assistant tutorials"
        if not self.ai:
            return (f"[assistant] No AI provider configured, so I can't generate a tutorial for "
                    f"'{topic}' right now. Built-in topics: {', '.join(_TUTORIAL_TOPICS)}")
        try:
            return self.ask_ai(
                f"Write a short (5-8 step) tutorial for using TermAId's '{topic}' feature.",
                system="You are TermAId's documentation writer. Be concrete, use numbered steps.",
            )
        except Exception as e:
            return f"[assistant] AI error: {e}"

    @safe
    def cmd_tutorials(self, arg=""):
        """List built-in tutorial topics"""
        return "[assistant] Tutorial topics: " + ", ".join(_TUTORIAL_TOPICS)

    @safe
    def cmd_quickstart(self, arg=""):
        """Canned quick-start guide (no AI needed)"""
        return f"[assistant] {_QUICKSTART}"

    @safe
    def cmd_tip(self, arg=""):
        """A random usage tip (no AI needed)"""
        import secrets
        return f"[assistant] Tip: {secrets.choice(_TIPS)}"

    @safe
    def cmd_search(self, arg=""):
        """Search built-in tips + tutorial topics: /assistant search <query>"""
        query = (arg or "").strip().lower()
        if not query:
            return "[assistant] Usage: /assistant search <query>"
        hits = []
        for tip in _TIPS:
            if query in tip.lower():
                hits.append(f"tip: {tip}")
        for topic in _TUTORIAL_TOPICS:
            if query in topic.lower():
                hits.append(f"tutorial topic: {topic}")
        if query in _QUICKSTART.lower():
            hits.append("quickstart guide mentions this — see /assistant quickstart")
        if not hits:
            return f"[assistant] No built-in tips/topics match '{query}'. Try /assistant ask instead."
        return f"[assistant] {len(hits)} match(es):\n" + "\n".join(f"  {h}" for h in hits)

    @safe
    def cmd_whatsnew(self, arg=""):
        """What changed recently (reads HISTORY.md if present)"""
        for candidate in (Path.cwd() / "HISTORY.md", Path(__file__).resolve().parents[3] / "HISTORY.md"):
            if candidate.exists():
                lines = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
                recent = [l for l in lines if l.strip().startswith("-")][:8]
                if recent:
                    return "[assistant] Recent history:\n" + "\n".join(recent)
        return "[assistant] No HISTORY.md found from the current working directory."

    @safe
    def cmd_history(self, arg=""):
        """Recent /assistant ask exchanges (default 20): /assistant history [n]"""
        s = (arg or "").strip()
        try:
            limit = int(s) if s else 20
        except ValueError:
            limit = 20
        if not self._history_file.exists():
            return "[assistant] No exchanges recorded yet."
        lines_raw = self._history_file.read_text(encoding="utf-8").splitlines()[-limit:]
        entries = []
        for l in lines_raw:
            if l.strip():
                try:
                    entries.append(json.loads(l))
                except Exception:
                    continue
        if not entries:
            return "[assistant] No exchanges recorded yet."
        out = [f"[assistant] Last {len(entries)} exchange(s):"]
        for e in entries:
            out.append(f"  [{e.get('at', '?')}] Q: {e.get('q', '')} -> A: {e.get('a', '')}")
        return "\n".join(out)

    @safe
    def cmd_feedback(self, arg=""):
        """Leave feedback, saved for later review: /assistant feedback <text>"""
        text = (arg or "").strip()
        if not text:
            return "[assistant] Usage: /assistant feedback <text>"
        entry = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), "text": text}
        with self._feedback_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        return "[assistant] Thanks — feedback saved."

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
