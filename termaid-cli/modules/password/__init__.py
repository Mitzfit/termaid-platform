"""Password Module — Password generation, strength analysis, HIBP breach check.

The HIBP breach check uses the k-anonymity API (only a 5-char SHA-1 prefix is
sent, never the password itself) and needs network access + httpx; it degrades
to a clear error message if unavailable.

Commands (~9):
  /password generate [length]        Random password (letters+digits+symbols)
  /password passphrase [n-words]     Random word-based passphrase
  /password strength <password>      Heuristic strength score + feedback
  /password entropy <password>       Estimated entropy in bits
  /password breach <password>        Have-I-Been-Pwned check (k-anonymity)
  /password policy <password>        Check against a common policy (len/classes)
  /password history                  Recently generated passwords (this session)
  /password clear-history            Clear the in-memory history
  /password explain                  How this module works
"""

import hashlib
import math
import secrets
import string
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_WORDLIST = [
    "amber", "anchor", "bramble", "canyon", "cinder", "cobalt", "cricket",
    "dapple", "ember", "falcon", "flicker", "granite", "harbor", "hazel",
    "juniper", "kestrel", "lantern", "meadow", "nimbus", "opal", "pebble",
    "quartz", "raven", "ripple", "saffron", "silver", "sparrow", "thistle",
    "umbra", "velvet", "willow", "zephyr",
]


def _score_password(pw: str) -> tuple[int, list[str]]:
    """0-100 heuristic strength score + human feedback."""
    score = 0
    notes = []
    length = len(pw)
    score += min(length * 4, 40)
    classes = sum([
        any(c.islower() for c in pw),
        any(c.isupper() for c in pw),
        any(c.isdigit() for c in pw),
        any(not c.isalnum() for c in pw),
    ])
    score += classes * 12
    if length < 8:
        notes.append("Too short — use at least 12 characters")
    if classes < 3:
        notes.append("Mix uppercase, lowercase, digits, and symbols")
    if pw.lower() == pw or pw.upper() == pw:
        notes.append("Single-case passwords are much weaker")
    if len(set(pw)) < length * 0.6:
        score -= 10
        notes.append("Repeated characters reduce effective entropy")
    score = max(0, min(100, score))
    if not notes:
        notes.append("Looks solid")
    return score, notes


def _entropy_bits(pw: str) -> float:
    pool = 0
    if any(c.islower() for c in pw): pool += 26
    if any(c.isupper() for c in pw): pool += 26
    if any(c.isdigit() for c in pw): pool += 10
    if any(not c.isalnum() for c in pw): pool += 32
    if pool == 0:
        return 0.0
    return len(pw) * math.log2(pool)


class PasswordModule(Module):
    name = "password"
    version = "1.0.0"
    description = "Password generation, strength analysis, HIBP breach check"
    author = "termaid"

    def on_load(self):
        for cmd in ["generate", "passphrase", "strength", "entropy",
                    "breach", "policy", "history", "clear-history", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        self._history: list[str] = []

    @safe
    def cmd_generate(self, arg=""):
        """Random password (letters+digits+symbols): /password generate [length]"""
        try:
            length = int((arg or "20").strip())
        except Exception:
            return "[password] Length must be an integer"
        length = max(4, min(length, 256))
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+[]{}"
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        self._history.append(pw)
        score, _ = _score_password(pw)
        return f"[password] {pw}\n  strength: {score}/100"

    @safe
    def cmd_passphrase(self, arg=""):
        """Random word-based passphrase: /password passphrase [n-words]"""
        try:
            n = int((arg or "5").strip())
        except Exception:
            return "[password] Word count must be an integer"
        n = max(3, min(n, 20))
        words = [secrets.choice(_WORDLIST) for _ in range(n)]
        phrase = "-".join(words) + "-" + str(secrets.randbelow(90) + 10)
        self._history.append(phrase)
        return f"[password] {phrase}\n  entropy: ~{_entropy_bits(phrase):.0f} bits"

    @safe
    def cmd_strength(self, arg=""):
        """Heuristic strength score + feedback"""
        pw = arg or ""
        if not pw:
            return "[password] Usage: /password strength <password>"
        score, notes = _score_password(pw)
        lines = [f"[password] Strength: {score}/100"]
        for n in notes:
            lines.append(f"  - {n}")
        return "\n".join(lines)

    @safe
    def cmd_entropy(self, arg=""):
        """Estimated entropy in bits"""
        pw = arg or ""
        if not pw:
            return "[password] Usage: /password entropy <password>"
        bits = _entropy_bits(pw)
        rating = "weak" if bits < 40 else "moderate" if bits < 60 else "strong" if bits < 80 else "very strong"
        return f"[password] ~{bits:.1f} bits of entropy ({rating})"

    @safe
    def cmd_breach(self, arg=""):
        """Have-I-Been-Pwned check (k-anonymity — only a hash prefix leaves this machine)"""
        pw = arg or ""
        if not pw:
            return "[password] Usage: /password breach <password>"
        sha1 = hashlib.sha1(pw.encode("utf-8")).hexdigest().upper()
        prefix, suffix = sha1[:5], sha1[5:]
        try:
            import httpx
        except ImportError:
            return "[password] httpx not installed — cannot query the breach API"
        try:
            with httpx.Client(timeout=8.0) as client:
                resp = client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
                resp.raise_for_status()
        except Exception as e:
            return f"[password] Breach check failed: {e}"
        for line in resp.text.splitlines():
            suf, count = line.split(":")
            if suf == suffix:
                return f"[password] FOUND in {int(count):,} breach(es) — do not use this password"
        return "[password] Not found in known breaches (HIBP)"

    @safe
    def cmd_policy(self, arg=""):
        """Check against a common policy: >=12 chars, 3+ classes, no whitespace"""
        pw = arg or ""
        if not pw:
            return "[password] Usage: /password policy <password>"
        checks = [
            (len(pw) >= 12, "at least 12 characters"),
            (sum([any(c.islower() for c in pw), any(c.isupper() for c in pw),
                  any(c.isdigit() for c in pw), any(not c.isalnum() for c in pw)]) >= 3,
             "at least 3 character classes"),
            (" " not in pw and "\t" not in pw, "no whitespace"),
        ]
        lines = ["[password] Policy check:"]
        all_ok = True
        for ok, desc in checks:
            lines.append(f"  {'PASS' if ok else 'FAIL'}  {desc}")
            all_ok = all_ok and ok
        lines.append(f"\n  Overall: {'meets policy' if all_ok else 'does NOT meet policy'}")
        return "\n".join(lines)

    @safe
    def cmd_history(self, arg=""):
        """Recently generated passwords (this session only, never persisted)"""
        if not self._history:
            return "[password] No passwords generated this session."
        lines = [f"[password] {len(self._history)} generated this session:"]
        for pw in self._history[-20:]:
            lines.append(f"  {pw}")
        return "\n".join(lines)

    @safe
    def cmd_clear_history(self, arg=""):
        """Clear the in-memory history"""
        n = len(self._history)
        self._history.clear()
        return f"[password] Cleared {n} entr{'y' if n == 1 else 'ies'} from history."

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
