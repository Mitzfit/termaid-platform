"""ApiKeys Module — Named API key store (PLAINTEXT — not encrypted).

Deliberately simple and explicit about its limits: this is a JSON file on
disk, not a vault. Values are masked by default everywhere they'd be
displayed (list/get without --reveal), but anyone with filesystem access
to TermAId's data directory can read the raw file. For anything that
actually needs OS-level secret protection, use /keyring instead (Windows
Credential Manager / macOS Keychain / Linux Secret Service via the
`keyring` package). SYSTEM-tier — never loaded in server mode.

Commands (~5):
  /apikeys set <name> <key>          Store a key (overwrites silently)
  /apikeys get <name> [reveal]         Show a key (masked unless 'reveal')
  /apikeys list                          List names + masked values
  /apikeys remove <name> confirm           Delete a stored key
  /apikeys explain                           How this module works
"""

import json
import os
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _mask(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


class ApiKeysModule(Module):
    name = "apikeys"
    version = "1.0.0"
    description = "Named API key store (plaintext — not encrypted; see /keyring for secure storage)"
    author = "termaid"

    def on_load(self):
        for cmd in ["set", "get", "list", "remove", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._path = data_dir / "apikeys.json"
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save(self):
        self._path.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    @safe
    def cmd_set(self, arg=""):
        """Store a key (overwrites silently): /apikeys set <name> <key>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[apikeys] Usage: /apikeys set <name> <key>"
        name, key = parts[0], parts[1].strip()
        self._data[name] = key
        self._save()
        return f"[apikeys] Stored '{name}' = {_mask(key)}  (plaintext on disk — see /keyring for secure storage)"

    @safe
    def cmd_get(self, arg=""):
        """Show a key (masked unless 'reveal'): /apikeys get <name> [reveal]"""
        parts = (arg or "").split()
        if not parts:
            return "[apikeys] Usage: /apikeys get <name> [reveal]"
        name = parts[0]
        reveal = len(parts) > 1 and parts[1].lower() == "reveal"
        if name not in self._data:
            return f"[apikeys] No key named '{name}'"
        value = self._data[name]
        return f"[apikeys] {name} = {value if reveal else _mask(value)}"

    @safe
    def cmd_list(self, arg=""):
        """List names + masked values"""
        if not self._data:
            return "[apikeys] No keys stored yet. /apikeys set <name> <key>"
        lines = [f"[apikeys] {len(self._data)} key(s):"]
        for name, value in sorted(self._data.items()):
            lines.append(f"  {name:20s} {_mask(value)}")
        return "\n".join(lines)

    @safe
    def cmd_remove(self, arg=""):
        """Delete a stored key (confirms): /apikeys remove <name> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            name = parts[0] if parts else "<name>"
            return f"[apikeys] Re-run as: /apikeys remove {name} confirm"
        name = parts[0]
        if name not in self._data:
            return f"[apikeys] No key named '{name}'"
        del self._data[name]
        self._save()
        return f"[apikeys] Removed '{name}'"

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
