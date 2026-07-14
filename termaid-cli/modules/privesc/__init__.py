"""Privesc Module — Elevate the operator's own session. DANGEROUS tier.

This is convenience for the machine's own operator, not an attack tool:
it triggers the SAME UAC consent dialog (Windows) or polkit prompt (Linux)
the operator would see running the command directly, on their own
interactive desktop, requiring them to physically approve it. There's no
way to answer that prompt through a headless request/response API, so this
launches it via a non-blocking Popen (never .run) and returns immediately
— it does not and cannot silently grant elevation; a human still has to
click "Yes" at the actual desktop.

Commands (~2):
  /privesc elevate <command> confirm     Launch a command with a UAC/polkit prompt
  /privesc status                          Is UAC/polkit configured on this host?
  /privesc explain                            How this module works
"""

import shutil
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class PrivescModule(Module):
    name = "privesc"
    version = "1.0.0"
    description = "Elevate the operator's own session via UAC/polkit"
    author = "termaid"

    def on_load(self):
        for cmd in ["elevate", "status", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_elevate(self, arg=""):
        """Launch a command with a UAC/polkit prompt (confirms): /privesc elevate <command> confirm"""
        text = (arg or "").rstrip()
        if not text.lower().endswith("confirm"):
            return ("[privesc] This pops a REAL elevation prompt on the desktop — someone has to "
                    "be there to approve it. Re-run as: /privesc elevate <command> confirm")
        command = text[:-len("confirm")].rstrip()
        if not command:
            return "[privesc] Usage: /privesc elevate <command> confirm"
        try:
            if sys.platform == "win32":
                escaped = command.replace("'", "''")
                ps_script = (
                    f"Start-Process powershell -ArgumentList '-NoProfile','-Command','{escaped}' "
                    "-Verb RunAs"
                )
                subprocess.Popen(["powershell", "-NoProfile", "-Command", ps_script],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "[privesc] Launched — a UAC prompt should appear on the desktop for approval."
            else:
                if not shutil.which("pkexec"):
                    return "[privesc] pkexec not found — install polkit, or use /sudo for headless elevation."
                subprocess.Popen(["pkexec", "sh", "-c", command],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return "[privesc] Launched — a polkit prompt should appear on the desktop for approval."
        except Exception as e:
            return f"[privesc] Failed to launch: {e}"

    @safe
    def cmd_status(self, arg=""):
        """Is UAC/polkit configured on this host?"""
        if sys.platform == "win32":
            try:
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System' "
                     "-Name EnableLUA -ErrorAction SilentlyContinue).EnableLUA"],
                    capture_output=True, text=True, timeout=8, encoding="utf-8", errors="replace")
                val = r.stdout.strip()
                return f"[privesc] UAC (EnableLUA): {'enabled' if val == '1' else 'disabled' if val == '0' else 'unknown'}"
            except Exception as e:
                return f"[privesc] Could not check UAC status: {e}"
        else:
            return f"[privesc] polkit (pkexec): {'available' if shutil.which('pkexec') else 'not found'}"

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
