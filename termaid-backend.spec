# termaid-backend.spec — PyInstaller spec for the local sidecar.
#
# Build:
#   pip install pyinstaller
#   cd backend
#   pyinstaller termaid-backend.spec --noconfirm
#
# Produces: dist/termaid-backend(.exe)
#
# Key challenges this spec handles:
#   1. Your modules load DYNAMICALLY via importlib from .py files on disk, so
#      they must ship as DATA FILES (not frozen bytecode). We bundle the whole
#      termaid-cli tree under "termaid-cli/" and runtime.py points the engine
#      there via sys._MEIPASS.
#   2. uvicorn, passlib's bcrypt backend, and the async DB drivers are imported
#      dynamically — PyInstaller misses them, so they're listed as hiddenimports.
#
# Set TERMAID_ROOT below to your extracted CLI project before building.

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# --- locate the TermAId CLI project to bundle ---
TERMAID_ROOT = os.environ.get(
    "TERMAID_ROOT",
    str(Path(".").resolve().parents[1] / "termaid-complete-windows"),
)
cli = Path(TERMAID_ROOT).resolve()
assert (cli / "modules").is_dir(), f"modules/ not found under {cli}"

# Ship the termaid package + all 120 module folders as data under termaid-cli/.
datas = [
    (str(cli / "termaid"), "termaid-cli/termaid"),
    (str(cli / "modules"), "termaid-cli/modules"),
]

# Dynamically-imported deps PyInstaller can't see by static analysis.
hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("anyio")
    + [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan.on",
        "passlib.handlers.bcrypt",
        "bcrypt",
        "aiosqlite",
        "asyncpg",
        "httpx",
        "jose.backends.cryptography_backend",
    ]
)
datas += collect_data_files("passlib")


a = Analysis(
    ["sidecar.py"],
    pathex=[str(Path(".").resolve().parents[0])],  # project root, so `backend` imports
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="termaid-backend",
    console=True,            # keep a console so Tauri can read the READY line
    onefile=True,
    upx=True,
    target_arch=None,        # native arch; CI sets per-runner
)
