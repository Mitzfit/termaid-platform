"""Bootmgr Module — Default OS + boot timeout management. DANGEROUS tier.

Windows: wraps `bcdedit`. Linux: reads/edits `/etc/default/grub`'s
GRUB_DEFAULT/GRUB_TIMEOUT and runs `update-grub` to apply. Changing the
default boot entry to something invalid, or setting the timeout to 0 on
a system you might need to interrupt at boot (e.g. to reach a recovery
menu), can make a system awkward to recover from — hence the confirm gate.

Commands (~3):
  /bootmgr show                       Current boot entries + default + timeout
  /bootmgr set-default <id> confirm     Change the default boot entry
  /bootmgr set-timeout <sec> confirm      Change the boot menu timeout
  /bootmgr explain                          How this module works
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_GRUB_DEFAULT = Path("/etc/default/grub")


class BootmgrModule(Module):
    name = "bootmgr"
    version = "1.0.0"
    description = "Default OS + boot timeout management"
    author = "termaid"

    def on_load(self):
        for cmd in ["show", "set-default", "set-timeout", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_show(self, arg=""):
        """Current boot entries + default + timeout"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(["bcdedit", "/enum"], capture_output=True, text=True, timeout=10)
                return f"[bootmgr] {r.stdout.strip() or r.stderr.strip()}"
            else:
                if not _GRUB_DEFAULT.is_file():
                    return "[bootmgr] /etc/default/grub not found (not a GRUB system?)."
                text = _GRUB_DEFAULT.read_text(errors="replace")
                default_m = re.search(r'^GRUB_DEFAULT=(.*)$', text, re.M)
                timeout_m = re.search(r'^GRUB_TIMEOUT=(.*)$', text, re.M)
                return (f"[bootmgr] GRUB_DEFAULT={default_m.group(1) if default_m else '?'}  "
                        f"GRUB_TIMEOUT={timeout_m.group(1) if timeout_m else '?'}")
        except Exception as e:
            return f"[bootmgr] Failed: {e}"

    @safe
    def cmd_set_default(self, arg=""):
        """Change the default boot entry (confirms): /bootmgr set-default <id> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[bootmgr] Usage: /bootmgr set-default <id> confirm"
        entry_id = parts[0]
        try:
            if sys.platform == "win32":
                r = subprocess.run(["bcdedit", "/default", entry_id], capture_output=True,
                                    text=True, timeout=10)
                return f"[bootmgr] {(r.stdout or r.stderr).strip()}"
            else:
                if not _GRUB_DEFAULT.is_file():
                    return "[bootmgr] /etc/default/grub not found."
                text = _GRUB_DEFAULT.read_text(errors="replace")
                text = re.sub(r'^GRUB_DEFAULT=.*$', f'GRUB_DEFAULT={entry_id}', text, flags=re.M)
                _GRUB_DEFAULT.write_text(text)
                if shutil.which("update-grub"):
                    subprocess.run(["update-grub"], capture_output=True, text=True, timeout=30)
                return f"[bootmgr] Default set to '{entry_id}' and grub updated."
        except Exception as e:
            return f"[bootmgr] Failed: {e}"

    @safe
    def cmd_set_timeout(self, arg=""):
        """Change the boot menu timeout (confirms): /bootmgr set-timeout <sec> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[bootmgr] Usage: /bootmgr set-timeout <sec> confirm"
        try:
            seconds = int(parts[0])
        except ValueError:
            return f"[bootmgr] Invalid seconds: {parts[0]}"
        try:
            if sys.platform == "win32":
                r = subprocess.run(["bcdedit", "/timeout", str(seconds)], capture_output=True,
                                    text=True, timeout=10)
                return f"[bootmgr] {(r.stdout or r.stderr).strip()}"
            else:
                if not _GRUB_DEFAULT.is_file():
                    return "[bootmgr] /etc/default/grub not found."
                text = _GRUB_DEFAULT.read_text(errors="replace")
                text = re.sub(r'^GRUB_TIMEOUT=.*$', f'GRUB_TIMEOUT={seconds}', text, flags=re.M)
                _GRUB_DEFAULT.write_text(text)
                if shutil.which("update-grub"):
                    subprocess.run(["update-grub"], capture_output=True, text=True, timeout=30)
                return f"[bootmgr] Timeout set to {seconds}s and grub updated."
        except Exception as e:
            return f"[bootmgr] Failed: {e}"

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
