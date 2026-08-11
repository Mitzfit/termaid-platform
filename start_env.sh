#!/bin/bash
cd ~/termaid-platform
source .venv/bin/activate
echo "[*] Starting TermAId Pro Backend Engine..."
PYTHONPATH=".:./termaid-cli" uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
echo "[*] Starting TermAId Pro Desktop Frontend..."
npm run dev --prefix frontend &
echo "[+] TermAId Pro is online! Access via http://localhost:5173"
