"""CyberChef Module — Local data-transform/decode operations. SAFE tier.

Covers the CyberChef "recipe" operations this codebase doesn't already
have: /text already has base64 and ROT13, so those aren't duplicated here.
Everything here is pure computation on the input you give it — no network
calls, no file access, no host interaction — which is exactly why it's
SAFE tier rather than SYSTEM. `magic` is the one operation that tries
several decodings automatically (CyberChef's own signature feature) but
it still only ever operates on the string you passed in.

Commands (~10):
  /cyberchef hex <encode|decode> <text>       Hex <-> raw bytes
  /cyberchef url <encode|decode> <text>         URL percent-encoding
  /cyberchef html <encode|decode> <text>          HTML entity encoding
  /cyberchef xor <key> <text>                       XOR with a hex or text key (output hex)
  /cyberchef gzip <compress|decompress> <text>        Gzip, base64-wrapped for text safety
  /cyberchef hash <algo> <text>                         md5/sha1/sha256/sha512/sha3_256 of text
  /cyberchef jwt-decode <token>                           Decode a JWT's header+payload (no verify)
  /cyberchef timestamp <to|from> <value>                    Unix epoch <-> ISO 8601
  /cyberchef magic <text>                                     Try to auto-detect + decode
  /cyberchef explain                                             How this module works
"""

import base64
import gzip
import hashlib
import html
import json
import urllib.parse
from datetime import datetime, timezone
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_HASH_ALGOS = {"md5", "sha1", "sha256", "sha512", "sha3_256"}


