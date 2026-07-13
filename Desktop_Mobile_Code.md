# Agent 09 — Desktop & Mobile / Tauri: OWNED SOURCE CODE

Hand edits back as text. The lib.rs native command bodies are Agent 07's — not included here.

## `desktop-mobile/src-tauri/src/main.rs`

```rust
// Desktop entry point. Mobile uses the #[tauri::mobile_entry_point] in lib.rs.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    termaid_lib::run()
}

```

## `desktop-mobile/src-tauri/Cargo.toml`

```toml
[package]
name = "termaid"
version = "2.0.0"
description = "TermAId — cross-platform AI terminal"
edition = "2021"
rust-version = "1.77.2"

# Tauri 2 builds a library that both desktop (main.rs) and mobile entry points use.
[lib]
name = "termaid_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-shell = "2"        # spawn the Python backend sidecar (local mode)
tauri-plugin-http = "2"         # talk to a remote backend (server mode)
serde = { version = "1", features = ["derive"] }
serde_json = "1"
sha2 = "0.10"                   # native hashing — the Rust performance path
termaid-scan = { path = "../../native" }   # in-process port scanner (offline-mobile path)

[features]
custom-protocol = ["tauri/custom-protocol"]

```

## `desktop-mobile/src-tauri/build.rs`

```rust
fn main() {
    tauri_build::build()
}

```

## `desktop-mobile/src-tauri/tauri.conf.json`

```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "TermAId",
  "version": "2.0.0",
  "identifier": "dev.termaid.app",
  "build": {
    "frontendDist": "../../frontend/dist",
    "devUrl": "http://localhost:5173",
    "beforeDevCommand": "npm --prefix ../../frontend run dev",
    "beforeBuildCommand": "npm --prefix ../../frontend run build"
  },
  "app": {
    "windows": [
      {
        "title": "TermAId",
        "width": 980,
        "height": 720,
        "minWidth": 360,
        "minHeight": 480,
        "resizable": true
      }
    ],
    "security": {
      "csp": "default-src 'self'; connect-src 'self' http://localhost:8000 ws://localhost:8000 https://* wss://*; style-src 'self' 'unsafe-inline'"
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "externalBin": ["binaries/termaid-backend"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ]
  },
  "plugins": {}
}

```

## `desktop-mobile/src-tauri/capabilities/default.json`

```json
{
  "$schema": "../gen/schemas/desktop-schema.json",
  "identifier": "default",
  "description": "Core permissions: spawn the local backend sidecar, make HTTP/WS calls.",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "shell:allow-spawn",
    "http:default"
  ]
}

```

## `desktop-mobile/package.json`

```json
{
  "name": "termaid-desktop-mobile",
  "private": true,
  "version": "2.0.0",
  "scripts": {
    "tauri": "tauri",
    "dev": "tauri dev",
    "build": "tauri build",
    "android:init": "tauri android init",
    "android:dev": "tauri android dev",
    "android:build": "tauri android build",
    "ios:init": "tauri ios init",
    "ios:dev": "tauri ios dev",
    "ios:build": "tauri ios build"
  },
  "devDependencies": {
    "@tauri-apps/cli": "^2.2.0"
  }
}

```

## `backend/sidecar.py`

```python
"""
sidecar.py — entry point for the bundled local backend.

This is what PyInstaller freezes and what Tauri spawns on app launch (local
mode). It starts uvicorn *programmatically* because the `uvicorn` CLI doesn't
exist inside a frozen binary.

Defaults to DEPLOYMENT_MODE=local (the device is the trusted operator) and binds
to loopback only, so nothing is exposed to the network.

Env:
  TERMAID_SIDECAR_HOST   default 127.0.0.1
  TERMAID_SIDECAR_PORT   default 8765
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the project importable whether run from source or frozen.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# A bundled local app is the trusted-operator case → local policy by default.
os.environ.setdefault("DEPLOYMENT_MODE", "local")


def main() -> None:
    import uvicorn
    from backend.main import app  # noqa: WPS433  (import after sys.path setup)

    host = os.environ.get("TERMAID_SIDECAR_HOST", "127.0.0.1")
    port = int(os.environ.get("TERMAID_SIDECAR_PORT", "8765"))
    # Print a line the Tauri side can wait on before loading the UI.
    print(f"TERMAID_SIDECAR_READY http://{host}:{port}", flush=True)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

```

## `backend/runtime.py`

