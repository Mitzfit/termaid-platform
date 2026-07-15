"""Doctor Module — Environment health check: is this machine set up correctly?

Checks for the tools TermAId's own modules lean on, plus a broader set of
common dev tooling, and a handful of sanity checks on the runtime itself
(Python version/venv, git identity config, disk headroom, .env presence,
basic network reachability). Read-only — never installs or modifies
anything, only reports and, for missing tools, suggests the install
command you'd run yourself.

Commands (~5):
  /doctor check              Full diagnostic run
  /doctor tool <name>          Check a single tool's availability + version
  /doctor fix <name>              Suggest an install command for a missing tool
  /doctor connectivity               Basic network reachability check
  /doctor explain                      How this module works
"""

import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_TOOLS = ["git", "docker", "nmap", "node", "npm", "whois", "dig", "curl",
          "wget", "ssh", "cargo", "rustc", "code", "tmux", "python3"]

_INSTALL_HINTS = {
    "win32": {
        "git": "winget install Git.Git",
        "docker": "winget install Docker.DockerDesktop",
        "nmap": "winget install Insecure.Nmap",
        "node": "winget install OpenJS.NodeJS",
        "npm": "winget install OpenJS.NodeJS  (npm comes bundled)",
        "curl": "already included in Windows 10 1803+",
        "wget": "winget install GNU.Wget2",
        "ssh": "Windows Optional Feature: OpenSSH Client",
        "cargo": "winget install Rustlang.Rustup",
        "rustc": "winget install Rustlang.Rustup  (installs cargo + rustc)",
        "code": "winget install Microsoft.VisualStudioCode",
        "tmux": "install via WSL/Cygwin — no native Windows build",
        "whois": "winget install --id 9NBLGGH4V8XS  (or use Sysinternals whois)",
        "dig": "part of BIND tools — winget install ISC.BIND9  or use WSL",
        "python3": "winget install Python.Python.3",
    },
    # Debian/Ubuntu (apt), macOS (brew), and Termux (pkg) side by side — a
    # bare "sudo apt install" is wrong advice on Fedora/Arch/Termux/macOS,
    # none of which have apt or (on Termux) sudo at all.
    "default": {
        "git": "apt install git  /  brew install git  /  pkg install git",
        "docker": "https://docs.docker.com/engine/install/  (not available on Termux — no daemon support)",
        "nmap": "apt install nmap  /  brew install nmap  /  pkg install nmap",
        "node": "apt install nodejs  /  brew install node  /  pkg install nodejs",
        "npm": "apt install npm  /  brew install node  /  pkg install nodejs  (npm comes bundled)",
        "curl": "apt install curl  /  brew install curl  /  pkg install curl",
        "wget": "apt install wget  /  brew install wget  /  pkg install wget",
        "ssh": "apt install openssh-client  /  brew install openssh  /  pkg install openssh",
        "cargo": "curl https://sh.rustup.rs -sSf | sh  /  pkg install rust",
        "rustc": "curl https://sh.rustup.rs -sSf | sh  /  pkg install rust  (installs cargo + rustc)",
        "code": "https://code.visualstudio.com/download  (not available on Termux — no GUI)",
        "tmux": "apt install tmux  /  brew install tmux  /  pkg install tmux",
        "whois": "apt install whois  /  brew install whois  /  pkg install whois",
        "dig": "apt install dnsutils  /  brew install bind  /  pkg install dnsutils",
        "python3": "apt install python3  /  brew install python3  /  pkg install python",
    },
}


class DoctorModule(Module):
    name = "doctor"
    version = "1.1.0"
    description = "Environment health check: is this machine set up correctly?"
    author = "termaid"

    def on_load(self):
        for cmd in ["check", "tool", "fix", "connectivity", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _version(self, tool: str) -> str:
        try:
            r = subprocess.run([tool, "--version"], capture_output=True, text=True,
                                timeout=5, encoding="utf-8", errors="replace")
            first_line = (r.stdout or r.stderr or "").strip().splitlines()
            return first_line[0][:60] if first_line else "(no version output)"
        except Exception:
            return ""

    def _git_identity(self):
        try:
            name = subprocess.run(["git", "config", "--global", "user.name"],
                                  capture_output=True, text=True, timeout=5).stdout.strip()
            email = subprocess.run(["git", "config", "--global", "user.email"],
                                   capture_output=True, text=True, timeout=5).stdout.strip()
            return name, email
        except Exception:
            return "", ""

    @safe
    def cmd_check(self, arg=""):
        """Full diagnostic run"""
        lines = ["=== Doctor ===\n", "Tools:"]
        for tool in _TOOLS:
            path = shutil.which(tool)
            if path:
                lines.append(f"  OK    {tool:8s} {self._version(tool)}")
            else:
                lines.append(f"  MISS  {tool:8s} not found on PATH  (see /doctor fix {tool})")

        lines.append("\nRuntime:")
        lines.append(f"  Python:      {sys.version.split()[0]}")
        lines.append(f"  Platform:    {sys.platform}")
        in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
        lines.append(f"  Virtualenv:  {'yes — ' + sys.prefix if in_venv else 'no (running on system Python)'}")

        env_path = Path(os.getcwd()) / ".env"
        lines.append(f"  .env file:   {'found' if env_path.exists() else 'MISSING'}")

        name, email = self._git_identity()
        if name and email:
            lines.append(f"  git identity: {name} <{email}>")
        else:
            lines.append("  git identity: NOT configured — git commit will fail. "
                        "Set with: git config --global user.name/user.email")

        try:
            usage = shutil.disk_usage(os.getcwd())
            pct = usage.used / usage.total * 100
            free_gb = usage.free / (1024 ** 3)
            flag = "OK" if pct < 90 else "WARN"
            lines.append(f"  Disk space:  {flag}  {pct:.0f}% used, {free_gb:.1f}GB free")
        except Exception:
            pass

        return "\n".join(lines)

    @safe
    def cmd_tool(self, arg=""):
        """Check a single tool's availability + version: /doctor tool <name>"""
        tool = (arg or "").strip()
        if not tool:
            return "[doctor] Usage: /doctor tool <name>"
        path = shutil.which(tool)
        if not path:
            return f"[doctor] '{tool}' not found on PATH. See /doctor fix {tool}"
        return f"[doctor] {tool}: {path}\n  {self._version(tool)}"

    @safe
    def cmd_fix(self, arg=""):
        """Suggest an install command for a missing tool: /doctor fix <name>"""
        tool = (arg or "").strip().lower()
        if not tool:
            return "[doctor] Usage: /doctor fix <name>"
        hints = _INSTALL_HINTS.get(sys.platform, _INSTALL_HINTS["default"])
        if tool not in hints:
            return f"[doctor] No install hint on file for '{tool}' — check its own project's install docs."
        if shutil.which(tool):
            return f"[doctor] '{tool}' is already on PATH — nothing to fix."
        return f"[doctor] To install {tool}:\n  {hints[tool]}"

    @safe
    def cmd_connectivity(self, arg=""):
        """Basic network reachability check"""
        lines = ["[doctor] Connectivity:"]
        try:
            socket.gethostbyname("github.com")
            lines.append("  DNS resolution:  OK (github.com resolved)")
        except Exception as e:
            lines.append(f"  DNS resolution:  FAIL ({e})")

        for host, port, label in [("github.com", 443, "HTTPS to github.com"),
                                   ("1.1.1.1", 53, "DNS port to 1.1.1.1")]:
            try:
                with socket.create_connection((host, port), timeout=4):
                    lines.append(f"  {label}:  OK")
            except Exception as e:
                lines.append(f"  {label}:  FAIL ({e})")

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
