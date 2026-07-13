"""
native.py — bridge from Python to the Rust `termaid-scan` binary.

This is the "we ported the slow part to Rust" integration. The backend shells
out to the compiled scanner and parses its JSON. Locating the binary:
  1. TERMAID_SCAN_BIN env var (explicit)
  2. native/target/release/termaid-scan (dev build)
  3. on PATH (installed)

Scanning is a network action, so the caller (main.py) only registers it in
LOCAL mode — never exposed to arbitrary users on a server.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def scanner_path() -> str | None:
    return _bin_path("termaid-scan", "TERMAID_SCAN_BIN")


def walker_path() -> str | None:
    return _bin_path("termaid-walk", "TERMAID_WALK_BIN")


def _bin_path(name: str, env_var: str) -> str | None:
    env = os.environ.get(env_var)
    if env and Path(env).exists():
        return env
    exe = f"{name}.exe" if os.name == "nt" else name
    dev = Path(__file__).resolve().parents[1] / "native" / "target" / "release" / exe
    if dev.exists():
        return str(dev)
    return shutil.which(name)


def is_available() -> bool:
    return scanner_path() is not None


def scan_ports(host: str, start: int = 1, end: int = 1024, timeout_ms: int = 300) -> dict:
    """Run the Rust scanner; return parsed JSON or an error dict."""
    binary = scanner_path()
    if not binary:
        return {"error": "termaid-scan binary not found — build it: "
                         "cd native && cargo build --release"}
    try:
        proc = subprocess.run(
            [binary, host, str(start), str(end), str(timeout_ms)],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {"error": "scan timed out"}
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or f"scanner exited {proc.returncode}"}
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"error": f"unparseable scanner output: {proc.stdout[:200]}"}


def format_scan(result: dict) -> str:
    """Human-readable rendering for the terminal (engine commands return str)."""
    if "error" in result:
        return f"[scan error] {result['error']}"
    host = result.get("host", "?")
    open_ports = result.get("open", [])
    if not open_ports:
        return (f"[netscan/rust] {host}: no open ports in "
                f"{result.get('scanned', 0)} scanned ({result.get('ms', 0)}ms)")
    lines = [f"[netscan/rust] {host} — {len(open_ports)} open "
             f"of {result.get('scanned', 0)} scanned ({result.get('ms', 0)}ms):"]
    for p in open_ports:
        lines.append(f"  {p['port']:>5}/tcp  {p['service']}")
    return "\n".join(lines)


def walk_dir(path: str, top_n: int = 10) -> dict:
    """Run the Rust directory walker; return parsed JSON or an error dict."""
    binary = walker_path()
    if not binary:
        return {"error": "termaid-walk binary not found — build it: "
                         "cd native && cargo build --release"}
    try:
        proc = subprocess.run(
            [binary, path, str(top_n)],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {"error": "walk timed out"}
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or f"walker exited {proc.returncode}"}
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"error": f"unparseable walker output: {proc.stdout[:200]}"}


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


def format_walk(result: dict) -> str:
    if "error" in result:
        return f"[walk error] {result['error']}"
    lines = [f"[fsscan/rust] {result.get('root', '?')} — "
             f"{result.get('files', 0)} files, {result.get('dirs', 0)} dirs, "
             f"{_human(result.get('bytes', 0))} total ({result.get('ms', 0)}ms)"]
    largest = result.get("largest", [])
    if largest:
        lines.append("  largest:")
        for item in largest:
            lines.append(f"    {_human(item['bytes']):>9}  {item['path']}")
    return "\n".join(lines)
