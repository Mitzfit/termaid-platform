"""Smart Module — Auto-detect wrong commands, suggest corrections.

Scans the modules/ directory the same way /catalog does (reading files
directly, not importing them) to build a list of every real "mod.cmd" name,
then uses difflib to find close matches for a mistyped command. Also keeps a
small learned-corrections table you can seed manually or bulk-import, and
tracks how often each learned correction actually gets used so you can see
which typos are worth having learned.

Commands (~10):
  /smart suggest <mod.cmd>       Closest real command(s) to a (possibly mistyped) one
  /smart did-you-mean <mod.cmd>   Alias of suggest
  /smart learn <wrong> <right>     Record a manual correction mapping
  /smart bulk-learn <path>          Import a JSON file of {"wrong": "right", ...} mappings
  /smart corrections                  List manually learned corrections
  /smart stats                          How often each learned correction has fired
  /smart forget <wrong>                    Remove a learned correction
  /smart count                               How many real commands are known
  /smart explain                               How this module works
"""

import difflib
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


class SmartModule(Module):
    name = "smart"
    version = "1.1.0"
    description = "Auto-detect wrong commands, suggest corrections"
    author = "termaid"

    def on_load(self):
        for cmd in ["suggest", "did-you-mean", "learn", "bulk-learn", "corrections",
                    "stats", "forget", "count", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "smart"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._corrections_file = self._dir / "corrections.json"
        self._stats_file = self._dir / "trigger_stats.json"
        self._modules_dir = Path(__file__).resolve().parent.parent
        self._cmd_cache = None

    def _load_corrections(self) -> dict:
        if self._corrections_file.exists():
            try:
                return json.loads(self._corrections_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_corrections(self, data: dict) -> None:
        self._corrections_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_stats(self) -> dict:
        if self._stats_file.exists():
            try:
                return json.loads(self._stats_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_stats(self, stats: dict) -> None:
        self._stats_file.write_text(json.dumps(stats, indent=2), encoding="utf-8")

    def _bump_stat(self, wrong: str) -> None:
        stats = self._load_stats()
        stats[wrong] = stats.get(wrong, 0) + 1
        self._save_stats(stats)

    def _known_commands(self, force: bool = False) -> list:
        """All 'mod.cmd' strings, discovered by reading module files directly
        (no import, so this is cheap and can't crash on a broken module)."""
        if self._cmd_cache is not None and not force:
            return self._cmd_cache
        out = []
        if self._modules_dir.is_dir():
            for entry in sorted(self._modules_dir.iterdir()):
                if not entry.is_dir() or entry.name.startswith(("_", ".")):
                    continue
                init_py = entry / "__init__.py"
                if not init_py.exists():
                    continue
                try:
                    text = init_py.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                name_match = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.M)
                mod_name = name_match.group(1) if name_match else entry.name
                for cmd in re.findall(r"def\s+cmd_(\w+)\s*\(", text):
                    out.append(f"{mod_name}.{cmd.replace('_', '-')}")
        self._cmd_cache = out
        return out

    @safe
    def cmd_suggest(self, arg=""):
        """Closest real command(s) to a (possibly mistyped) one"""
        typed = (arg or "").strip()
        if not typed:
            return "[smart] Usage: /smart suggest <mod.cmd>"
        corrections = self._load_corrections()
        if typed in corrections:
            self._bump_stat(typed)
            return f"[smart] Did you mean '{corrections[typed]}'? (learned correction)"
        known = self._known_commands()
        matches = difflib.get_close_matches(typed, known, n=5, cutoff=0.5)
        if not matches:
            return f"[smart] No close match found for '{typed}' among {len(known)} known commands."
        lines = [f"[smart] Closest match(es) to '{typed}':"]
        for m in matches:
            lines.append(f"  {m}")
        return "\n".join(lines)

    @safe
    def cmd_did_you_mean(self, arg=""):
        """Alias of /smart suggest"""
        return self.cmd_suggest(arg)

    @safe
    def cmd_learn(self, arg=""):
        """Record a manual correction: /smart learn <wrong> <right>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[smart] Usage: /smart learn <wrong-command> <right-command>"
        wrong, right = parts
        corrections = self._load_corrections()
        corrections[wrong] = right
        self._save_corrections(corrections)
        return f"[smart] Learned: '{wrong}' -> '{right}'"

    @safe
    def cmd_bulk_learn(self, arg=""):
        """Import a JSON file of {"wrong": "right", ...} mappings: /smart bulk-learn <path>"""
        path = (arg or "").strip()
        if not path:
            return '[smart] Usage: /smart bulk-learn <path> (a JSON object: {"wrong": "right", ...})'
        p = Path(path).expanduser()
        if not p.is_file():
            return f"[smart] Not found: {p}"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return f"[smart] Couldn't parse {p}: {e}"
        if not isinstance(data, dict):
            return f"[smart] {p} must contain a JSON object of wrong -> right mappings"
        corrections = self._load_corrections()
        added = 0
        for wrong, right in data.items():
            if isinstance(wrong, str) and isinstance(right, str):
                corrections[wrong] = right
                added += 1
        self._save_corrections(corrections)
        return f"[smart] Imported {added} correction(s) from {p}"

    @safe
    def cmd_corrections(self, arg=""):
        """List manually learned corrections"""
        corrections = self._load_corrections()
        if not corrections:
            return "[smart] No learned corrections yet. /smart learn <wrong> <right>"
        lines = [f"[smart] {len(corrections)} learned correction(s):"]
        for wrong, right in sorted(corrections.items()):
            lines.append(f"  {wrong} -> {right}")
        return "\n".join(lines)

    @safe
    def cmd_stats(self, arg=""):
        """How often each learned correction has fired"""
        stats = self._load_stats()
        if not stats:
            return "[smart] No corrections have fired yet."
        lines = [f"[smart] Trigger counts ({len(stats)} correction(s) ever used):"]
        for wrong, count in sorted(stats.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {count:4d}x  {wrong}")
        return "\n".join(lines)

    @safe
    def cmd_forget(self, arg=""):
        """Remove a learned correction"""
        wrong = (arg or "").strip()
        if not wrong:
            return "[smart] Usage: /smart forget <wrong-command>"
        corrections = self._load_corrections()
        if wrong not in corrections:
            return f"[smart] No learned correction for '{wrong}'"
        del corrections[wrong]
        self._save_corrections(corrections)
        return f"[smart] Forgot correction for '{wrong}'"

    @safe
    def cmd_count(self, arg=""):
        """How many real commands are known"""
        known = self._known_commands(force=True)
        return f"[smart] {len(known)} known command(s) across the modules/ directory"

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
