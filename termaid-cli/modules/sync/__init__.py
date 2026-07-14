"""Sync Module — One-way directory sync by size + mtime comparison.

Deliberately not a wrapper around rsync/robocopy (availability varies too
much cross-platform) — a small stdlib-only comparison that copies files
from src to dst when the dst is missing, smaller, or older. Never deletes
anything from dst that isn't present in src (that would need a separate,
more dangerous "mirror" mode this module doesn't implement). `diff` is a
dry run; `run` requires confirmation before copying.

Commands (~3):
  /sync diff <src> <dst>         Dry run: what would be copied
  /sync run <src> <dst> confirm    Actually copy the differing files
  /sync explain                      How this module works
"""

import shutil
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class SyncModule(Module):
    name = "sync"
    version = "1.0.0"
    description = "One-way directory sync by size + mtime comparison"
    author = "termaid"

    def on_load(self):
        for cmd in ["diff", "run", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _plan(self, src: Path, dst: Path):
        to_copy = []
        for f in src.rglob("*"):
            if not f.is_file():
                continue
            rel = f.relative_to(src)
            target = dst / rel
            if not target.exists():
                to_copy.append((f, target, "new"))
            else:
                sstat, tstat = f.stat(), target.stat()
                if sstat.st_size != tstat.st_size or sstat.st_mtime > tstat.st_mtime + 1:
                    to_copy.append((f, target, "updated"))
        return to_copy

    def _parse_args(self, arg: str):
        parts = (arg or "").split()
        if len(parts) < 2:
            return None
        return Path(parts[0]).expanduser().resolve(), Path(parts[1]).expanduser().resolve()

    @safe
    def cmd_diff(self, arg=""):
        """Dry run: what would be copied: /sync diff <src> <dst>"""
        parsed = self._parse_args(arg)
        if not parsed:
            return "[sync] Usage: /sync diff <src> <dst>"
        src, dst = parsed
        if not src.is_dir():
            return f"[sync] Not a directory: {src}"
        plan = self._plan(src, dst)
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
        """Actually copy the differing files (confirms): /sync run <src> <dst> confirm"""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[sync] Usage: /sync run <src> <dst> confirm"
        src = Path(parts[0]).expanduser().resolve()
        dst = Path(parts[1]).expanduser().resolve()
        if not src.is_dir():
            return f"[sync] Not a directory: {src}"
        plan = self._plan(src, dst)
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
