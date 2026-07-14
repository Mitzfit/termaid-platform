"""Text Module — Text processing utilities: case, sort, dedupe, wrap, count, replace.

Commands (~24):
  /text upper <text>            UPPERCASE
  /text lower <text>            lowercase
  /text title <text>            Title Case
  /text camel <text>            camelCase
  /text snake <text>            snake_case
  /text kebab <text>            kebab-case
  /text sort <lines>            Sort lines alphabetically
  /text dedupe <lines>          Remove duplicate lines (order-preserving)
  /text wrap <width> <text>     Word-wrap to a given column width
  /text count <text>            Char/word/line counts
  /text replace <old> <new> <text>   Literal find/replace
  /text reverse <text>          Reverse the string
  /text trim <text>             Strip leading/trailing whitespace per line
  /text pad <width> <text>      Pad to width (right-pad with spaces)
  /text slug <text>             URL-friendly slug
  /text lines <text>            Split into numbered lines
  /text join <sep> <lines>      Join lines with a separator
  /text search <pattern> <text> Literal substring search with line numbers
  /text emails <text>           Extract email addresses
  /text urls <text>             Extract URLs
  /text b64encode <text>        Base64 encode
  /text b64decode <text>        Base64 decode
  /text rot13 <text>            ROT13 cipher
  /text explain                 How this module works
"""

import base64
import codecs
import re
import textwrap
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _to_words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", text)


