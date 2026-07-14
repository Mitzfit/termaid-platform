"""Autoconfig Module — Auto-detect reasonable defaults for /config.

Reads the same config.json file /config manages (same schema, same path)
and proposes values based on what it can detect about the machine (tool
availability, platform). `detect` is a dry run showing what it would set
without touching anything; `apply confirm` actually writes those values
in, without overwriting any key you've already set yourself.

Commands (~2):
  /autoconfig detect         Show what would be set, without writing anything
  /autoconfig apply confirm    Write the detected defaults (skips existing keys)
  /autoconfig explain             How this module works
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


class AutoconfigModule(Module):
    name = "autoconfig"
    version = "1.0.0"
    description = "Auto-detect reasonable defaults for /config"
    author = "termaid"

    def on_load(self):
        for cmd in ["detect", "apply", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        data_dir.mkdir(parents=True, exist_ok=True)
        self._config_path = data_dir / "config.json"  # same file /config manages

    def _load_config(self) -> dict:
        if self._config_path.exists():
            try:
                return json.loads(self._config_path.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_config(self, data: dict):
        self._config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _detected(self) -> dict:
        values = {"platform": sys.platform}
        values["git_available"] = "true" if shutil.which("git") else "false"
        values["docker_available"] = "true" if shutil.which("docker") else "false"
        values["editor"] = os.environ.get("EDITOR") or ("notepad" if sys.platform == "win32" else "nano")
        values["color_output"] = "true" if sys.stdout.isatty() else "false"
        return values

    @safe
    def cmd_detect(self, arg=""):
        """Show what would be set, without writing anything"""
        current = self._load_config()
        detected = self._detected()
        lines = ["[autoconfig] Detected values:"]
        for key, value in detected.items():
            status = " (already set, would skip)" if key in current else ""
            lines.append(f"  {key:16s} = {value!r}{status}")
        lines.append("\n  Re-run as: /autoconfig apply confirm")
        return "\n".join(lines)

    @safe
    def cmd_apply(self, arg=""):
        """Write the detected defaults, skipping existing keys (confirms): /autoconfig apply confirm"""
        if (arg or "").strip().lower() != "confirm":
            return "[autoconfig] Re-run as: /autoconfig apply confirm"
        current = self._load_config()
        detected = self._detected()
        written = []
        for key, value in detected.items():
            if key not in current:
                current[key] = value
                written.append(key)
        self._save_config(current)
        if not written:
            return "[autoconfig] Nothing to write — every detected key already has a value in /config."
        return f"[autoconfig] Set {len(written)} key(s): {', '.join(written)}"

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
