"""AITools Module — Unified registry for free + paid AI CLI agents.

Detects which known AI coding CLIs are installed on this machine (via
shutil.which) and gives basic usage info. Does NOT launch them itself —
spawning an interactive external CLI from inside a web request has no good
way to attach a real terminal, so this module stays informational and lets
you copy the invocation to run yourself.

Commands (~7):
  /aitools list             List all known AI CLI tools in the registry
  /aitools detect             Which ones are actually installed on this machine
  /aitools info <tool>          Usage info for one tool
  /aitools add <name> <bin> <usage>   Register a custom tool not in the built-in list
  /aitools explain               How this module works
"""

import json
import os
import shutil
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_REGISTRY = {
    "claude": {"binary": "claude", "usage": "claude \"<prompt>\"",
              "note": "Claude Code CLI (Anthropic)"},
    "aider": {"binary": "aider", "usage": "aider <files...>",
             "note": "AI pair-programming in your terminal, many model backends"},
    "gh-copilot": {"binary": "gh", "usage": "gh copilot suggest \"<task>\"",
                  "note": "GitHub Copilot CLI extension (needs 'gh extension install')"},
    "cursor-agent": {"binary": "cursor-agent", "usage": "cursor-agent \"<prompt>\"",
                     "note": "Cursor's CLI agent"},
    "codex": {"binary": "codex", "usage": "codex \"<prompt>\"",
             "note": "OpenAI Codex CLI"},
    "ollama": {"binary": "ollama", "usage": "ollama run <model> \"<prompt>\"",
              "note": "Local open-source models, no API key/network needed"},
}


class AIToolsModule(Module):
    name = "aitools"
    version = "1.0.0"
    description = "Unified launcher for free + paid AI CLI agents"
    author = "termaid"

    def on_load(self):
        for cmd in ["list", "detect", "info", "add", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "aitools"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._custom_file = self._dir / "custom.json"

    def _load_custom(self) -> dict:
        if self._custom_file.exists():
            try:
                return json.loads(self._custom_file.read_text())
            except Exception:
                pass
        return {}

    def _all_tools(self) -> dict:
        return {**_REGISTRY, **self._load_custom()}

    @safe
    def cmd_list(self, arg=""):
        """List all known AI CLI tools in the registry"""
        tools = self._all_tools()
        lines = [f"[aitools] {len(tools)} known tool(s):"]
        for name, info in sorted(tools.items()):
            lines.append(f"  {name:<14s} {info.get('note', '')}")
        return "\n".join(lines)

    @safe
    def cmd_detect(self, arg=""):
        """Which ones are actually installed on this machine"""
        tools = self._all_tools()
        lines = ["[aitools] Detection results:"]
        found_any = False
        for name, info in sorted(tools.items()):
            path = shutil.which(info.get("binary", name))
            mark = "installed" if path else "not found"
            if path:
                found_any = True
            lines.append(f"  {name:<14s} {mark}" + (f"  ({path})" if path else ""))
        if not found_any:
            lines.append("\n  None detected. /aitools info <tool> for install hints.")
        return "\n".join(lines)

    @safe
    def cmd_info(self, arg=""):
        """Usage info for one tool"""
        name = (arg or "").strip().lower()
        if not name:
            return "[aitools] Usage: /aitools info <tool>. See /aitools list"
        tools = self._all_tools()
        if name not in tools:
            return f"[aitools] Unknown tool '{name}'. See /aitools list"
        info = tools[name]
        path = shutil.which(info.get("binary", name))
        lines = [f"[aitools] {name}:"]
        lines.append(f"  {info.get('note', '')}")
        lines.append(f"  usage:    {info.get('usage', '')}")
        lines.append(f"  status:   {'installed at ' + path if path else 'not installed'}")
        return "\n".join(lines)

    @safe
    def cmd_add(self, arg=""):
        """Register a custom tool: /aitools add <name> <binary> <usage-text>"""
        parts = (arg or "").split(None, 2)
        if len(parts) != 3:
            return "[aitools] Usage: /aitools add <name> <binary> <usage-text>"
        name, binary, usage = parts
        custom = self._load_custom()
        custom[name] = {"binary": binary, "usage": usage, "note": "custom (user-added)"}
        self._custom_file.write_text(json.dumps(custom, indent=2))
        return f"[aitools] Registered custom tool '{name}'"

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
