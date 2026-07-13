"""
secrets.py — keep provider API keys out of .env by using the OS keychain.

Uses the `keyring` library, which targets the native secret store on each OS:
  • Windows  → Credential Manager
  • macOS    → Keychain
  • Linux    → Secret Service (GNOME Keyring / KWallet)

Headless boxes and Termux often have NO keyring backend. That's fine: every
function degrades gracefully to environment variables, so the app keeps working
— it just isn't using the secure store. `keyring_available()` tells you which
you're getting.

CLI:
    python -m backend.secrets set GEMINI_API_KEY
    python -m backend.secrets get GEMINI_API_KEY
    python -m backend.secrets list
    python -m backend.secrets delete GEMINI_API_KEY
"""

from __future__ import annotations

import os
import sys

SERVICE = "termaid"

# Provider key names we hydrate into the environment at startup so BOTH the
# streaming path and the CLI's own provider code can see them.
KNOWN_KEYS = [
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "GROQ_API_KEY", "CEREBRAS_API_KEY",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY",
    "XAI_API_KEY", "TOGETHER_API_KEY", "FIREWORKS_API_KEY", "DEEPINFRA_API_KEY",
]

try:
    import keyring
    from keyring.errors import KeyringError
    _HAVE_KEYRING = True
except Exception:  # pragma: no cover - keyring not installed
    keyring = None  # type: ignore
    KeyringError = Exception  # type: ignore
    _HAVE_KEYRING = False


def keyring_available() -> bool:
    """True only if keyring is installed AND a usable backend is present."""
    if not _HAVE_KEYRING:
        return False
    try:
        backend = keyring.get_keyring()
        # The 'fail' / 'null' backends mean no real store is available.
        name = backend.__class__.__name__.lower()
        return "fail" not in name and "null" not in name
    except Exception:
        return False


def get_secret(name: str) -> str | None:
    """Keychain first, then environment. Never raises."""
    if keyring_available():
        try:
            val = keyring.get_password(SERVICE, name)
            if val:
                return val
        except KeyringError:
            pass
    return os.environ.get(name) or None


def set_secret(name: str, value: str) -> bool:
    if keyring_available():
        try:
            keyring.set_password(SERVICE, name, value)
            return True
        except KeyringError:
            pass
    return False


def delete_secret(name: str) -> bool:
    if keyring_available():
        try:
            keyring.delete_password(SERVICE, name)
            return True
        except KeyringError:
            pass
    return False


def hydrate_env() -> int:
    """Copy known secrets from the keychain into os.environ (without clobbering
    values already set explicitly). Returns how many were loaded."""
    loaded = 0
    if not keyring_available():
        return 0
    for key in KNOWN_KEYS:
        if os.environ.get(key):
            continue
        val = get_secret(key)
        if val:
            os.environ[key] = val
            loaded += 1
    return loaded


# --------------------------------------------------------------------------- #
def _cli() -> int:
    import argparse
    import getpass

    p = argparse.ArgumentParser(prog="python -m backend.secrets")
    sub = p.add_subparsers(dest="cmd", required=True)
    for c in ("get", "set", "delete"):
        sp = sub.add_parser(c)
        sp.add_argument("name")
    sub.add_parser("list")
    sub.add_parser("status")
    args = p.parse_args()

    if not keyring_available():
        print("⚠  no OS keychain backend available — falling back to env vars.")
        print("   (On Termux/headless Linux this is expected; use a .env or "
              "`pip install keyrings.alt` for an encrypted file store.)")

    if args.cmd == "status":
        print(f"keyring available: {keyring_available()}")
    elif args.cmd == "get":
        print(get_secret(args.name) or "(not set)")
    elif args.cmd == "set":
        value = getpass.getpass(f"value for {args.name}: ")
        print("stored in keychain" if set_secret(args.name, value)
              else "could not store (no backend) — set it as an env var instead")
    elif args.cmd == "delete":
        print("deleted" if delete_secret(args.name) else "nothing to delete")
    elif args.cmd == "list":
        for k in KNOWN_KEYS:
            mark = "✓" if get_secret(k) else "·"
            print(f"  {mark} {k}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
