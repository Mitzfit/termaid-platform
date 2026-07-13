# TermAId Platform

Your TermAId CLI, evolved into a full platform: a typed web UI that compiles to
**desktop and mobile native apps**, a policy-guarded Python API over your
existing 120 modules, streaming AI, and SQL migrations — without changing a line
of your `termaid/` package.

See **[ARCHITECTURE.md](./ARCHITECTURE.md)** for the full picture in order, and **[SETUP.md](./SETUP.md)** for step-by-step install on Termux / Linux / Windows.

```
termaid-platform/
├── ARCHITECTURE.md          ← read this first
├── backend/                 Python · FastAPI · SQLAlchemy · Alembic
│   ├── engine.py            loads your modules, policy-filtered
│   ├── policy.py            allow-list + local/server modes  ← "local tool" answer
│   ├── ai_stream.py         streaming AI over WebSocket
│   ├── main.py              REST + WS + auth + rate limiting
│   └── migrations/          Alembic (alembic upgrade head)
├── frontend/                TypeScript · Vite (strict, type-checked)
│   └── src/{api,ws,terminal,main}.ts
├── desktop-mobile/          Rust · Tauri 2 → Win/mac/Linux + iOS/Android
│   └── src-tauri/src/lib.rs native commands + sidecar setup
└── native/                  Rust · termaid-scan fast scanner sidecar
```

## 60-second start (web, dev)

```bash
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env          # set TERMAID_ROOT + JWT_SECRET
alembic upgrade head
uvicorn backend.main:app --reload --port 8000        # terminal 1

cd ../frontend && npm install && npm run dev          # terminal 2 → :5173
```

Register, then try `calc.hex 255`, `text.upper hello`, or `? explain TCP` (the
`?` prefix streams an AI answer if you've set `AI_PROVIDER`).

## Build the native apps

```bash
cd desktop-mobile && npm install
npm run build          # desktop installer for your OS
npm run android:init && npm run android:build   # Android (needs Studio+NDK)
npm run ios:init && npm run ios:build           # iOS (needs Xcode, macOS)
```

## What was verified in this build

- Engine loads **120 modules / 1948 commands** from your real package.
- Policy: **server → 42 mods / 610 cmds**, **local → 94 mods / 1459 cmds**;
  `privesc` blocked in both.
- All backend Python compiles; TypeScript passes `tsc` strict.
- Rust (Tauri shell + scanner) is written against Tauri 2 / stable Rust but was
  not compiled here (no Rust toolchain in the build sandbox) — `cargo build`
  on your machine is the check.
