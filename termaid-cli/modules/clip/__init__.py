"""Clip Module — Cross-platform clipboard manager with history.

Reads/writes the OS clipboard via small platform-specific subprocess calls
(no third-party clipboard library needed): PowerShell Get-Clipboard/Set-Clipboard
on Windows, pbcopy/pbpaste on macOS, xclip/xsel on Linux/Termux.

Every /clip copy is also appended to a local history file (this module's own
history — it can't see clipboard changes made by other applications).

Commands (11):
  /clip copy <text>          Copy text to the clipboard (+ record in history)
  /clip paste                Read the current clipboard contents
  /clip history [n]          Show the last n copies (default 10)
  /clip clear-history        Clear the history (confirms)
  /clip save <name> <text>   Save named text (not the live clipboard)
  /clip load <name>          Copy a saved named text back to the clipboard
  /clip list-saved           List saved named entries
  /clip delete-saved <name>  Delete a saved named entry
  /clip search <text>        Search history + saved entries
  /clip status               Which clipboard backend is in use
  /clip explain              How this module works
"""

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _backend() -> str:
    if sys.platform == "win32":
        return "powershell"
    if sys.platform == "darwin":
        return "pbcopy/pbpaste"
    if shutil.which("xclip"):
        return "xclip"
    if shutil.which("xsel"):
        return "xsel"
    if shutil.which("termux-clipboard-set"):
        return "termux-api"
    return "none"


def _clip_set(text: str) -> str | None:
    """Write to the OS clipboard. Returns an error string, or None on success."""
    try:
        if sys.platform == "win32":
            subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
                          input=text, capture_output=True, text=True, timeout=5)
        elif sys.platform == "darwin":
            subprocess.run(["pbcopy"], input=text, capture_output=True, text=True, timeout=5)
        elif shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=text,
                          capture_output=True, text=True, timeout=5)
        elif shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"], input=text,
                          capture_output=True, text=True, timeout=5)
        elif shutil.which("termux-clipboard-set"):
            subprocess.run(["termux-clipboard-set"], input=text,
                          capture_output=True, text=True, timeout=5)
        else:
            return "no clipboard backend found on this platform"
        return None
    except Exception as e:
        return str(e)


def _clip_get() -> tuple[str, str | None]:
    """Read the OS clipboard. Returns (text, error)."""
    try:
        if sys.platform == "win32":
            r = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                              capture_output=True, text=True, timeout=5)
            return (r.stdout.rstrip("\r\n"), None if r.returncode == 0 else r.stderr)
        elif sys.platform == "darwin":
            r = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            return (r.stdout, None if r.returncode == 0 else r.stderr)
        elif shutil.which("xclip"):
            r = subprocess.run(["xclip", "-selection", "clipboard", "-o"],
                              capture_output=True, text=True, timeout=5)
            return (r.stdout, None if r.returncode == 0 else r.stderr)
        elif shutil.which("xsel"):
            r = subprocess.run(["xsel", "--clipboard", "--output"],
                              capture_output=True, text=True, timeout=5)
            return (r.stdout, None if r.returncode == 0 else r.stderr)
        elif shutil.which("termux-clipboard-get"):
            r = subprocess.run(["termux-clipboard-get"], capture_output=True, text=True, timeout=5)
            return (r.stdout, None if r.returncode == 0 else r.stderr)
        return ("", "no clipboard backend found on this platform")
    except Exception as e:
        return ("", str(e))


