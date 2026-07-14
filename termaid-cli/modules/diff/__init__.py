"""Diff Module — File and directory comparison via difflib.

Commands (~8):
  /diff text <a> <b>          Unified diff of two inline text blocks
  /diff file <path-a> <path-b>    Unified diff of two files on disk
  /diff dir <path-a> <path-b>     Compare two directory trees (added/removed/changed)
  /diff ratio <a> <b>          Similarity ratio (0-1) between two texts
  /diff words <a> <b>          Word-level diff of two lines
  /diff patch <path> <out>     Write a unified diff of two files to a patch file
  /diff explain                How this module works
"""

import difflib
import os
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class DiffModule(Module):
    name = "diff"
    version = "1.0.0"
    description = "File and directory comparison via difflib"
    author = "termaid"

    def on_load(self):
        for cmd in ["text", "file", "dir", "ratio", "words", "patch", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _split_ab(self, arg: str, sep: str = "|||") -> tuple[str, str] | None:
        """Two blobs of text separated by a literal '|||' on its own line, or
        two whitespace-separated single-line values (no spaces in either)."""
        if sep in arg:
            a, b = arg.split(sep, 1)
            return a.strip("\n"), b.strip("\n")
        parts = arg.split()
        if len(parts) == 2:
            return parts[0], parts[1]
        return None

    @safe
    def cmd_text(self, arg=""):
        """Unified diff of two inline text blocks: /diff text <a> ||| <b>"""
        pair = self._split_ab(arg or "")
        if not pair:
            return "[diff] Usage: /diff text <text-a> ||| <text-b>  (or two single words)"
        a, b = pair
        out = list(difflib.unified_diff(
            a.splitlines(), b.splitlines(), fromfile="a", tofile="b", lineterm=""
        ))
        return "\n".join(out) if out else "[diff] No differences."

    @safe
    def cmd_file(self, arg=""):
        """Unified diff of two files: /diff file <path-a> <path-b>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[diff] Usage: /diff file <path-a> <path-b>"
        pa, pb = Path(parts[0]).expanduser(), Path(parts[1]).expanduser()
        if not pa.exists() or not pb.exists():
            return f"[diff] Missing file: {pa if not pa.exists() else pb}"
        try:
            a = pa.read_text(encoding="utf-8", errors="replace").splitlines()
            b = pb.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception as e:
            return f"[diff] Read failed: {e}"
        out = list(difflib.unified_diff(a, b, fromfile=str(pa), tofile=str(pb), lineterm=""))
        return "\n".join(out) if out else "[diff] Files are identical."

    @safe
    def cmd_dir(self, arg=""):
        """Compare two directory trees: /diff dir <path-a> <path-b>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[diff] Usage: /diff dir <path-a> <path-b>"
        da, db = Path(parts[0]).expanduser(), Path(parts[1]).expanduser()
        if not da.is_dir() or not db.is_dir():
            return "[diff] Both paths must be existing directories."

        files_a = {str(p.relative_to(da)) for p in da.rglob("*") if p.is_file()}
        files_b = {str(p.relative_to(db)) for p in db.rglob("*") if p.is_file()}

        only_a = sorted(files_a - files_b)
        only_b = sorted(files_b - files_a)
        common = sorted(files_a & files_b)

        changed = []
        for rel in common:
            fa, fb = da / rel, db / rel
            try:
                if fa.read_bytes() != fb.read_bytes():
                    changed.append(rel)
            except Exception:
                changed.append(rel)

        lines = [f"[diff] {da} vs {db}"]
        if only_a:
            lines.append(f"\n  Only in {da} ({len(only_a)}):")
            lines += [f"    - {f}" for f in only_a[:50]]
        if only_b:
            lines.append(f"\n  Only in {db} ({len(only_b)}):")
            lines += [f"    - {f}" for f in only_b[:50]]
        if changed:
            lines.append(f"\n  Changed ({len(changed)}):")
            lines += [f"    ~ {f}" for f in changed[:50]]
        if not (only_a or only_b or changed):
            lines.append("\n  Directories are identical.")
        return "\n".join(lines)

    @safe
    def cmd_ratio(self, arg=""):
        """Similarity ratio (0-1): /diff ratio <a> ||| <b>"""
        pair = self._split_ab(arg or "")
        if not pair:
            return "[diff] Usage: /diff ratio <text-a> ||| <text-b>  (or two single words)"
        a, b = pair
        ratio = difflib.SequenceMatcher(None, a, b).ratio()
        return f"[diff] Similarity: {ratio:.3f} ({ratio*100:.1f}%)"

    @safe
    def cmd_words(self, arg=""):
        """Word-level diff of two lines: /diff words <line-a> ||| <line-b>"""
        pair = self._split_ab(arg or "")
        if not pair:
            return "[diff] Usage: /diff words <line-a> ||| <line-b>"
        a, b = pair
        sm = difflib.SequenceMatcher(None, a.split(), b.split())
        out = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                out.append(" ".join(a.split()[i1:i2]))
            elif tag == "delete":
                out.append(f"[-{' '.join(a.split()[i1:i2])}-]")
            elif tag == "insert":
                out.append(f"[+{' '.join(b.split()[j1:j2])}+]")
            elif tag == "replace":
                out.append(f"[-{' '.join(a.split()[i1:i2])}-][+{' '.join(b.split()[j1:j2])}+]")
        return " ".join(out)

    @safe
    def cmd_patch(self, arg=""):
        """Write a unified diff of two files to a patch file: /diff patch <a> <b> <out>"""
        parts = (arg or "").split()
        if len(parts) != 3:
            return "[diff] Usage: /diff patch <path-a> <path-b> <out.patch>"
        pa, pb, out = (Path(p).expanduser() for p in parts)
        if not pa.exists() or not pb.exists():
            return f"[diff] Missing file: {pa if not pa.exists() else pb}"
        a = pa.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        b = pb.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        patch = list(difflib.unified_diff(a, b, fromfile=str(pa), tofile=str(pb)))
        if not patch:
            return "[diff] Files are identical — no patch written."
        out.write_text("".join(patch), encoding="utf-8")
        return f"[diff] Patch written to {out} ({len(patch)} line(s))"

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
