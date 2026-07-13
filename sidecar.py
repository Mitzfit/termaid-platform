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
