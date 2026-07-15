"""Verify Module — File integrity verification against known checksums.

Distinct from /filetools hash (which just computes and prints a hash):
this compares against an *expected* value and gives a clear match/mismatch
verdict. `checksum`/`sidecar` check one file at a time; `batch` checks
many at once against a manifest; `generate-sidecar` is the write-side
complement to `sidecar` (creates the checksum file instead of reading
one); `compare-dirs` verifies two whole trees are identical, useful right
after a /sync or /backup.

Commands (~5):
  /verify checksum <path> <expected_hash> [algo]     Compare against a given hash
  /verify sidecar <path>                                Compare against a <path>.<algo> sidecar file
  /verify generate-sidecar <path> [algo]                   Create a <path>.<algo> checksum file
  /verify batch <manifest_path> [algo]                        Verify many files against a manifest
  /verify compare-dirs <dir1> <dir2>                             Confirm two trees are byte-identical
  /verify explain                                                   How this module works
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
    version = "1.1.0"
    description = "File integrity verification against known checksums"
    author = "termaid"

    def on_load(self):
        for cmd in ["checksum", "sidecar", "generate-sidecar", "batch", "compare-dirs", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

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
    def cmd_generate_sidecar(self, arg=""):
        """Create a <path>.<algo> checksum file: /verify generate-sidecar <path> [algo]"""
        parts = (arg or "").split()
        if not parts:
            return "[verify] Usage: /verify generate-sidecar <path> [md5|sha1|sha256|sha512]"
        path = parts[0]
        algo = parts[1].lower() if len(parts) > 1 else "sha256"
        if algo not in _HASH_ALGOS:
            return f"[verify] Unknown algorithm '{algo}'. Choose from: {', '.join(sorted(_HASH_ALGOS))}"
        p = Path(path).expanduser()
        if not p.is_file():
            return f"[verify] Not found: {p}"
        digest = _hash_file(p, algo)
        sidecar = p.with_name(p.name + "." + algo)
        sidecar.write_text(f"{digest}  {p.name}\n", encoding="utf-8")
        return f"[verify] Created {sidecar.name} ({algo}: {digest})"

    @safe
    def cmd_batch(self, arg=""):
        """Verify many files against a manifest: /verify batch <manifest_path> [algo]

        Manifest format: one "<hash>  <relative-or-absolute-path>" pair per line
        (the same format `sha256sum`/`certutil -hashfile` output uses), relative
        paths resolved against the manifest's own directory."""
        parts = (arg or "").split()
        if not parts:
            return "[verify] Usage: /verify batch <manifest_path> [algo]"
        manifest_path = Path(parts[0]).expanduser()
        algo = parts[1].lower() if len(parts) > 1 else "sha256"
        if algo not in _HASH_ALGOS:
            return f"[verify] Unknown algorithm '{algo}'. Choose from: {', '.join(sorted(_HASH_ALGOS))}"
        if not manifest_path.is_file():
            return f"[verify] Manifest not found: {manifest_path}"

        base = manifest_path.parent
        matched, mismatched, missing = 0, [], []
        for line in manifest_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            tokens = line.split(None, 1)
            if len(tokens) != 2:
                continue
            expected, rel = tokens
            target = Path(rel)
            if not target.is_absolute():
                target = base / rel
            if not target.is_file():
                missing.append(rel)
                continue
            actual = _hash_file(target, algo)
            if actual.lower() == expected.lower():
                matched += 1
            else:
                mismatched.append(rel)

        lines = [f"[verify] Batch check against {manifest_path.name} ({algo}):",
                f"  Matched:    {matched}",
                f"  Mismatched: {len(mismatched)}",
                f"  Missing:    {len(missing)}"]
        for rel in mismatched[:20]:
            lines.append(f"    MISMATCH  {rel}")
        for rel in missing[:20]:
            lines.append(f"    MISSING   {rel}")
        return "\n".join(lines)

    @safe
    def cmd_compare_dirs(self, arg=""):
        """Confirm two trees are byte-identical: /verify compare-dirs <dir1> <dir2>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[verify] Usage: /verify compare-dirs <dir1> <dir2>"
        dir1 = Path(parts[0]).expanduser().resolve()
        dir2 = Path(parts[1]).expanduser().resolve()
        if not dir1.is_dir() or not dir2.is_dir():
            return "[verify] Both paths must be existing directories."

        def _safe_files(root):
            rels = set()
            for f in root.rglob("*"):
                try:
                    if f.is_file():
                        rels.add(f.relative_to(root))
                except OSError:
                    continue
            return rels

        rels1 = _safe_files(dir1)
        rels2 = _safe_files(dir2)
        only_in_1 = rels1 - rels2
        only_in_2 = rels2 - rels1
        common = rels1 & rels2

        mismatched = []
        for rel in common:
            try:
                if _hash_file(dir1 / rel, "sha256") != _hash_file(dir2 / rel, "sha256"):
                    mismatched.append(str(rel))
            except OSError:
                mismatched.append(str(rel))

        if not only_in_1 and not only_in_2 and not mismatched:
            return f"[verify] {dir1} and {dir2} are identical — {len(common)} file(s) checked."

        lines = [f"[verify] {dir1} vs {dir2}:"]
        if only_in_1:
            lines.append(f"  Only in {dir1.name} ({len(only_in_1)}): " + ", ".join(sorted(str(r) for r in only_in_1)[:10]))
        if only_in_2:
            lines.append(f"  Only in {dir2.name} ({len(only_in_2)}): " + ", ".join(sorted(str(r) for r in only_in_2)[:10]))
        if mismatched:
            lines.append(f"  Content differs ({len(mismatched)}):")
            for rel in mismatched[:20]:
                lines.append(f"    {rel}")
        return "\n".join(lines)

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
