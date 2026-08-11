#!/bin/bash
echo "[+] Starting Termaid Pro Ecosystem..."
source .venv/bin/activate
PYTHONPATH=".:./termaid-cli" uvicorn backend.main:app --host 0.0.0.0 --port 8000 &
sleep 2
npm run dev --prefix frontend &
echo "[+] All systems online. Awaiting connection."
wait
