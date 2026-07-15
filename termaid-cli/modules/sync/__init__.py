"""Sync Module — One-way/two-way directory sync by size + mtime comparison.

Deliberately not a wrapper around rsync/robocopy (availability varies too
much cross-platform) — a small stdlib-only comparison that copies files
when one side is missing, smaller, or older than the other. One-way sync
never deletes anything from dst that isn't present in src. Two-way sync
copies in whichever direction is newer per file and reports (without
guessing) any file changed on both sides since they'd otherwise agree —
that's a conflict, not something to silently resolve. `diff`/`verify` are
read-only; `run`/`two-way` require confirmation before touching anything.

Commands (~5):
  /sync diff <src> <dst> [exclude-glob,...]         Dry run: what would be copied
  /sync run <src> <dst> [exclude-glob,...] confirm     Actually copy the differing files
  /sync verify <src> <dst>                               Confirm src/dst are byte-identical (post-sync check)
  /sync two-way <dir1> <dir2> confirm                       Sync newer-wins both directions, flags conflicts
  /sync explain                                                How this module works
"""

import fnmatch
import hashlib
import shutil
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _excluded(rel_path: Path, patterns: list) -> bool:
    s = str(rel_path)
    return any(fnmatch.fnmatch(s, pat) or fnmatch.fnmatch(rel_path.name, pat) for pat in patterns)