class ClipModule(Module):
    name = "clip"
    version = "1.0.0"
    description = "Cross-platform clipboard manager with history"
    author = "termaid"

    def on_load(self):
        for cmd in ["copy", "paste", "history", "clear-history", "save",
                    "load", "list-saved", "delete-saved", "search", "status", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "clip"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._history_file = self._dir / "history.json"
        self._saved_file = self._dir / "saved.json"

    def _load_json(self, path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return default

    @safe
    def cmd_copy(self, arg=""):
        """Copy text to the clipboard (+ record in history)"""
        text = arg or ""
        if not text:
            return "[clip] Usage: /clip copy <text>"
        err = _clip_set(text)
        if err:
            return f"[clip] Copy failed: {err}"
        history = self._load_json(self._history_file, [])
        history.append({"text": text, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        self._history_file.write_text(json.dumps(history[-200:], indent=2))
        return f"[clip] Copied ({len(text)} chars)"

    @safe
    def cmd_paste(self, arg=""):
        """Read the current clipboard contents"""
        text, err = _clip_get()
        if err:
            return f"[clip] Paste failed: {err}"
        return text if text else "[clip] Clipboard is empty"

    @safe
    def cmd_history(self, arg=""):
        """Show the last n copies (default 10)"""
        try:
            n = int((arg or "10").strip())
        except Exception:
            n = 10
        history = self._load_json(self._history_file, [])
        if not history:
            return "[clip] No copy history yet."
        lines = [f"[clip] Last {min(n, len(history))} of {len(history)} copies:"]
        for item in history[-n:][::-1]:
            preview = item["text"][:60].replace("\n", " ")
            lines.append(f"  [{item.get('at', '?')}] {preview}")
        return "\n".join(lines)

    @safe
    def cmd_clear_history(self, arg=""):
        """Clear the history (confirms)"""
        if (arg or "").strip().lower() != "confirm":
            return "[clip] This clears ALL copy history. Re-run as: /clip clear-history confirm"
        n = len(self._load_json(self._history_file, []))
        self._history_file.write_text("[]")
        return f"[clip] Cleared {n} entr{'y' if n == 1 else 'ies'}."

    @safe
    def cmd_save(self, arg=""):
        """Save named text: /clip save <name> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[clip] Usage: /clip save <name> <text>"
        name, text = parts
        saved = self._load_json(self._saved_file, {})
        saved[name] = text
        self._saved_file.write_text(json.dumps(saved, indent=2))
        return f"[clip] Saved '{name}'"

    @safe
    def cmd_load(self, arg=""):
        """Copy a saved named text back to the clipboard"""
        name = (arg or "").strip()
        if not name:
            return "[clip] Usage: /clip load <name>"
        saved = self._load_json(self._saved_file, {})
        if name not in saved:
            return f"[clip] No saved entry named '{name}'"
        err = _clip_set(saved[name])
        if err:
            return f"[clip] Copy failed: {err}"
        return f"[clip] Copied '{name}' to the clipboard"

    @safe
    def cmd_list_saved(self, arg=""):
        """List saved named entries"""
        saved = self._load_json(self._saved_file, {})
        if not saved:
            return "[clip] No saved entries yet. /clip save <name> <text>"
        lines = [f"[clip] {len(saved)} saved entr{'y' if len(saved) == 1 else 'ies'}:"]
        for name, text in sorted(saved.items()):
            lines.append(f"  {name:<15s} {text[:50]!r}")
        return "\n".join(lines)

    @safe
    def cmd_delete_saved(self, arg=""):
        """Delete a saved named entry"""
        name = (arg or "").strip()
        if not name:
            return "[clip] Usage: /clip delete-saved <name>"
        saved = self._load_json(self._saved_file, {})
        if name not in saved:
            return f"[clip] No saved entry named '{name}'"
        del saved[name]
        self._saved_file.write_text(json.dumps(saved, indent=2))
        return f"[clip] Deleted '{name}'"

    @safe
    def cmd_search(self, arg=""):
        """Search history + saved entries"""
        q = (arg or "").strip().lower()
        if not q:
            return "[clip] Usage: /clip search <text>"
        lines = [f"[clip] Results for '{q}':"]
        history = self._load_json(self._history_file, [])
        hist_hits = [h for h in history if q in h["text"].lower()]
        if hist_hits:
            lines.append(f"\n  History ({len(hist_hits)}):")
            for h in hist_hits[-10:]:
                lines.append(f"    [{h.get('at', '?')}] {h['text'][:60]}")
        saved = self._load_json(self._saved_file, {})
        saved_hits = {n: t for n, t in saved.items() if q in n.lower() or q in t.lower()}
        if saved_hits:
            lines.append(f"\n  Saved ({len(saved_hits)}):")
            for name, text in saved_hits.items():
                lines.append(f"    {name}: {text[:60]}")
        if not hist_hits and not saved_hits:
            lines.append("  No matches.")
        return "\n".join(lines)

    @safe
    def cmd_status(self, arg=""):
        """Which clipboard backend is in use"""
        return f"[clip] Backend: {_backend()}  (platform: {sys.platform})"

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