```python
"""
runtime.py — resolve paths that differ between "running from source" and
"running inside a PyInstaller-frozen sidecar binary".

When frozen, PyInstaller extracts bundled data to a temp dir exposed as
`sys._MEIPASS`. We ship the TermAId CLI source + modules under
`<_MEIPASS>/termaid-cli`, so the engine must look there instead of at the
developer's TERMAID_ROOT.
"""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def bundled_root() -> Path | None:
    """The bundled termaid-cli dir when frozen, else None."""
    if not is_frozen():
        return None
    return Path(sys._MEIPASS) / "termaid-cli"  # type: ignore[attr-defined]


def resolve_termaid_root(configured: str | Path) -> Path:
    """Prefer the bundled copy when frozen; otherwise use the configured path."""
    if is_frozen():
        b = bundled_root()
        if b and (b / "modules").is_dir():
            return b
    return Path(configured).resolve()

```

## `scripts/build_sidecar.sh`

```bash
#!/usr/bin/env bash
# Build the local backend sidecar (macOS / Linux) and place it for Tauri.
#   TERMAID_ROOT=/path/to/termaid-complete-windows scripts/build_sidecar.sh
set -euo pipefail
cd "$(dirname "$0")/../backend"
: "${TERMAID_ROOT:?set TERMAID_ROOT to your extracted TermAId CLI project}"
pip install -r requirements.txt pyinstaller
TERMAID_ROOT="$TERMAID_ROOT" pyinstaller termaid-backend.spec --noconfirm
python ../scripts/name_sidecar.py
echo "Done. Now: cd ../desktop-mobile && npm run build"

```

## `scripts/build_sidecar.ps1`

```powershell
# Build the local backend sidecar (Windows 11) and place it for Tauri.
#   $env:TERMAID_ROOT="C:\path\to\termaid-complete-windows"; .\scripts\build_sidecar.ps1
$ErrorActionPreference = "Stop"
if (-not $env:TERMAID_ROOT) { throw "set TERMAID_ROOT to your extracted TermAId CLI project" }
Push-Location "$PSScriptRoot\..\backend"
pip install -r requirements.txt pyinstaller
pyinstaller termaid-backend.spec --noconfirm
python ..\scripts\name_sidecar.py
Pop-Location
Write-Host "Done. Now: cd desktop-mobile; npm run build"

```

## `scripts/fetch_cli.py`

```python
#!/usr/bin/env python3
"""
fetch_cli.py — make the TermAId CLI source available at vendor/termaid-cli so
the sidecar build (PyInstaller) can bundle it. Cross-platform; runs on every CI
runner after setup-python.

Resolution order:
  1. vendor/termaid-cli/modules already present (git submodule or committed) → use it.
  2. env TERMAID_CLI_TARBALL_URL set → download + extract a .tar.gz into vendor/.
  3. env TERMAID_ROOT points at a local dir with modules/ → copy it.
  else: exit non-zero with guidance.

On success, prints the resolved path and writes it to GITHUB_ENV as TERMAID_ROOT.
"""
from __future__ import annotations

import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "termaid-cli"


def _export(path: Path) -> None:
    print(f"TERMAID_ROOT resolved → {path}")
    gh_env = os.environ.get("GITHUB_ENV")
    if gh_env:
        with open(gh_env, "a", encoding="utf-8") as fh:
            fh.write(f"TERMAID_ROOT={path}\n")


def _looks_like_cli(p: Path) -> bool:
    return (p / "modules").is_dir() and (p / "termaid").is_dir()


def main() -> None:
    # 1. already vendored
    if _looks_like_cli(VENDOR):
        _export(VENDOR)
        return

    # 2. tarball URL
    url = os.environ.get("TERMAID_CLI_TARBALL_URL")
    if url:
        VENDOR.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            print(f"downloading {url}")
            urllib.request.urlretrieve(url, tmp.name)
            with tarfile.open(tmp.name) as tf:
                tf.extractall(VENDOR.parent)
        # find the extracted dir that looks like the CLI
        for cand in [VENDOR, *VENDOR.parent.iterdir()]:
            if cand.is_dir() and _looks_like_cli(cand):
                if cand != VENDOR:
                    if VENDOR.exists():
                        shutil.rmtree(VENDOR)
                    cand.rename(VENDOR)
                _export(VENDOR)
                return
        sys.exit("tarball extracted but no termaid CLI (modules/ + termaid/) found")

    # 3. local TERMAID_ROOT
    local = os.environ.get("TERMAID_ROOT")
    if local and _looks_like_cli(Path(local)):
        _export(Path(local).resolve())
        return

    sys.exit(
        "Could not locate the TermAId CLI source. Do one of:\n"
        "  • add it as a git submodule at vendor/termaid-cli\n"
        "  • set repo variable TERMAID_CLI_TARBALL_URL to a .tar.gz of it\n"
        "  • set TERMAID_ROOT to a local checkout"
    )


if __name__ == "__main__":
    main()

```

## `scripts/name_sidecar.py`

```python
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

```
