"""DevDetect Module — OS, hardware, and dev-tool capability detection.

Detects which common development tools are installed and their versions, via
`shutil.which` + a `--version` probe. Useful as a quick "what do I have on
this machine" check before assuming a tool exists.

Commands (~7):
  /devdetect scan            Detect all known dev tools + versions
  /devdetect check <tool>      Check one specific tool
  /devdetect os                  OS/platform summary
  /devdetect explain                How this module works
"""

import platform
import shutil
import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TOOLS = {
    "python": ["python", "--version"],
    "python3": ["python3", "--version"],
    "node": ["node", "--version"],
    "npm": ["npm", "--version"],
    "git": ["git", "--version"],
    "docker": ["docker", "--version"],
    "cargo": ["cargo", "--version"],
    "rustc": ["rustc", "--version"],
    "go": ["go", "version"],
    "java": ["java", "-version"],
    "gcc": ["gcc", "--version"],
    "make": ["make", "--version"],
    "code": ["code", "--version"],
    "gh": ["gh", "--version"],
    "kubectl": ["kubectl", "version", "--client"],
}


class DevDetectModule(Module):
    name = "devdetect"
    version = "1.0.0"
    description = "OS, hardware, and capability detection"
    author = "termaid"

    def on_load(self):
        for cmd in ["scan", "check", "os", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _probe(self, name: str, argv: list[str]) -> str:
        path = shutil.which(name)
        if not path:
            return "not installed"
        try:
            r = subprocess.run(argv, capture_output=True, text=True, timeout=5,
                              encoding="utf-8", errors="replace")
            out = (r.stdout or r.stderr).strip().splitlines()
            return out[0] if out else "installed (version unknown)"
        except Exception:
            return "installed (version check failed)"

    @safe
    def cmd_scan(self, arg=""):
        """Detect all known dev tools + versions"""
        lines = ["[devdetect] Scan results:"]
        for name, argv in _TOOLS.items():
            lines.append(f"  {name:<10s} {self._probe(name, argv)}")
        return "\n".join(lines)

    @safe
    def cmd_check(self, arg=""):
        """Check one specific tool"""
        name = (arg or "").strip().lower()
        if not name:
            return "[devdetect] Usage: /devdetect check <tool>. See /devdetect scan for known tools."
        argv = _TOOLS.get(name, [name, "--version"])
        return f"[devdetect] {name}: {self._probe(name, argv)}"

    @safe
    def cmd_os(self, arg=""):
        """OS/platform summary"""
        return (f"[devdetect] {platform.system()} {platform.release()} "
                f"({platform.machine()}), Python {platform.python_version()}")

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