class CyberChefModule(Module):
    name = "cyberchef"
    version = "1.0.0"
    description = "Local data-transform/decode operations (CyberChef-style recipes)"
    author = "termaid"

    def on_load(self):
        for cmd in ["hex", "url", "html", "xor", "gzip", "hash", "jwt-decode", "timestamp", "magic", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_hex(self, arg=""):
        """Hex <-> raw bytes: /cyberchef hex <encode|decode> <text>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[cyberchef] Usage: /cyberchef hex <encode|decode> <text>"
        mode, text = parts
        try:
            if mode == "encode":
                return f"[cyberchef] {text.encode('utf-8').hex()}"
            elif mode == "decode":
                return f"[cyberchef] {bytes.fromhex(text.replace(' ', '')).decode('utf-8', errors='replace')}"
        except Exception as e:
            return f"[cyberchef] Failed: {e}"
        return "[cyberchef] Usage: /cyberchef hex <encode|decode> <text>"

    @safe
    def cmd_url(self, arg=""):
        """URL percent-encoding: /cyberchef url <encode|decode> <text>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[cyberchef] Usage: /cyberchef url <encode|decode> <text>"
        mode, text = parts
        if mode == "encode":
            return f"[cyberchef] {urllib.parse.quote(text)}"
        elif mode == "decode":
            return f"[cyberchef] {urllib.parse.unquote(text)}"
        return "[cyberchef] Usage: /cyberchef url <encode|decode> <text>"

    @safe
    def cmd_html(self, arg=""):
        """HTML entity encoding: /cyberchef html <encode|decode> <text>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[cyberchef] Usage: /cyberchef html <encode|decode> <text>"
        mode, text = parts
        if mode == "encode":
            return f"[cyberchef] {html.escape(text)}"
        elif mode == "decode":
            return f"[cyberchef] {html.unescape(text)}"
        return "[cyberchef] Usage: /cyberchef html <encode|decode> <text>"

    @safe
    def cmd_xor(self, arg=""):
        """XOR with a hex or text key, output hex: /cyberchef xor <key> <text>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[cyberchef] Usage: /cyberchef xor <key> <text>"
        key_s, text = parts
        try:
            key = bytes.fromhex(key_s)
        except ValueError:
            key = key_s.encode("utf-8")
        if not key:
            return "[cyberchef] Key can't be empty"
        data = text.encode("utf-8")
        out = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
        return f"[cyberchef] {out.hex()}"

    @safe
    def cmd_gzip(self, arg=""):
        """Gzip, base64-wrapped for text safety: /cyberchef gzip <compress|decompress> <text>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[cyberchef] Usage: /cyberchef gzip <compress|decompress> <text>"
        mode, text = parts
        try:
            if mode == "compress":
                compressed = gzip.compress(text.encode("utf-8"))
                return f"[cyberchef] {base64.b64encode(compressed).decode('ascii')}"
            elif mode == "decompress":
                raw = base64.b64decode(text)
                return f"[cyberchef] {gzip.decompress(raw).decode('utf-8', errors='replace')}"
        except Exception as e:
            return f"[cyberchef] Failed: {e}"
        return "[cyberchef] Usage: /cyberchef gzip <compress|decompress> <text>"

    @safe
    def cmd_hash(self, arg=""):
        """md5/sha1/sha256/sha512/sha3_256 of text: /cyberchef hash <algo> <text>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return f"[cyberchef] Usage: /cyberchef hash <{'|'.join(sorted(_HASH_ALGOS))}> <text>"
        algo, text = parts[0].lower(), parts[1]
        if algo not in _HASH_ALGOS:
            return f"[cyberchef] Unknown algorithm. Choose from: {', '.join(sorted(_HASH_ALGOS))}"
        digest = hashlib.new(algo, text.encode("utf-8")).hexdigest()
        return f"[cyberchef] {algo}({text!r}) = {digest}"

    @safe
    def cmd_jwt_decode(self, arg=""):
        """Decode a JWT's header+payload, no signature verification: /cyberchef jwt-decode <token>"""
        token = (arg or "").strip()
        parts = token.split(".")
        if len(parts) != 3:
            return "[cyberchef] Not a JWT (expected header.payload.signature)"
        def _b64url_json(segment):
            padded = segment + "=" * (-len(segment) % 4)
            return json.loads(base64.urlsafe_b64decode(padded))
        try:
            header = _b64url_json(parts[0])
            payload = _b64url_json(parts[1])
        except Exception as e:
            return f"[cyberchef] Failed to decode: {e}"
        return (f"[cyberchef] Header:  {json.dumps(header, indent=2)}\n"
                f"[cyberchef] Payload: {json.dumps(payload, indent=2)}\n"
                f"[cyberchef] (signature NOT verified — this only decodes, it doesn't validate authenticity)")

    @safe
    def cmd_timestamp(self, arg=""):
        """Unix epoch <-> ISO 8601: /cyberchef timestamp <to|from> <value>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[cyberchef] Usage: /cyberchef timestamp <to|from> <value>\n  to <ISO date>: date -> epoch\n  from <epoch>: epoch -> date"
        mode, value = parts
        try:
            if mode == "to":
                dt = datetime.fromisoformat(value.strip())
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return f"[cyberchef] {int(dt.timestamp())}"
            elif mode == "from":
                dt = datetime.fromtimestamp(float(value.strip()), tz=timezone.utc)
                return f"[cyberchef] {dt.isoformat()}"
        except Exception as e:
            return f"[cyberchef] Failed: {e}"
        return "[cyberchef] Usage: /cyberchef timestamp <to|from> <value>"

    @safe
    def cmd_magic(self, arg=""):
        """Try to auto-detect + decode: /cyberchef magic <text>"""
        text = (arg or "").strip()
        if not text:
            return "[cyberchef] Usage: /cyberchef magic <text>"
        findings = []

        try:
            padded = text + "=" * (-len(text) % 4)
            decoded = base64.b64decode(padded, validate=True).decode("utf-8")
            if decoded.isprintable():
                findings.append(f"Base64 decode: {decoded!r}")
        except Exception:
            pass

        if all(c in "0123456789abcdefABCDEF " for c in text) and len(text.replace(" ", "")) % 2 == 0:
            try:
                decoded = bytes.fromhex(text.replace(" ", "")).decode("utf-8")
                if decoded.isprintable():
                    findings.append(f"Hex decode: {decoded!r}")
            except Exception:
                pass

        if "%" in text:
            try:
                decoded = urllib.parse.unquote(text)
                if decoded != text:
                    findings.append(f"URL decode: {decoded!r}")
            except Exception:
                pass

        if text.count(".") == 2:
            jwt_result = self.cmd_jwt_decode(text)
            if not jwt_result.startswith("[cyberchef] Not a JWT") and not jwt_result.startswith("[cyberchef] Failed"):
                findings.append("Looks like a JWT — see /cyberchef jwt-decode for full output")

        if not findings:
            return f"[cyberchef] No obvious encoding detected for {text!r}."
        return "[cyberchef] Possible interpretations:\n" + "\n".join(f"  - {f}" for f in findings)

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
