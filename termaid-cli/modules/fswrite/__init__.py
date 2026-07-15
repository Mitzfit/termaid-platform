"""FSWrite Module — Arbitrary file write access, anywhere on disk. DANGEROUS tier.

Built with real, unrestricted write access, as explicitly requested: the
caller (human or AI) supplies file content and a destination path, and this
module writes it there — no bounded template set, no restriction to a
project directory. That's the whole point: placing a config file (or any
other file) wherever it's actually needed, not just inside TermAId's own
data directory.

The one boundary that *does* exist mirrors /selfmod's own carve-out: this
module refuses to touch `backend/policy.py` or `backend/main.py` — the
access-control engine deciding whether this module is even reachable. The
operator already has full filesystem access regardless of what this module
does; the boundary just keeps "arbitrary file write" from also meaning
"rewrite the security tier system gating yourself."

Every overwrite/append/restore backs up the previous file content first
(raw bytes, so binary files survive round-trip too) to
%APPDATA%/termaid/fswrite_backups — see /backup for the general-purpose
version of this pattern, and /selfmod for the module-source-specific one.
Content arrives from the command line, so `write`/`append` take literal text
(preserving internal whitespace/newlines — see `_parse_content_confirm`);
`write-b64` takes base64 for exact-byte/binary content.

Commands (~7):
  /fswrite write <path> <content...> confirm       Write text content (overwrites; backs up first)
  /fswrite write-b64 <path> <base64> confirm          Write exact bytes from base64 (overwrites; backs up first)
  /fswrite append <path> <content...> confirm            Append text content (backs up first if file exists)
  /fswrite mkdir <path> confirm                             Create a directory, including parents
  /fswrite list-backups [filter]                               List backups taken by this module
  /fswrite restore <path> confirm                                 Restore the most recent backup for a path
  /fswrite explain                                                   How this module works
"""

import base64
import binascii
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_MAX_BYTES = 10 * 1024 * 1024  # 10MB — generous for config files, blocks pathological requests


