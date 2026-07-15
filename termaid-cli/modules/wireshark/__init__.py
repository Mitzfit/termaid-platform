"""Wireshark Module — Packet capture via tshark. SYSTEM tier.

Wraps `tshark` (Wireshark's CLI component) rather than the GUI, since a
backend module can't drive a desktop window. Captures are always time-
bounded — `duration` is capped at 300s and passed to tshark's own
`-a duration:N` stop condition *plus* a matching subprocess timeout, so a
capture can never block the shared request/response event loop
indefinitely (the same discipline applied to `bench`, `sync`, and every
other module that waits on a real external process in this codebase).
Captures are saved under TermAId's own data dir and listed/read back
through this module — never handed a path outside that directory to
avoid accidentally overwriting something already on disk.

Commands (~4):
  /wireshark interfaces                          List capture-able interfaces
  /wireshark capture <interface> <secs> [filter] confirm  Capture to a new file (max 300s)
  /wireshark read <name> [filter]                            Summarize a saved capture
  /wireshark list                                                List saved captures
  /wireshark explain                                                How this module works
"""

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_MAX_DURATION = 300


def _tshark_path() -> str:
    return shutil.which("tshark") or ""


class WiresharkModule(Module):
    name = "wireshark"
    version = "1.0.0"
    description = "Packet capture via tshark (Wireshark's CLI component)"
    author = "termaid"

    def on_load(self):
        for cmd in ["interfaces", "capture", "read", "list", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "captures"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, name: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z0-9_\-]+", name))

    @safe
    def cmd_interfaces(self, arg=""):
        """List capture-able interfaces"""
        tshark = _tshark_path()
        if not tshark:
            return "[wireshark] tshark not found. Install Wireshark (its CLI component is enough)."
        try:
            r = subprocess.run([tshark, "-D"], capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[wireshark] Failed: {e}"
        return f"[wireshark] Interfaces:\n{r.stdout.strip() or r.stderr.strip()}"

    @safe
    def cmd_capture(self, arg=""):
        """Capture to a new file, max 300s (confirms): /wireshark capture <interface> <secs> [filter] confirm"""
        parts = (arg or "").split()
        if len(parts) < 3 or parts[-1].lower() != "confirm":
            return "[wireshark] Usage: /wireshark capture <interface> <secs> [bpf-filter] confirm"
        interface = parts[0]
        try:
            duration = int(parts[1])
        except ValueError:
            return f"[wireshark] Invalid duration: {parts[1]}"
        duration = max(1, min(duration, _MAX_DURATION))
        bpf_filter = " ".join(parts[2:-1]) if len(parts) > 3 else ""

        tshark = _tshark_path()
        if not tshark:
            return "[wireshark] tshark not found. Install Wireshark (its CLI component is enough)."

        out_name = time.strftime("capture-%Y%m%d-%H%M%S.pcapng")
        out_path = self._dir / out_name
        cmd = [tshark, "-i", interface, "-a", f"duration:{duration}", "-w", str(out_path)]
        if bpf_filter:
            cmd += ["-f", bpf_filter]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 15)
        except subprocess.TimeoutExpired:
            return f"[wireshark] Capture didn't stop within {duration + 15}s — check the interface name."
        except Exception as e:
            return f"[wireshark] Failed: {e}"
        if r.returncode != 0 and not out_path.exists():
            return f"[wireshark] Capture failed: {(r.stderr or r.stdout).strip()}"
        size = out_path.stat().st_size if out_path.exists() else 0
        return f"[wireshark] Captured {duration}s on '{interface}' -> {out_name} ({size:,} bytes)"

    @safe
    def cmd_read(self, arg=""):
        """Summarize a saved capture: /wireshark read <name> [display-filter]"""
        parts = (arg or "").split(maxsplit=1)
        if not parts:
            return "[wireshark] Usage: /wireshark read <name> [display-filter] (see /wireshark list)"
        name = parts[0]
        if not self._safe_name(name.replace(".pcapng", "").replace(".pcap", "")):
            return "[wireshark] Invalid capture name."
        display_filter = parts[1] if len(parts) > 1 else ""
        path = self._dir / name
        if not path.is_file():
            return f"[wireshark] No capture named '{name}'. See /wireshark list"
        tshark = _tshark_path()
        if not tshark:
            return "[wireshark] tshark not found."
        cmd = [tshark, "-r", str(path)]
        if display_filter:
            cmd += ["-Y", display_filter]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except subprocess.TimeoutExpired:
            return "[wireshark] Reading the capture timed out (30s) — it may be very large."
        except Exception as e:
            return f"[wireshark] Failed: {e}"
        out = r.stdout.strip()
        lines = out.splitlines()
        shown = "\n".join(lines[:200])
        more = f"\n... and {len(lines) - 200} more line(s)" if len(lines) > 200 else ""
        return f"[wireshark] {name} ({len(lines)} packet(s) matched):\n{shown or '(no packets)'}{more}"

    @safe
    def cmd_list(self, arg=""):
        """List saved captures"""
        caps = sorted(self._dir.glob("*.pcap*"))
        if not caps:
            return "[wireshark] No captures yet. /wireshark capture <interface> <secs> confirm"
        lines = [f"[wireshark] {len(caps)} capture(s):"]
        for p in caps:
            lines.append(f"  {p.name:35s} {p.stat().st_size:,} bytes")
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
