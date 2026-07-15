"""Perms Module — View and change file/directory permissions + ownership. DANGEROUS tier.

Windows: wraps `icacls` for viewing/setting ACLs and ownership. Linux/
macOS: wraps `chmod`/`chown`/`stat`. Viewing and auditing are unrestricted;
anything that changes permissions or ownership confirms first since a bad
change (accidentally locking yourself out of your own files, or over-
widening access) is easy to do by accident and can be awkward to undo.

Commands (~6):
  /perms show <path>                        Show current permissions
  /perms owner <path>                          Show current owner
  /perms set <path> <mode> confirm               Set permissions (chmod octal / icacls grant string)
  /perms set-owner <path> <owner> confirm          Change ownership
  /perms audit <path>                                Recursively scan for risky permissions
  /perms reset <path> confirm                          Reset to inherited default permissions (Windows only)
  /perms explain                                          How this module works
"""

import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class PermsModule(Module):
    name = "perms"
    version = "1.1.0"
    description = "View and change file/directory permissions + ownership"
    author = "termaid"

    def on_load(self):
        for cmd in ["show", "owner", "set", "set-owner", "audit", "reset", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_show(self, arg=""):
        """Show current permissions: /perms show <path>"""
        path = (arg or "").strip()
        if not path:
            return "[perms] Usage: /perms show <path>"
        try:
            if sys.platform == "win32":
                r = subprocess.run(["icacls", path], capture_output=True, text=True, timeout=10)
            else:
                r = subprocess.run(["ls", "-ld", path], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[perms] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[perms] {path}:\n{out}" if out else f"[perms] No output for {path}"

    @safe
    def cmd_owner(self, arg=""):
        """Show current owner: /perms owner <path>"""
        path = (arg or "").strip()
        if not path:
            return "[perms] Usage: /perms owner <path>"
        try:
            if sys.platform == "win32":
                r = subprocess.run(["powershell", "-NoProfile", "-Command",
                                    f"(Get-Acl -LiteralPath '{path}' -ErrorAction Stop).Owner"],
                                    capture_output=True, text=True, timeout=10, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(["stat", "-c", "%U:%G", path] if sys.platform.startswith("linux")
                                    else ["stat", "-f", "%Su:%Sg", path],
                                    capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[perms] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[perms] Owner of {path}: {out or 'unknown'}"

    @safe
    def cmd_set(self, arg=""):
        """Set permissions (confirms): /perms set <path> <mode> confirm

        Linux/macOS <mode> is chmod-style octal (e.g. 644). Windows <mode> is
        an icacls grant string (e.g. "Everyone:R" or "%USERNAME%:F")."""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[perms] Usage: /perms set <path> <mode> confirm"
        path, mode = parts[0], parts[1]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["icacls", path, "/grant", mode], capture_output=True,
                                    text=True, timeout=15)
            else:
                r = subprocess.run(["chmod", mode, path], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[perms] Failed: {e}"
        if r.returncode != 0:
            return f"[perms] {(r.stderr or r.stdout).strip()}"
        return f"[perms] Updated {path} -> {mode}"

    @safe
    def cmd_set_owner(self, arg=""):
        """Change ownership (confirms): /perms set-owner <path> <owner> confirm"""
        parts = (arg or "").split()
        if len(parts) != 3 or parts[-1].lower() != "confirm":
            return "[perms] Usage: /perms set-owner <path> <owner> confirm"
        path, owner = parts[0], parts[1]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["icacls", path, "/setowner", owner], capture_output=True,
                                    text=True, timeout=15)
            else:
                r = subprocess.run(["chown", owner, path], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[perms] Failed: {e}"
        if r.returncode != 0:
            return f"[perms] {(r.stderr or r.stdout).strip()}"
        return f"[perms] Set owner of {path} -> {owner}"

    @safe
    def cmd_audit(self, arg=""):
        """Recursively scan for risky permissions: /perms audit <path>"""
        path = (arg or "").strip()
        if not path:
            return "[perms] Usage: /perms audit <path>"
        root = Path(path).expanduser()
        if not root.is_dir():
            return f"[perms] Not a directory: {root}"

        if sys.platform == "win32":
            try:
                r = subprocess.run(["icacls", str(root), "/t", "/c"], capture_output=True,
                                    text=True, timeout=30)
            except subprocess.TimeoutExpired:
                return "[perms] Audit timed out (30s) — try a smaller directory."
            except Exception as e:
                return f"[perms] Failed: {e}"
            flagged = [l for l in r.stdout.splitlines() if "Everyone:(F)" in l or "Everyone:(M)" in l]
            if not flagged:
                return f"[perms] No files granting Everyone full/modify access found under {root}."
            lines = [f"[perms] {len(flagged)} path(s) grant Everyone broad access under {root}:"]
            lines.extend(f"  {l.strip()}" for l in flagged[:50])
            return "\n".join(lines)
        else:
            import stat as stat_mod
            risky = []
            for p in root.rglob("*"):
                try:
                    mode = p.stat().st_mode
                except OSError:
                    continue
                flags = []
                if mode & stat_mod.S_IWOTH:
                    flags.append("world-writable")
                if mode & stat_mod.S_ISUID:
                    flags.append("setuid")
                if mode & stat_mod.S_ISGID:
                    flags.append("setgid")
                if flags:
                    risky.append((p, flags))
            if not risky:
                return f"[perms] No world-writable/setuid/setgid paths found under {root}."
            lines = [f"[perms] {len(risky)} risky path(s) under {root}:"]
            for p, flags in risky[:50]:
                lines.append(f"  {', '.join(flags):25s} {p}")
            return "\n".join(lines)

    @safe
    def cmd_reset(self, arg=""):
        """Reset to inherited default permissions (confirms, Windows only): /perms reset <path> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[-1].lower() != "confirm":
            return "[perms] This resets ACLs to their inherited defaults. Re-run as: /perms reset <path> confirm"
        path = " ".join(parts[:-1])
        if sys.platform != "win32":
            return "[perms] There's no direct 'reset to inherited' equivalent on Linux/macOS — restore from a known-good /perms show output with /perms set instead."
        try:
            r = subprocess.run(["icacls", path, "/reset"], capture_output=True, text=True, timeout=15)
        except Exception as e:
            return f"[perms] Failed: {e}"
        if r.returncode != 0:
            return f"[perms] {(r.stderr or r.stdout).strip()}"
        return f"[perms] Reset {path} to inherited default permissions."

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
