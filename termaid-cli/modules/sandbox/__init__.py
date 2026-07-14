"""Sandbox Module — Ephemeral scratch directories, with staging + snapshots.

Directory isolation, not process isolation: /sandbox run executes a
command with its working directory set to the sandbox, so relative paths
stay contained — it does NOT sandbox the process itself (no seccomp, no
namespace, no resource limits). For running genuinely untrusted code
you'd need OS-level isolation this module doesn't attempt; be clear about
that distinction when using it.

Every sandbox is tracked with a creation timestamp so stale ones (created
long ago and forgotten) can be found and cleaned up. Snapshots are zip
archives stored alongside the registry — restoring one confirms first
since it replaces the sandbox's current contents.

Commands (~11):
  /sandbox create [label]                Create a new scratch directory
  /sandbox list                            Show tracked scratch directories
  /sandbox path <label>                      Print a scratch directory's path
  /sandbox contents <label>                    List files + sizes inside
  /sandbox size <label>                          Total disk usage
  /sandbox copy-in <label> <src>                   Copy a file/dir into the sandbox
  /sandbox copy-out <label> <name> <dst>             Copy something out of the sandbox
  /sandbox run <label> <command>                       Run a command with cwd=sandbox (30s timeout)
  /sandbox snapshot <label> [name]                       Zip the sandbox's current contents
  /sandbox snapshots <label>                               List snapshots for a sandbox
  /sandbox restore <label> <snapshot> confirm                Replace contents from a snapshot
  /sandbox stale [days]                                        List sandboxes older than N days (default 7)
  /sandbox destroy <label> confirm                               Delete a scratch directory + contents
  /sandbox explain                                                   How this module works
"""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
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


def _dir_size(path: Path) -> int:
    total = 0
    for f in path.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