class TextModule(Module):
    name = "text"
    version = "1.0.0"
    description = "Text processing utilities: case, sort, dedupe, wrap, count, replace"
    author = "termaid"

    def on_load(self):
        cmds = ["upper", "lower", "title", "camel", "snake", "kebab",
                "sort", "dedupe", "wrap", "count", "replace", "reverse",
                "trim", "pad", "slug", "lines", "join", "search",
                "emails", "urls", "b64encode", "b64decode", "rot13", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_upper(self, arg=""):
        """UPPERCASE"""
        return (arg or "").upper() or "[text] Usage: /text upper <text>"

    @safe
    def cmd_lower(self, arg=""):
        """lowercase"""
        return (arg or "").lower() or "[text] Usage: /text lower <text>"

    @safe
    def cmd_title(self, arg=""):
        """Title Case"""
        return (arg or "").title() or "[text] Usage: /text title <text>"

    @safe
    def cmd_camel(self, arg=""):
        """camelCase"""
        words = _to_words(arg or "")
        if not words:
            return "[text] Usage: /text camel <text>"
        return words[0].lower() + "".join(w.capitalize() for w in words[1:])

    @safe
    def cmd_snake(self, arg=""):
        """snake_case"""
        words = _to_words(arg or "")
        if not words:
            return "[text] Usage: /text snake <text>"
        return "_".join(w.lower() for w in words)

    @safe
    def cmd_kebab(self, arg=""):
        """kebab-case"""
        words = _to_words(arg or "")
        if not words:
            return "[text] Usage: /text kebab <text>"
        return "-".join(w.lower() for w in words)

    @safe
    def cmd_sort(self, arg=""):
        """Sort lines alphabetically"""
        text = arg or ""
        if not text.strip():
            return "[text] Usage: /text sort <newline-separated lines>"
        return "\n".join(sorted(text.splitlines()))

    @safe
    def cmd_dedupe(self, arg=""):
        """Remove duplicate lines (order-preserving)"""
        text = arg or ""
        if not text.strip():
            return "[text] Usage: /text dedupe <newline-separated lines>"
        seen = set()
        out = []
        for line in text.splitlines():
            if line not in seen:
                seen.add(line)
                out.append(line)
        return "\n".join(out)

    @safe
    def cmd_wrap(self, arg=""):
        """Word-wrap to a given column width: /text wrap <width> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[text] Usage: /text wrap <width> <text>"
        try:
            width = int(parts[0])
        except Exception:
            return "[text] Width must be an integer"
        return "\n".join(textwrap.wrap(parts[1], width=width)) or ""

    @safe
    def cmd_count(self, arg=""):
        """Char/word/line counts"""
        text = arg or ""
        lines = text.splitlines() or [""]
        words = _to_words(text)
        return (f"[text] chars={len(text)}  words={len(words)}  "
                f"lines={len(lines)}  (no trailing whitespace, incl. text passed)")

    @safe
    def cmd_replace(self, arg=""):
        """Literal find/replace: /text replace <old> <new> <text>"""
        parts = (arg or "").split(None, 2)
        if len(parts) != 3:
            return "[text] Usage: /text replace <old> <new> <text>"
        old, new, text = parts
        return text.replace(old, new)

    @safe
    def cmd_reverse(self, arg=""):
        """Reverse the string"""
        return (arg or "")[::-1] or "[text] Usage: /text reverse <text>"

    @safe
    def cmd_trim(self, arg=""):
        """Strip leading/trailing whitespace per line"""
        text = arg or ""
        if not text:
            return "[text] Usage: /text trim <text>"
        return "\n".join(line.strip() for line in text.splitlines())

    @safe
    def cmd_pad(self, arg=""):
        """Pad to width: /text pad <width> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[text] Usage: /text pad <width> <text>"
        try:
            width = int(parts[0])
        except Exception:
            return "[text] Width must be an integer"
        return parts[1].ljust(width)

    @safe
    def cmd_slug(self, arg=""):
        """URL-friendly slug"""
        text = (arg or "").strip().lower()
        if not text:
            return "[text] Usage: /text slug <text>"
        slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
        return slug or "[text] (nothing left after slugifying)"

    @safe
    def cmd_lines(self, arg=""):
        """Split into numbered lines"""
        text = arg or ""
        if not text:
            return "[text] Usage: /text lines <text>"
        return "\n".join(f"{i:>4d}: {line}" for i, line in enumerate(text.splitlines(), 1))

    @safe
    def cmd_join(self, arg=""):
        """Join lines with a separator: /text join <sep> <lines>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[text] Usage: /text join <sep> <newline-separated lines>"
        sep, text = parts
        sep = sep.replace("\\n", "\n").replace("\\t", "\t")
        return sep.join(text.splitlines())

    @safe
    def cmd_search(self, arg=""):
        """Literal substring search with line numbers: /text search <pattern> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[text] Usage: /text search <pattern> <text>"
        pattern, text = parts
        hits = [f"  {i}: {line}" for i, line in enumerate(text.splitlines(), 1) if pattern in line]
        if not hits:
            return f"[text] No matches for '{pattern}'"
        return f"[text] {len(hits)} match(es):\n" + "\n".join(hits)

    @safe
    def cmd_emails(self, arg=""):
        """Extract email addresses"""
        hits = _EMAIL_RE.findall(arg or "")
        return "\n".join(hits) if hits else "[text] No email addresses found"

    @safe
    def cmd_urls(self, arg=""):
        """Extract URLs"""
        hits = _URL_RE.findall(arg or "")
        return "\n".join(hits) if hits else "[text] No URLs found"

    @safe
    def cmd_b64encode(self, arg=""):
        """Base64 encode"""
        text = arg or ""
        if not text:
            return "[text] Usage: /text b64encode <text>"
        return base64.b64encode(text.encode("utf-8")).decode("ascii")

    @safe
    def cmd_b64decode(self, arg=""):
        """Base64 decode"""
        text = (arg or "").strip()
        if not text:
            return "[text] Usage: /text b64decode <base64-text>"
        try:
            return base64.b64decode(text).decode("utf-8", errors="replace")
        except Exception as e:
            return f"[text] Decode failed: {e}"

    @safe
    def cmd_rot13(self, arg=""):
        """ROT13 cipher"""
        text = arg or ""
        if not text:
            return "[text] Usage: /text rot13 <text>"
        return codecs.encode(text, "rot13")

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
