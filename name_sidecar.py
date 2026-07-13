#!/usr/bin/env python3
"""Copy the PyInstaller output to the Tauri externalBin target-triple name."""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def host_triple() -> str:
    out = subprocess.check_output(["rustc", "-Vv"], text=True)
    for line in out.splitlines():
        if line.startswith("host:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("could not determine host triple from rustc -Vv")


def main() -> None:
    triple = host_triple()
    is_win = "windows" in triple
    src = ROOT / "backend" / "dist" / ("termaid-backend.exe" if is_win else "termaid-backend")
    if not src.exists():
        raise SystemExit(f"sidecar not found: {src} (run PyInstaller first)")
    dst_dir = ROOT / "desktop-mobile" / "src-tauri" / "binaries"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"termaid-backend-{triple}{'.exe' if is_win else ''}"
    shutil.copy2(src, dst)
    print(f"sidecar → {dst}")


if __name__ == "__main__":
    main()
