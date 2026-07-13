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
