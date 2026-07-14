"""Extras Module — Optional nice-to-have tool detection.

Distinct from /doctor (which checks tools other TermAId modules actively
depend on — git, docker, nmap): this checks a longer tail of genuinely
optional tools that are useful but nothing here requires — media/doc
conversion, archive, and JSON tooling. Read-only, just reports presence.

Commands (~2):
  /extras check         Check for optional tool availability
  /extras explain          How this module works
"""

import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_EXTRAS = ["ffmpeg", "magick", "convert", "pandoc", "jq", "7z", "curl", "rsync"]


class ExtrasModule(Module):
    name = "extras"
    version = "1.0.0"
    description = "Optional nice-to-have tool detection"
    author = "termaid"

    def on_load(self):
        for cmd in ["check", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _version(self, tool: str) -> str:
        for flag in ("--version", "-version", "version"):
            try:
                r = subprocess.run([tool, flag], capture_output=True, text=True,
                                    timeout=5, encoding="utf-8", errors="replace")
                first_line = (r.stdout or r.stderr or "").strip().splitlines()
                if first_line:
                    return first_line[0][:60]
            except Exception:
                continue
        return ""

    @safe
    def cmd_check(self, arg=""):
        """Check for optional tool availability"""
        lines = ["[extras] Optional tools:"]
        for tool in _EXTRAS:
            path = shutil.which(tool)
            if path:
                lines.append(f"  OK    {tool:10s} {self._version(tool)}")
            else:
                lines.append(f"  --    {tool:10s} not found")
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
