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
