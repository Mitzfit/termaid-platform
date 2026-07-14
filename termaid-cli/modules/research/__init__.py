"""Research Module — Web fetch + AI summarization for research workflows.

Fetches a URL, strips HTML down to readable text (a lightweight regex strip —
no external HTML-parsing dependency), and optionally asks the AI to
summarize or answer a question about it.

Commands (~9):
  /research fetch <url>            Fetch a URL, return cleaned plain text (truncated)
  /research summarize <url>          Fetch + AI summary
  /research ask <url> <question>       Fetch + ask the AI a specific question about it
  /research save <name> <url>            Save a URL under a short name for later
  /research list-saved                     List saved URLs
  /research open <name>                      Fetch a previously saved URL by name
  /research explain                            How this module works
"""

import json
import os
import re
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_MAX_CHARS = 8000


def _strip_html(html: str) -> str:
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class ResearchModule(Module):
    name = "research"
    version = "1.0.0"
    description = "Web fetch + AI summarization for research workflows"
    author = "termaid"

    def on_load(self):
        for cmd in ["fetch", "summarize", "ask", "save", "list-saved", "open", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "research"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._saved_file = self._dir / "saved.json"

    def _load_saved(self) -> dict:
        if self._saved_file.exists():
            try:
                return json.loads(self._saved_file.read_text())
            except Exception:
                pass
        return {}

    def _fetch_text(self, url: str) -> tuple[str, str]:
        """Returns (text, error)."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            import httpx
        except ImportError:
            return "", "httpx not installed"
        try:
            with httpx.Client(timeout=15.0, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "Mozilla/5.0 (TermAId research)"})
                resp.raise_for_status()
        except Exception as e:
            return "", str(e)
        text = _strip_html(resp.text)
        return text[:_MAX_CHARS], ""

    @safe
    def cmd_fetch(self, arg=""):
        """Fetch a URL, return cleaned plain text (truncated)"""
        url = (arg or "").strip()
        if not url:
            return "[research] Usage: /research fetch <url>"
        text, err = self._fetch_text(url)
        if err:
            return f"[research] Fetch failed: {err}"
        return text or "[research] (page fetched but no readable text extracted)"

    @safe
    def cmd_summarize(self, arg=""):
        """Fetch + AI summary"""
        url = (arg or "").strip()
        if not url:
            return "[research] Usage: /research summarize <url>"
        text, err = self._fetch_text(url)
        if err:
            return f"[research] Fetch failed: {err}"
        if not self.ai:
            return f"[research] No AI configured. Raw text (truncated):\n\n{text[:1000]}"
        try:
            return self.ask_ai(text, system="Summarize this page in 3-5 sentences, factually, no filler.")
        except Exception as e:
            return f"[research] AI error: {e}"

    @safe
    def cmd_ask(self, arg=""):
        """Fetch + ask the AI a specific question about it: /research ask <url> <question>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[research] Usage: /research ask <url> <question>"
        url, question = parts
        text, err = self._fetch_text(url)
        if err:
            return f"[research] Fetch failed: {err}"
        if not self.ai:
            return "[research] No AI provider configured."
        try:
            return self.ask_ai(
                f"Page content:\n{text}\n\nQuestion: {question}",
                system="Answer the question using ONLY the page content given. If it's not "
                      "answered there, say so plainly rather than guessing.",
            )
        except Exception as e:
            return f"[research] AI error: {e}"

    @safe
    def cmd_save(self, arg=""):
        """Save a URL under a short name: /research save <name> <url>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[research] Usage: /research save <name> <url>"
        name, url = parts
        saved = self._load_saved()
        saved[name] = url
        self._saved_file.write_text(json.dumps(saved, indent=2))
        return f"[research] Saved '{name}' -> {url}"

    @safe
    def cmd_list_saved(self, arg=""):
        """List saved URLs"""
        saved = self._load_saved()
        if not saved:
            return "[research] No saved URLs yet. /research save <name> <url>"
        lines = [f"[research] {len(saved)} saved:"]
        for name, url in sorted(saved.items()):
            lines.append(f"  {name:<15s} {url}")
        return "\n".join(lines)

    @safe
    def cmd_open(self, arg=""):
        """Fetch a previously saved URL by name"""
        name = (arg or "").strip()
        if not name:
            return "[research] Usage: /research open <name>"
        saved = self._load_saved()
        if name not in saved:
            return f"[research] No saved URL named '{name}'"
        return self.cmd_fetch(saved[name])

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
