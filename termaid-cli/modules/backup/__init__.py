"""Backup Module — Zip-based backup + restore with a manifest.

Creates timestamped zip archives of a file or directory under TermAId's
own data dir (not scattered next to the source), and tracks them in a
manifest so /backup list and /backup restore can refer to them by label
instead of a full path. Restore extracts into a target directory and
confirms first since it can silently overwrite files there.

Commands (~4):
  /backup create <path> [label]           Zip a file/dir, tracked by label
  /backup list                              Show all tracked backups
  /backup restore <label> <outdir> confirm    Extract a backup
  /backup explain                               How this module works
"""

import json
import os
import sys
import time
import zipfile
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


class BackupModule(Module):
    name = "backup"
    version = "1.0.0"
    description = "Zip-based backup + restore with a manifest"
    author = "termaid"

    def on_load(self):
        for cmd in ["create", "list", "restore", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "backups"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._dir / "manifest.json"
        self._manifest = self._load_manifest()

    def _load_manifest(self) -> dict:
        if self._manifest_path.exists():
            try:
                return json.loads(self._manifest_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_manifest(self):
        self._manifest_path.write_text(json.dumps(self._manifest, indent=2), encoding="utf-8")

    @safe
    def cmd_create(self, arg=""):
        """Zip a file/dir, tracked by label: /backup create <path> [label]"""
        parts = (arg or "").split(maxsplit=1)
        if not parts:
            return "[backup] Usage: /backup create <path> [label]"
        src = Path(parts[0]).expanduser().resolve()
        if not src.exists():
            return f"[backup] Not found: {src}"
        label = parts[1].strip() if len(parts) > 1 else src.name
        safe_label = "".join(c if c.isalnum() or c in "-_." else "_" for c in label)
        ts = time.strftime("%Y%m%d-%H%M%S")
        archive_name = f"{safe_label}-{ts}.zip"
        out = self._dir / archive_name
        try:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                if src.is_file():
                    zf.write(src, src.name)
                else:
                    for f in src.rglob("*"):
                        if f.is_file():
                            zf.write(f, f.relative_to(src.parent))
        except Exception as e:
            return f"[backup] Failed: {e}"
        size = out.stat().st_size
        self._manifest[label] = {
            "archive": archive_name, "source": str(src), "created": ts, "size": size,
        }
        self._save_manifest()
        return f"[backup] Created '{label}' from {src} -> {archive_name} ({_human(size)})"

    @safe
    def cmd_list(self, arg=""):
        """Show all tracked backups"""
        if not self._manifest:
            return "[backup] No backups yet. /backup create <path> [label]"
        lines = [f"[backup] {len(self._manifest)} backup(s):"]
        for label, info in sorted(self._manifest.items(), key=lambda kv: kv[1].get("created", "")):
            lines.append(f"  {label:20s} {info.get('created', '?')}  {_human(info.get('size', 0))}  "
                        f"from {info.get('source', '?')}")
        return "\n".join(lines)

    @safe
    def cmd_restore(self, arg=""):
        """Extract a backup (confirms — can overwrite files): /backup restore <label> <outdir> confirm"""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[backup] Usage: /backup restore <label> <outdir> confirm"
        label = parts[0]
        outdir = Path(" ".join(parts[1:-1])).expanduser()
        info = self._manifest.get(label)
        if not info:
            return f"[backup] No backup labeled '{label}'. See /backup list"
        archive = self._dir / info["archive"]
        if not archive.exists():
            return f"[backup] Archive file missing on disk: {archive}"
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(outdir)
                n = len(zf.namelist())
        except Exception as e:
            return f"[backup] Restore failed: {e}"
        return f"[backup] Restored '{label}' ({n} item(s)) to {outdir}"

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