class FSWriteModule(Module):
    name = "fswrite"
    version = "1.0.0"
    description = "Arbitrary file write access anywhere on disk (config files, dotfiles, anything)"
    author = "termaid"

    def on_load(self):
        for cmd in ["write", "write-b64", "append", "mkdir", "list-backups", "restore", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._backup_dir = data_dir / "fswrite_backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

        # repo_root/modules/fswrite/__init__.py -> parents[0]=fswrite, [1]=modules,
        # [2]=termaid-cli, [3]=repo root. Same fixed-parent-dir assumption /selfmod
        # makes about its own layout.
        repo_root = Path(__file__).resolve().parents[3]
        self._denylist = set()
        for rel in ("backend/policy.py", "backend/main.py"):
            try:
                self._denylist.add((repo_root / rel).resolve())
            except OSError:
                pass

    def _sanitize(self, p: Path) -> str:
        s = str(p)
        for ch in (":", "\\", "/"):
            s = s.replace(ch, "_")
        return s

    def _backup(self, target: Path) -> Path:
        # Microsecond-resolution timestamp, plus a collision counter as a last
        # resort — a plain %Y%m%d-%H%M%S timestamp collides (and silently
        # clobbers the earlier backup) when two writes to the same path land
        # in the same second, which a scripted sequence of edits does easily.
        ts = time.strftime("%Y%m%d-%H%M%S") + f"-{int((time.time() % 1) * 1e6):06d}"
        stem = f"{self._sanitize(target)}__{ts}"
        backup_path = self._backup_dir / f"{stem}.bak"
        n = 1
        while backup_path.exists():
            backup_path = self._backup_dir / f"{stem}-{n}.bak"
            n += 1
        backup_path.write_bytes(target.read_bytes())
        return backup_path

    def _check_target(self, path_str: str):
        """Resolve a destination path and reject the two access-control files.
        Returns (Path, None) on success or (None, error-message) on failure."""
        if not (path_str or "").strip():
            return None, "[fswrite] A destination path is required."
        target = Path(path_str).expanduser()
        try:
            target = target.resolve()
        except OSError as e:
            return None, f"[fswrite] Cannot resolve path: {e}"
        if target in self._denylist:
            return None, ("[fswrite] Refusing to write to the access-control engine itself "
                          "(backend/policy.py or backend/main.py) — out of scope for this module.")
        return target, None

    def _parse_content_confirm(self, arg: str):
        """Split '<path> <content...> confirm' preserving internal whitespace/
        newlines in content (unlike a plain .split()). Returns (path_str, content)
        or None if the path or trailing 'confirm' token is missing."""
        parts = (arg or "").split(None, 1)
        if len(parts) < 2:
            return None
        path_str, rest = parts
        rest = rest.rstrip()
        if not rest.lower().endswith("confirm"):
            return None
        content = rest[: -len("confirm")].rstrip()
        return path_str, content

    @safe
    def cmd_write(self, arg=""):
        """Write text content to a path, creating parent dirs (overwrites; confirms):
        /fswrite write <path> <content...> confirm"""
        parsed = self._parse_content_confirm(arg)
        if parsed is None:
            return "[fswrite] Usage: /fswrite write <path> <content...> confirm"
        path_str, content = parsed
        target, err = self._check_target(path_str)
        if err:
            return err
        data = content.encode("utf-8")
        if len(data) > _MAX_BYTES:
            return f"[fswrite] Content too large ({len(data):,} bytes, max {_MAX_BYTES:,})."
        backup_path = self._backup(target) if target.is_file() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        msg = f"[fswrite] Wrote {target} ({len(data):,} bytes)."
        if backup_path:
            msg += f" Backed up previous version to {backup_path.name}."
        return msg

    @safe
    def cmd_write_b64(self, arg=""):
        """Write exact bytes from base64 content (overwrites; confirms):
        /fswrite write-b64 <path> <base64-content> confirm"""
        parts = (arg or "").split()
        if len(parts) != 3 or parts[-1].lower() != "confirm":
            return "[fswrite] Usage: /fswrite write-b64 <path> <base64-content> confirm"
        path_str, b64 = parts[0], parts[1]
        target, err = self._check_target(path_str)
        if err:
            return err
        try:
            data = base64.b64decode(b64, validate=True)
        except (binascii.Error, ValueError) as e:
            return f"[fswrite] Invalid base64 content: {e}"
        if len(data) > _MAX_BYTES:
            return f"[fswrite] Content too large ({len(data):,} bytes, max {_MAX_BYTES:,})."
        backup_path = self._backup(target) if target.is_file() else None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        msg = f"[fswrite] Wrote {target} ({len(data):,} bytes)."
        if backup_path:
            msg += f" Backed up previous version to {backup_path.name}."
        return msg

    @safe
    def cmd_append(self, arg=""):
        """Append text content to a path, creating it if missing (confirms):
        /fswrite append <path> <content...> confirm"""
        parsed = self._parse_content_confirm(arg)
        if parsed is None:
            return "[fswrite] Usage: /fswrite append <path> <content...> confirm"
        path_str, content = parsed
        target, err = self._check_target(path_str)
        if err:
            return err
        data = content.encode("utf-8")
        backup_path = None
        if target.is_file():
            if target.stat().st_size + len(data) > _MAX_BYTES:
                return f"[fswrite] Resulting file would be too large (max {_MAX_BYTES:,} bytes)."
            backup_path = self._backup(target)
        elif len(data) > _MAX_BYTES:
            return f"[fswrite] Content too large ({len(data):,} bytes, max {_MAX_BYTES:,})."
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "ab") as f:
            f.write(data)
        msg = f"[fswrite] Appended {len(data):,} bytes to {target}."
        if backup_path:
            msg += f" Backed up previous version to {backup_path.name}."
        return msg

    @safe
    def cmd_mkdir(self, arg=""):
        """Create a directory, including parents (confirms): /fswrite mkdir <path> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[-1].lower() != "confirm":
            return "[fswrite] Usage: /fswrite mkdir <path> confirm"
        target, err = self._check_target(parts[0])
        if err:
            return err
        if target.is_dir():
            return f"[fswrite] Already exists: {target}"
        if target.exists():
            return f"[fswrite] A file already exists at {target} — not a directory."
        target.mkdir(parents=True, exist_ok=True)
        return f"[fswrite] Created directory {target}"

    @safe
    def cmd_list_backups(self, arg=""):
        """List backups taken by this module, optionally filtered: /fswrite list-backups [filter]"""
        filt = (arg or "").strip().lower()
        matches = sorted(self._backup_dir.glob("*.bak"), reverse=True)
        if filt:
            matches = [p for p in matches if filt in p.name.lower()]
        if not matches:
            return "[fswrite] No backups found." + (f" (filter: {filt})" if filt else "")
        lines = [f"[fswrite] {len(matches)} backup(s):"]
        for p in matches[:50]:
            lines.append(f"  {p.name}  ({p.stat().st_size:,} bytes)")
        if len(matches) > 50:
            lines.append(f"  ... and {len(matches) - 50} more")
        return "\n".join(lines)

    @safe
    def cmd_restore(self, arg=""):
        """Restore the most recent backup for a path (confirms): /fswrite restore <path> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[-1].lower() != "confirm":
            return "[fswrite] Usage: /fswrite restore <path> confirm"
        target, err = self._check_target(parts[0])
        if err:
            return err
        matches = sorted(self._backup_dir.glob(f"{self._sanitize(target)}__*.bak"), reverse=True)
        if not matches:
            return f"[fswrite] No backups found for {target}."
        latest = matches[0]
        data = latest.read_bytes()
        # Back up the current (about-to-be-replaced) state too, so a restore is itself reversible.
        if target.is_file():
            self._backup(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"[fswrite] Restored {target} from {latest.name} ({len(data):,} bytes)."

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
