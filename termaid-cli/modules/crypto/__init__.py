"""Crypto Module — File encryption/signing. DANGEROUS tier.

Uses `cryptography`'s Fernet (AES-128-CBC + HMAC, authenticated encryption)
for encrypt/decrypt and stdlib `hmac`/`sha256` for sign/verify — vetted
primitives, not a hand-rolled cipher. Encrypt/decrypt always write to a
NEW file (never overwrite the source), specifically so a mistake doesn't
destroy the only copy of either the plaintext or the ciphertext. Losing
the key file is still unrecoverable by design (that's what encryption
means) — /crypto keygen tells you exactly where it's stored so you can
back it up yourself.

Commands (~6):
  /crypto keygen [name]                    Generate a new key (default name "default")
  /crypto list-keys                          List available key names
  /crypto encrypt <path> [key] confirm         Encrypt a file to <path>.enc
  /crypto decrypt <path.enc> [key] confirm       Decrypt to <path> (without .enc)
  /crypto sign <path> [key]                        HMAC-sign a file to <path>.sig
  /crypto verify <path> <sig-path> [key]             Verify a signature
  /crypto explain                                        How this module works
"""

import hashlib
import hmac
import os
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

try:
    from cryptography.fernet import Fernet, InvalidToken
    _CRYPTO_AVAILABLE = True
except ImportError:
    _CRYPTO_AVAILABLE = False


class CryptoModule(Module):
    name = "crypto"
    version = "1.0.0"
    description = "File encryption/signing (Fernet + HMAC-SHA256 — vetted primitives)"
    author = "termaid"

    def on_load(self):
        for cmd in ["keygen", "list-keys", "encrypt", "decrypt", "sign", "verify", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._key_dir = data_dir / "crypto_keys"
        self._key_dir.mkdir(parents=True, exist_ok=True)

    def _key_path(self, name: str) -> Path:
        return self._key_dir / f"{name}.key"

    @safe
    def cmd_keygen(self, arg=""):
        """Generate a new key (default name "default"): /crypto keygen [name]"""
        if not _CRYPTO_AVAILABLE:
            return "[crypto] The 'cryptography' package isn't installed.\n  Install it with: pip install cryptography"
        name = (arg or "default").strip()
        path = self._key_path(name)
        if path.exists():
            return f"[crypto] Key '{name}' already exists at {path} — not overwriting."
        key = Fernet.generate_key()
        path.write_bytes(key)
        return f"[crypto] Generated key '{name}' -> {path}\n  Back this up — losing it makes anything encrypted with it permanently unrecoverable."

    @safe
    def cmd_list_keys(self, arg=""):
        """List available key names"""
        keys = sorted(p.stem for p in self._key_dir.glob("*.key"))
        if not keys:
            return "[crypto] No keys yet. /crypto keygen [name]"
        return f"[crypto] {len(keys)} key(s): {', '.join(keys)}"

    @safe
    def cmd_encrypt(self, arg=""):
        """Encrypt a file to <path>.enc (confirms): /crypto encrypt <path> [key] confirm"""
        if not _CRYPTO_AVAILABLE:
            return "[crypto] The 'cryptography' package isn't installed."
        parts = (arg or "").split()
        if len(parts) < 2 or parts[-1].lower() != "confirm":
            return "[crypto] Usage: /crypto encrypt <path> [key] confirm"
        path = Path(parts[0]).expanduser()
        key_name = parts[1] if len(parts) == 3 else "default"
        if not path.is_file():
            return f"[crypto] Not found: {path}"
        key_path = self._key_path(key_name)
        if not key_path.exists():
            return f"[crypto] No key named '{key_name}'. /crypto keygen {key_name}"
        out = path.with_suffix(path.suffix + ".enc")
        if out.exists():
            return f"[crypto] {out} already exists — remove it first or choose a different source."
        try:
            fernet = Fernet(key_path.read_bytes())
            token = fernet.encrypt(path.read_bytes())
            out.write_bytes(token)
        except Exception as e:
            return f"[crypto] Failed: {e}"
        return f"[crypto] Encrypted {path} -> {out} (using key '{key_name}'). Original left untouched."

    @safe
    def cmd_decrypt(self, arg=""):
        """Decrypt to <path> without .enc (confirms): /crypto decrypt <path.enc> [key] confirm"""
        if not _CRYPTO_AVAILABLE:
            return "[crypto] The 'cryptography' package isn't installed."
        parts = (arg or "").split()
        if len(parts) < 2 or parts[-1].lower() != "confirm":
            return "[crypto] Usage: /crypto decrypt <path.enc> [key] confirm"
        path = Path(parts[0]).expanduser()
        key_name = parts[1] if len(parts) == 3 else "default"
        if not path.is_file():
            return f"[crypto] Not found: {path}"
        key_path = self._key_path(key_name)
        if not key_path.exists():
            return f"[crypto] No key named '{key_name}'."
        out = path.with_suffix("") if path.suffix == ".enc" else path.with_suffix(path.suffix + ".dec")
        if out.exists():
            return f"[crypto] {out} already exists — remove it first or choose a different destination."
        try:
            fernet = Fernet(key_path.read_bytes())
            data = fernet.decrypt(path.read_bytes())
            out.write_bytes(data)
        except InvalidToken:
            return "[crypto] Decryption failed — wrong key, or the file isn't valid ciphertext from this key."
        except Exception as e:
            return f"[crypto] Failed: {e}"
        return f"[crypto] Decrypted {path} -> {out}. Encrypted file left untouched."

    @safe
    def cmd_sign(self, arg=""):
        """HMAC-sign a file to <path>.sig: /crypto sign <path> [key]"""
        parts = (arg or "").split()
        if not parts:
            return "[crypto] Usage: /crypto sign <path> [key]"
        path = Path(parts[0]).expanduser()
        key_name = parts[1] if len(parts) > 1 else "default"
        if not path.is_file():
            return f"[crypto] Not found: {path}"
        key_path = self._key_path(key_name)
        if not key_path.exists():
            return f"[crypto] No key named '{key_name}'. /crypto keygen {key_name}"
        digest = hmac.new(key_path.read_bytes(), path.read_bytes(), hashlib.sha256).hexdigest()
        sig_path = path.with_suffix(path.suffix + ".sig")
        sig_path.write_text(digest, encoding="utf-8")
        return f"[crypto] Signed {path} -> {sig_path} (using key '{key_name}')"

    @safe
    def cmd_verify(self, arg=""):
        """Verify a signature: /crypto verify <path> <sig-path> [key]"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[crypto] Usage: /crypto verify <path> <sig-path> [key]"
        path = Path(parts[0]).expanduser()
        sig_path = Path(parts[1]).expanduser()
        key_name = parts[2] if len(parts) > 2 else "default"
        if not path.is_file() or not sig_path.is_file():
            return "[crypto] Both the file and its signature file must exist."
        key_path = self._key_path(key_name)
        if not key_path.exists():
            return f"[crypto] No key named '{key_name}'."
        expected = hmac.new(key_path.read_bytes(), path.read_bytes(), hashlib.sha256).hexdigest()
        actual = sig_path.read_text(encoding="utf-8", errors="replace").strip()
        if hmac.compare_digest(expected, actual):
            return f"[crypto] VALID — {path} matches its signature (key '{key_name}')."
        return f"[crypto] INVALID — {path} does not match {sig_path} under key '{key_name}'."

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
