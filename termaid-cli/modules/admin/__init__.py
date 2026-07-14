"""Admin Module — Local administrator/root group management. DANGEROUS tier.

Windows: wraps `net localgroup Administrators`. Linux: wraps the `sudo`
and `wheel`/`sudoers` group via `usermod`/`gpasswd`. Viewing membership is
unrestricted; adding or removing a user from the admin group confirms
first — this directly controls who can act as an administrator on this
machine, which is about as consequential as a permission change gets.

Commands (~4):
  /admin status                  Is this backend process itself running elevated?
  /admin list-admins               List members of the local admin group
  /admin add-admin <user> confirm    Add a user to the local admin group
  /admin remove-admin <user> confirm   Remove a user from the local admin group
  /admin explain                         How this module works
"""

import ctypes
import os
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class AdminModule(Module):
    name = "admin"
    version = "1.0.0"
    description = "Local administrator/root group management"
    author = "termaid"

    def on_load(self):
        for cmd in ["status", "list-admins", "add-admin", "remove-admin", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_status(self, arg=""):
        """Is this backend process itself running elevated?"""
        try:
            if sys.platform == "win32":
                elevated = bool(ctypes.windll.shell32.IsUserAnAdmin())
            else:
                elevated = os.geteuid() == 0
        except Exception as e:
            return f"[admin] Could not determine elevation status: {e}"
        return f"[admin] This process is {'running elevated (Administrator/root)' if elevated else 'NOT elevated'}."

    @safe
    def cmd_list_admins(self, arg=""):
        """List members of the local admin group"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(["net", "localgroup", "Administrators"], capture_output=True,
                                    text=True, timeout=10)
            else:
                group = "wheel" if os.path.exists("/etc/redhat-release") else "sudo"
                r = subprocess.run(["getent", "group", group], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[admin] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[admin] {out}" if out else "[admin] No output."

    @safe
    def cmd_add_admin(self, arg=""):
        """Add a user to the local admin group (confirms): /admin add-admin <user> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            user = parts[0] if parts else "<user>"
            return f"[admin] This grants full administrator/root rights to '{user}'. Re-run as: /admin add-admin {user} confirm"
        user = parts[0]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["net", "localgroup", "Administrators", user, "/add"],
                                    capture_output=True, text=True, timeout=10)
            else:
                group = "wheel" if os.path.exists("/etc/redhat-release") else "sudo"
                r = subprocess.run(["usermod", "-aG", group, user], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[admin] Failed: {e}"
        if r.returncode != 0:
            return f"[admin] {(r.stderr or r.stdout).strip()}"
        return f"[admin] Added '{user}' to the local admin group"

    @safe
    def cmd_remove_admin(self, arg=""):
        """Remove a user from the local admin group (confirms): /admin remove-admin <user> confirm"""
        parts = (arg or "").split()
        if len(parts) < 2 or parts[1].lower() != "confirm":
            user = parts[0] if parts else "<user>"
            return f"[admin] Re-run as: /admin remove-admin {user} confirm"
        user = parts[0]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["net", "localgroup", "Administrators", user, "/delete"],
                                    capture_output=True, text=True, timeout=10)
            else:
                group = "wheel" if os.path.exists("/etc/redhat-release") else "sudo"
                r = subprocess.run(["gpasswd", "-d", user, group], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[admin] Failed: {e}"
        if r.returncode != 0:
            return f"[admin] {(r.stderr or r.stdout).strip()}"
        return f"[admin] Removed '{user}' from the local admin group"

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
