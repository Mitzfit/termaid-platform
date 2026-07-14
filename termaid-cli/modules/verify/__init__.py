"""Verify Module — File integrity verification against a known checksum.

Distinct from /filetools hash (which just computes and prints a hash):
this compares against an *expected* value and gives a clear match/mismatch
verdict — either passed inline or read from a `<file>.sha256` / `.sha1` /
`.md5` sidecar file if one exists next to the target, the common
convention for download checksums.

Commands (~2):
  /verify checksum <path> <expected_hash> [algo]     Compare against a given hash
  /verify sidecar <path>                                Compare against a <path>.<algo> sidecar file
  /verify explain                                          How this module works
"""

import hashlib
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_HASH_ALGOS = {"md5", "sha1", "sha256", "sha512"}


def _hash_file(p: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class VerifyModule(Module):
    name = "verify"
    version = "1.0.0"
    description = "File integrity verification against a known checksum"
    author = "termaid"

    def on_load(self):
        for cmd in ["checksum", "sidecar", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_checksum(self, arg=""):
        """Compare against a given hash: /verify checksum <path> <expected_hash> [algo]"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[verify] Usage: /verify checksum <path> <expected_hash> [md5|sha1|sha256|sha512]"
        path, expected = parts[0], parts[1].strip().lower()
        algo = parts[2].lower() if len(parts) > 2 else {32: "md5", 40: "sha1", 64: "sha256",
                                                          128: "sha512"}.get(len(expected), "sha256")
        if algo not in _HASH_ALGOS:
            return f"[verify] Unknown algorithm '{algo}'. Choose from: {', '.join(sorted(_HASH_ALGOS))}"
        p = Path(path).expanduser()
        if not p.is_file():
            return f"[verify] Not found: {p}"
        actual = _hash_file(p, algo)
        if actual == expected:
            return f"[verify] MATCH — {p.name} ({algo}) matches the expected checksum."
        return (f"[verify] MISMATCH — {p.name} ({algo})\n"
                f"  expected: {expected}\n"
                f"  actual:   {actual}")

    @safe
    def cmd_sidecar(self, arg=""):
        """Compare against a <path>.<algo> sidecar file: /verify sidecar <path>"""
        path = (arg or "").strip()
        if not path:
            return "[verify] Usage: /verify sidecar <path>"
        p = Path(path).expanduser()
        if not p.is_file():
            return f"[verify] Not found: {p}"
        for algo in ("sha256", "sha512", "sha1", "md5"):
            sidecar = p.with_name(p.name + "." + algo)
            if sidecar.is_file():
                expected_line = sidecar.read_text(encoding="utf-8", errors="replace").strip().split()
                if not expected_line:
                    continue
                expected = expected_line[0].lower()
                actual = _hash_file(p, algo)
                if actual == expected:
                    return f"[verify] MATCH — {p.name} matches {sidecar.name}"
                return (f"[verify] MISMATCH — {p.name} vs {sidecar.name}\n"
                        f"  expected: {expected}\n"
                        f"  actual:   {actual}")
        return f"[verify] No sidecar checksum file found next to {p} (looked for .sha256/.sha512/.sha1/.md5)"

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
