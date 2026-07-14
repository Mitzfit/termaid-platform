"""Keyring Module — OS-native secure secret storage.

Wraps the `keyring` PyPI package, which talks to Windows Credential
Manager, macOS Keychain, or the Linux Secret Service (whichever the OS
provides) — secrets never touch a plaintext file TermAId controls. If the
package (or a working backend) isn't available, every command reports
that clearly rather than silently falling back to something less secure;
use /apikeys if you knowingly want a simpler plaintext store instead.

Commands (~4):
  /keyring set <service> <username> <secret>     Store a secret
  /keyring get <service> <username>                Retrieve a secret
  /keyring remove <service> <username> confirm       Delete a secret
  /keyring explain                                     How this module works
"""

import sys
from pathlib import Path as _Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

# The module loader puts <TERMAID_ROOT>/modules on sys.path so `modules.<name>`
# packages can be found — but that means a bare `import keyring` from *this*
# file (which lives in modules/keyring/) would resolve to itself instead of
# the real PyPI package. Filter that one entry out just for this import.
_saved_path = sys.path[:]
try:
    sys.path = [p for p in sys.path if _Path(p).name != "modules"]
    try:
        import keyring as _keyring
        _AVAILABLE = True
    except ImportError:
        _AVAILABLE = False
finally:
    sys.path = _saved_path

_APP = "termaid"


class KeyringModule(Module):
    name = "keyring"
    version = "1.0.0"
    description = "OS-native secure secret storage (Windows Credential Manager / macOS Keychain / Secret Service)"
    author = "termaid"

    def on_load(self):
        for cmd in ["set", "get", "remove", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _key(self, service: str, username: str) -> str:
        return f"{_APP}:{service}:{username}"

    @safe
    def cmd_set(self, arg=""):
        """Store a secret: /keyring set <service> <username> <secret>"""
        if not _AVAILABLE:
            return "[keyring] The 'keyring' package isn't installed.\n  Install it with: pip install keyring"
        parts = (arg or "").split(maxsplit=2)
        if len(parts) < 3:
            return "[keyring] Usage: /keyring set <service> <username> <secret>"
        service, username, secret = parts
        try:
            _keyring.set_password(self._key(service, username), username, secret)
        except Exception as e:
            return f"[keyring] Failed to store secret: {e}"
        return f"[keyring] Stored secret for {service}/{username} in the OS credential store"

    @safe
    def cmd_get(self, arg=""):
        """Retrieve a secret: /keyring get <service> <username>"""
        if not _AVAILABLE:
            return "[keyring] The 'keyring' package isn't installed.\n  Install it with: pip install keyring"
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[keyring] Usage: /keyring get <service> <username>"
        service, username = parts[0], parts[1]
        try:
            secret = _keyring.get_password(self._key(service, username), username)
        except Exception as e:
            return f"[keyring] Failed to retrieve secret: {e}"
        if secret is None:
            return f"[keyring] No secret found for {service}/{username}"
        return f"[keyring] {service}/{username} = {secret}"

    @safe
    def cmd_remove(self, arg=""):
        """Delete a secret (confirms): /keyring remove <service> <username> confirm"""
        if not _AVAILABLE:
            return "[keyring] The 'keyring' package isn't installed.\n  Install it with: pip install keyring"
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[keyring] Usage: /keyring remove <service> <username> confirm"
        service, username = parts[0], parts[1]
        try:
            _keyring.delete_password(self._key(service, username), username)
        except Exception as e:
            return f"[keyring] Failed to remove secret (may not exist): {e}"
        return f"[keyring] Removed secret for {service}/{username}"

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