class SandboxModule(Module):
    name = "sandbox"
    version = "1.1.0"
    description = "Ephemeral scratch directories, with staging + snapshots"
    author = "termaid"

    def on_load(self):
        for cmd in ["create", "list", "path", "contents", "size", "copy-in", "copy-out",
                    "run", "snapshot", "snapshots", "restore", "stale", "destroy", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = data_dir / "sandboxes.json"
        self._snapshot_dir = data_dir / "sandbox_snapshots"
        self._snapshot_dir.mkdir(parents=True, exist_ok=True)
        self._registry = self._load()

    def _load(self) -> dict:
        if self._registry_path.exists():
            try:
                data = json.loads(self._registry_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
            # Upgrade legacy string-only entries (path only, no timestamp) in place.
            for label, value in list(data.items()):
                if isinstance(value, str):
                    data[label] = {"path": value, "created": 0}
            return data
        return {}

    def _save(self):
        self._registry_path.write_text(json.dumps(self._registry, indent=2), encoding="utf-8")

    def _resolve(self, label: str):
        entry = self._registry.get(label)
        if not entry:
            return None
        return Path(entry["path"])

    @safe
    def cmd_create(self, arg=""):
        """Create a new scratch directory: /sandbox create [label]"""
        label = (arg or "").strip() or time.strftime("sb-%Y%m%d-%H%M%S")
        if label in self._registry:
            return f"[sandbox] '{label}' already exists at {self._registry[label]['path']}"
        path = Path(tempfile.mkdtemp(prefix=f"termaid-sandbox-{label}-"))
        self._registry[label] = {"path": str(path), "created": time.time()}
        self._save()
        return f"[sandbox] Created '{label}' -> {path}"

    @safe
    def cmd_list(self, arg=""):
        """Show tracked scratch directories"""
        if not self._registry:
            return "[sandbox] No scratch directories yet. /sandbox create [label]"
        lines = [f"[sandbox] {len(self._registry)} directory(ies):"]
        for label, entry in sorted(self._registry.items()):
            path = Path(entry["path"])
            exists = "" if path.is_dir() else "  (missing on disk)"
            age = ""
            if entry.get("created"):
                days = (time.time() - entry["created"]) / 86400
                age = f"  ({days:.1f}d old)"
            lines.append(f"  {label:20s} {path}{exists}{age}")
        return "\n".join(lines)

    @safe
    def cmd_path(self, arg=""):
        """Print a scratch directory's path: /sandbox path <label>"""
        label = (arg or "").strip()
        if not label:
            return "[sandbox] Usage: /sandbox path <label>"
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        return f"[sandbox] {label} -> {path}"

    @safe
    def cmd_contents(self, arg=""):
        """List files + sizes inside: /sandbox contents <label>"""
        label = (arg or "").strip()
        if not label:
            return "[sandbox] Usage: /sandbox contents <label>"
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        if not path.is_dir():
            return f"[sandbox] Directory missing on disk: {path}"
        files = sorted(f for f in path.rglob("*") if f.is_file())
        if not files:
            return f"[sandbox] '{label}' is empty."
        lines = [f"[sandbox] {label} ({len(files)} file(s)):"]
        for f in files[:100]:
            try:
                size = f.stat().st_size
            except OSError:
                size = 0
            lines.append(f"  {_human(size):>10s}  {f.relative_to(path)}")
        if len(files) > 100:
            lines.append(f"  ... and {len(files) - 100} more")
        return "\n".join(lines)

    @safe
    def cmd_size(self, arg=""):
        """Total disk usage: /sandbox size <label>"""
        label = (arg or "").strip()
        if not label:
            return "[sandbox] Usage: /sandbox size <label>"
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        if not path.is_dir():
            return f"[sandbox] Directory missing on disk: {path}"
        return f"[sandbox] {label}: {_human(_dir_size(path))}"

    @safe
    def cmd_copy_in(self, arg=""):
        """Copy a file/dir into the sandbox: /sandbox copy-in <label> <src>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[sandbox] Usage: /sandbox copy-in <label> <src>"
        label, src_s = parts
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        src = Path(src_s).expanduser().resolve()
        if not src.exists():
            return f"[sandbox] Source not found: {src}"
        dest = path / src.name
        try:
            if src.is_dir():
                shutil.copytree(src, dest, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dest)
        except Exception as e:
            return f"[sandbox] Copy failed: {e}"
        return f"[sandbox] Copied {src} -> {dest}"

    @safe
    def cmd_copy_out(self, arg=""):
        """Copy something out of the sandbox: /sandbox copy-out <label> <name> <dst>"""
        parts = (arg or "").split(maxsplit=2)
        if len(parts) < 3:
            return "[sandbox] Usage: /sandbox copy-out <label> <name> <dst>"
        label, name, dst_s = parts
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        src = path / name
        if not src.exists():
            return f"[sandbox] Not found in sandbox: {name}"
        dst = Path(dst_s).expanduser()
        if dst.is_dir():
            target = dst / name
        elif dst.exists():
            target = dst  # existing file: overwrite
        elif dst.suffix == "":
            # Doesn't exist yet and looks like a directory path (no extension) — create it.
            dst.mkdir(parents=True, exist_ok=True)
            target = dst / name
        else:
            # Doesn't exist yet and looks like a file path — treat dst itself as the target.
            dst.parent.mkdir(parents=True, exist_ok=True)
            target = dst
        try:
            if src.is_dir():
                shutil.copytree(src, target, dirs_exist_ok=True)
            else:
                shutil.copy2(src, target)
        except Exception as e:
            return f"[sandbox] Copy failed: {e}"
        return f"[sandbox] Copied {src} -> {target}"

    @safe
    def cmd_run(self, arg=""):
        """Run a command with cwd=sandbox (30s timeout): /sandbox run <label> <command>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) < 2:
            return "[sandbox] Usage: /sandbox run <label> <command>"
        label, command = parts
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        if not path.is_dir():
            return f"[sandbox] Directory missing on disk: {path}"
        try:
            tokens = shlex.split(command, posix=(sys.platform != "win32"))
        except ValueError as e:
            return f"[sandbox] Couldn't parse command: {e}"
        if not tokens:
            return "[sandbox] Usage: /sandbox run <label> <command>"
        try:
            r = subprocess.run(tokens, cwd=str(path), capture_output=True, text=True,
                                timeout=30, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return f"[sandbox] Command not found: {tokens[0]}"
        except subprocess.TimeoutExpired:
            return "[sandbox] Command timed out (30s). This runs with a scoped cwd, not a scoped process — long-running commands aren't a fit here."
        out = (r.stdout or "").strip()
        err = (r.stderr or "").strip()
        result = out or "(no output)"
        if err:
            result += f"\n[stderr]\n{err}"
        return f"[sandbox:{label}] (exit {r.returncode}) {result}"

    @safe
    def cmd_snapshot(self, arg=""):
        """Zip the sandbox's current contents: /sandbox snapshot <label> [name]"""
        parts = (arg or "").split(maxsplit=1)
        if not parts:
            return "[sandbox] Usage: /sandbox snapshot <label> [name]"
        label = parts[0]
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        if not path.is_dir():
            return f"[sandbox] Directory missing on disk: {path}"
        snap_name = parts[1].strip() if len(parts) > 1 else time.strftime("%Y%m%d-%H%M%S")
        safe_snap = "".join(c if c.isalnum() or c in "-_." else "_" for c in snap_name)
        out = self._snapshot_dir / f"{label}__{safe_snap}.zip"
        try:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in path.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(path))
        except Exception as e:
            return f"[sandbox] Snapshot failed: {e}"
        return f"[sandbox] Snapshotted '{label}' -> {out.name} ({_human(out.stat().st_size)})"

    @safe
    def cmd_snapshots(self, arg=""):
        """List snapshots for a sandbox: /sandbox snapshots <label>"""
        label = (arg or "").strip()
        if not label:
            return "[sandbox] Usage: /sandbox snapshots <label>"
        prefix = f"{label}__"
        matches = sorted(f for f in self._snapshot_dir.glob(f"{prefix}*.zip"))
        if not matches:
            return f"[sandbox] No snapshots for '{label}'."
        lines = [f"[sandbox] {len(matches)} snapshot(s) for '{label}':"]
        for f in matches:
            snap_name = f.stem[len(prefix):]
            lines.append(f"  {snap_name:25s} {_human(f.stat().st_size)}")
        return "\n".join(lines)

    @safe
    def cmd_restore(self, arg=""):
        """Replace contents from a snapshot (confirms): /sandbox restore <label> <snapshot> confirm"""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[sandbox] This replaces the sandbox's current contents. Re-run as: /sandbox restore <label> <snapshot> confirm"
        label, snap_name = parts[0], parts[1]
        path = self._resolve(label)
        if path is None:
            return f"[sandbox] No sandbox named '{label}'"
        snap_path = self._snapshot_dir / f"{label}__{snap_name}.zip"
        if not snap_path.is_file():
            return f"[sandbox] No snapshot '{snap_name}' for '{label}'. See /sandbox snapshots {label}"
        try:
            if path.is_dir():
                shutil.rmtree(path)
            path.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(snap_path) as zf:
                zf.extractall(path)
                n = len(zf.namelist())
        except Exception as e:
            return f"[sandbox] Restore failed: {e}"
        return f"[sandbox] Restored '{label}' from snapshot '{snap_name}' ({n} item(s))"

    @safe
    def cmd_stale(self, arg=""):
        """List sandboxes older than N days (default 7): /sandbox stale [days]"""
        s = (arg or "").strip()
        try:
            days = float(s) if s else 7.0
        except ValueError:
            return f"[sandbox] Invalid days: {s}"
        cutoff = time.time() - days * 86400
        stale = [(label, entry) for label, entry in self._registry.items()
                if entry.get("created", time.time()) < cutoff]
        if not stale:
            return f"[sandbox] No sandboxes older than {days} day(s)."
        lines = [f"[sandbox] {len(stale)} sandbox(es) older than {days} day(s):"]
        for label, entry in sorted(stale, key=lambda x: x[1].get("created", 0)):
            age_days = (time.time() - entry.get("created", time.time())) / 86400
            lines.append(f"  {label:20s} {age_days:.1f}d old  {entry['path']}")
        lines.append("\n  Clean up with: /sandbox destroy <label> confirm")
        return "\n".join(lines)

    @safe
    def cmd_destroy(self, arg=""):
        """Delete a scratch directory + contents (confirms): /sandbox destroy <label> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            label = parts[0] if parts else "<label>"
            return f"[sandbox] This deletes the directory and everything in it. Re-run as: /sandbox destroy {label} confirm"
        label = parts[0]
        if label not in self._registry:
            return f"[sandbox] No sandbox named '{label}'"
        path = Path(self._registry[label]["path"])
        if path.is_dir():
            try:
                shutil.rmtree(path)
            except Exception as e:
                return f"[sandbox] Failed to remove {path}: {e}"
        del self._registry[label]
        self._save()
        return f"[sandbox] Destroyed '{label}' ({path})"

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
