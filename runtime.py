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