def _hash_file(p: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class SyncModule(Module):
    name = "sync"
    version = "1.1.0"
    description = "One-way/two-way directory sync by size + mtime comparison"
    author = "termaid"

    def on_load(self):
        for cmd in ["diff", "run", "verify", "two-way", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    def _plan(self, src: Path, dst: Path, patterns: list):
        to_copy = []
        for f in src.rglob("*"):
            try:
                if not f.is_file():
                    continue
                rel = f.relative_to(src)
                if patterns and _excluded(rel, patterns):
                    continue
                target = dst / rel
                if not target.exists():
                    to_copy.append((f, target, "new"))
                else:
                    sstat, tstat = f.stat(), target.stat()
                    if sstat.st_size != tstat.st_size or sstat.st_mtime > tstat.st_mtime + 1:
                        to_copy.append((f, target, "updated"))
            except OSError:
                continue
        return to_copy

    def _parse_args(self, arg: str):
        parts = (arg or "").split()
        if len(parts) < 2:
            return None, None, None
        src = Path(parts[0]).expanduser().resolve()
        dst = Path(parts[1]).expanduser().resolve()
        patterns = parts[2].split(",") if len(parts) > 2 and parts[2].lower() != "confirm" else []
        return src, dst, patterns

    @safe
    def cmd_diff(self, arg=""):
        """Dry run: what would be copied: /sync diff <src> <dst> [exclude-glob,...]"""
        src, dst, patterns = self._parse_args(arg)
        if src is None:
            return "[sync] Usage: /sync diff <src> <dst> [exclude-glob,...] (e.g. *.log,node_modules/*)"
        if not src.is_dir():
            return f"[sync] Not a directory: {src}"
        plan = self._plan(src, dst, patterns)
        if not plan:
            return f"[sync] {dst} is already up to date with {src}."
        lines = [f"[sync] {len(plan)} file(s) would be copied {src} -> {dst}:"]
        for f, target, reason in plan[:50]:
            lines.append(f"  {reason:8s} {f.relative_to(src)}")
        if len(plan) > 50:
            lines.append(f"  ... and {len(plan) - 50} more")
        lines.append("\n  Re-run as: /sync run " + str(src) + " " + str(dst) + " confirm")
        return "\n".join(lines)

    @safe
    def cmd_run(self, arg=""):
        """Actually copy the differing files (confirms): /sync run <src> <dst> [exclude-glob,...] confirm"""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[sync] Usage: /sync run <src> <dst> [exclude-glob,...] confirm"
        src = Path(parts[0]).expanduser().resolve()
        dst = Path(parts[1]).expanduser().resolve()
        patterns = parts[2].split(",") if len(parts) == 4 else []
        if not src.is_dir():
            return f"[sync] Not a directory: {src}"
        plan = self._plan(src, dst, patterns)
        if not plan:
            return f"[sync] {dst} is already up to date with {src}."
        copied = 0
        for f, target, _ in plan:
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, target)
                copied += 1
            except Exception:
                pass
        return f"[sync] Copied {copied}/{len(plan)} file(s) {src} -> {dst}"

    @safe
    def cmd_verify(self, arg=""):
        """Confirm src/dst are byte-identical (post-sync check): /sync verify <src> <dst>"""
        src, dst, _ = self._parse_args(arg)
        if src is None:
            return "[sync] Usage: /sync verify <src> <dst>"
        if not src.is_dir() or not dst.is_dir():
            return "[sync] Both src and dst must be existing directories."
        mismatches = []
        checked = 0
        for f in src.rglob("*"):
            try:
                if not f.is_file():
                    continue
                rel = f.relative_to(src)
                target = dst / rel
                if not target.is_file():
                    mismatches.append(f"missing in dst: {rel}")
                    continue
            except OSError:
                continue
            checked += 1
            if _hash_file(f) != _hash_file(target):
                mismatches.append(f"content differs: {rel}")
        if not mismatches:
            return f"[sync] Verified — all {checked} file(s) in {src} match {dst} byte-for-byte."
        lines = [f"[sync] {len(mismatches)} mismatch(es) out of {checked + len(mismatches)} checked:"]
        for m in mismatches[:50]:
            lines.append(f"  {m}")
        return "\n".join(lines)

    @safe
    def cmd_two_way(self, arg=""):
        """Sync newer-wins both directions, flags conflicts (confirms): /sync two-way <dir1> <dir2> confirm"""
        parts = (arg or "").split()
        if len(parts) != 3 or parts[-1].lower() != "confirm":
            return "[sync] Usage: /sync two-way <dir1> <dir2> confirm"
        dir1 = Path(parts[0]).expanduser().resolve()
        dir2 = Path(parts[1]).expanduser().resolve()
        if not dir1.is_dir() or not dir2.is_dir():
            return "[sync] Both directories must already exist."

        rels = set()
        for f in dir1.rglob("*"):
            try:
                if f.is_file():
                    rels.add(f.relative_to(dir1))
            except OSError:
                continue
        for f in dir2.rglob("*"):
            try:
                if f.is_file():
                    rels.add(f.relative_to(dir2))
            except OSError:
                continue

        copied_to_2, copied_to_1, conflicts = 0, 0, []
        for rel in rels:
            p1, p2 = dir1 / rel, dir2 / rel
            try:
                e1, e2 = p1.is_file(), p2.is_file()
                if e1 and not e2:
                    p2.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p1, p2)
                    copied_to_2 += 1
                elif e2 and not e1:
                    p1.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(p2, p1)
                    copied_to_1 += 1
                else:
                    s1, s2 = p1.stat(), p2.stat()
                    if s1.st_size == s2.st_size and abs(s1.st_mtime - s2.st_mtime) < 2:
                        continue
                    if s1.st_mtime > s2.st_mtime + 2:
                        shutil.copy2(p1, p2)
                        copied_to_2 += 1
                    elif s2.st_mtime > s1.st_mtime + 2:
                        shutil.copy2(p2, p1)
                        copied_to_1 += 1
                    else:
                        conflicts.append(str(rel))
            except Exception:
                conflicts.append(f"{rel} (error during copy)")

        lines = [f"[sync] two-way {dir1} <-> {dir2}:",
                f"  Copied {dir1.name} -> {dir2.name}: {copied_to_2}",
                f"  Copied {dir2.name} -> {dir1.name}: {copied_to_1}"]
        if conflicts:
            lines.append(f"  Conflicts (same mtime, different content — not resolved automatically):")
            for c in conflicts[:20]:
                lines.append(f"    {c}")
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
