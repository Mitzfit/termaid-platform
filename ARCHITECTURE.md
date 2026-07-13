# Termaid Platform — Architecture

Everything below is wired up in this repo. This document is the map, in the
order you'd build and run it.

---

## Platform state (owned by the Master Agent / ops desk)

**Version: 2.3.3.** This section is updated on every accepted hand-back.

Integrated so far:
- **2.3.3 · Config/Architecture** — Flattened workspace alignment. Fixed `launch.json` port mismatch (5173), Vite scripts added to `package.json`, Tauri config paths normalized, enforced spelling convention.
- **2.3.1 · Database** — schema/ORM/migrations documented + hardened (created_at
  server defaults, get_db rollback); model + helper tests. Health 5.8→7.0.
- **2.3.2 · Auth & Security** — refresh-token rotation/revoke-on-use, server-mode
  JWT-secret guard, policy deconflicted (find→SYSTEM-only, SAFE=27). Health 5.9→7.3.
- **2.3.2 · AI & The Brain** — NEW `backend/brain_config.py` (declarative system-
  prompt governor + `wrap_untrusted` injection boundary); cancel/timeout-safe
  streaming + opt-in `events=True`; provider-spec validation. Health 5.9→7.3.

Open cross-window items (must land for the above to be fully enforced):
- Backend Core: wire `/api/auth/refresh` → `auth.rotate_refresh_token`; adopt
  `stream_chat(events=True)`.
- Frontend: store the rotated refresh token.
- Reasoning modules: adopt `wrap_untrusted` + a `BrainConfig` preset.

---

## The stack, in order

```
┌───────────────────────────────────────────────────────────────────┐
│ 1. UI            TypeScript + Vite (strict)        frontend/        │
│                  one web UI → browser, desktop, mobile             │
├───────────────────────────────────────────────────────────────────┤
│ 2. Native shell  Rust / Tauri 2                    desktop-mobile/  │
│                  compiles the UI into Win/mac/Linux + iOS/Android  │
├───────────────────────────────────────────────────────────────────┤
│ 3. API           Python / FastAPI (async)          backend/        │
│                  REST + WebSocket, JWT auth, rate limiting         │
├───────────────────────────────────────────────────────────────────┤
│ 4. Engine        Python                             backend/engine  │
│                  loads your 120 modules once, policy-filtered      │
├───────────────────────────────────────────────────────────────────┤
│ 5. Data          SQL via SQLAlchemy + Alembic       backend/        │
│                  SQLite (dev) → Postgres (prod), real migrations   │
├───────────────────────────────────────────────────────────────────┤
│ 6. Native uplift Rust                               native/         │
│                  fast scanner sidecar for slow Python modules      │
└───────────────────────────────────────────────────────────────────┘
```

### Why each language

| Layer | Language | Why it's the right tool |
|-------|----------|-------------------------|
| Engine + API | **Python** | Your 120 modules already are Python. The command registry is `handler(arg) -> str` — perfect API shape. Zero rewrite. |
| Frontend | **TypeScript** | Types catch the bugs that bite at the API boundary. Strict mode is on; the whole UI type-checks. |
| Native shell + perf | **Rust** | Tauri (Rust) compiles one web UI to every desktop **and** mobile target. Rust also hosts the speed-critical bits (scanning, hashing) that drag in Python. |
| Persistence | **SQL** | One `DATABASE_URL` switches SQLite↔Postgres. Alembic gives you versioned, reversible schema changes. |

---

## 1 → 6: build & run order

```bash
# 1. Backend (Python)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env            # set TERMAID_ROOT, JWT_SECRET, DEPLOYMENT_MODE
alembic upgrade head               # create the schema (SQL migrations)
uvicorn backend.main:app --reload --port 8000

# 2. Frontend (TypeScript)
cd ../frontend
npm install
npm run dev                        # http://localhost:5173 (proxies API+WS to :8000)

# 3. Desktop / mobile app (Rust / Tauri)
cd ../desktop-mobile
npm install
npm run dev                        # native desktop window, hot-reloads the UI
npm run build                      # → installers for the current OS

# 4. Mobile
npm run android:init && npm run android:dev   # needs Android Studio + NDK
npm run ios:init && npm run ios:dev           # needs Xcode (macOS only)

# 5. Native scanner (Rust)
cd ../native
cargo build --release              # → target/release/termaid-scan
```

---

## "What about it running as a local tool?"

Your CLI assumes a trusted operator on their own machine. A network service
doesn't get that assumption. The platform keeps **both** without compromise:

### Deployment modes (`DEPLOYMENT_MODE` in `.env`)

- **`local`** — the app runs on the user's own device (inside the Tauri bundle,
  talking to a `127.0.0.1` Python sidecar). The user *is* the trusted operator,
  so the policy loads everything **except** a tiny deny-list of irreversible
  operations (firmware flashing, privilege escalation, disk wipes). Result here:
  **94 modules / 1459 commands**.

- **`server`** — exposed to remote or multiple users. The policy default-denies:
  only the curated **safe + AI** allow-list is even imported. System, device,
  network-attack, and firmware modules never load. Result here:
  **42 modules / 610 commands**, and e.g. `privesc` simply does not exist on the
  wire.

Both verified against your real modules (`backend/policy.py`). Operators tune the
line with `MODULE_EXTRA_ALLOW` / `MODULE_EXTRA_DENY`.

### Local app, three ways to reach a backend

1. **Bundled sidecar (recommended for "a local tool")** — PyInstaller freezes
   the FastAPI backend into a single binary; Tauri ships it under
   `bundle.externalBin` and spawns it on launch (see `lib.rs` `setup()`). The app
   is then a self-contained desktop/mobile program with no Python install
   required and, with a local Ollama model, no internet either.
2. **Remote server** — point the UI at your hosted API; skip the sidecar.
3. **Plain browser** — the same UI served by FastAPI's static mount.

---

## Streaming AI over WebSocket

`backend/ai_stream.py` adds async, token-by-token streaming for every provider
you already support (Gemini, OpenAI-format, Anthropic, Ollama), reusing your
`PROVIDER_SPECS` so there's one source of truth.

Protocol on `/ws/terminal`:

```
client → {"type":"chat","payload":"explain the TCP handshake"}
server → {"type":"chat_delta","text":"The "}      ← repeated as tokens arrive
server → {"type":"chat_delta","text":"TCP "}
server → {"type":"chat_done"}
```

In the UI, type `? your question` (or `ask …`) to stream a chat; anything else
runs as a module command and returns one result block.

---

## Other recommendations (and what's already in)

**Already implemented**
- ✅ Module allow-list + deployment modes (`policy.py`)
- ✅ Alembic migrations (`backend/migrations/`)
- ✅ Streaming AI over WebSocket (`ai_stream.py`)
- ✅ Per-user rate limiting (in-memory token bucket; swap for Redis at scale)
- ✅ JWT access + refresh with rotation-ready refresh sessions
- ✅ Command-history audit log (great for "which commands actually get used")
- ✅ Strict TypeScript, typed API + WS clients
- ✅ Rust native command (Tauri) + Rust scanner sidecar
- ✅ CI matrix — Python (3.11/3.12) + TypeScript + Rust on every push
  (`.github/workflows/ci.yml`)
- ✅ Cross-platform release pipeline — desktop installers (Win/mac/Linux) +
  Android (`.github/workflows/release.yml`)
- ✅ Test suite — policy, stream-parser, and fake-engine API tests (`backend/tests/`)
- ✅ PyInstaller sidecar so the local app bundles the backend
  (`termaid-backend.spec`, `BUILD_LOCAL_APP.md`)
- ✅ Bundled-sidecar release pipeline that vendors the CLI + freezes the backend
  into the desktop app (`.github/workflows/release-bundled.yml`, `scripts/fetch_cli.py`)
- ✅ First module ported to Rust end-to-end — `netscan`'s port-scan hot path is
  now the `termaid_scan` crate, reachable three ways from one codebase:
  CLI sidecar (Python shells out), backend `/api/scan`, and in-process Tauri
  `native_scan` (the offline-mobile path). Tested on both sides.

- ✅ OS keychain for secrets — provider keys live in Credential Manager / Keychain /
  Secret Service via `backend/secrets.py`, hydrated into the env at startup, with
  graceful env fallback on Termux/headless. CLI: `python -m backend.secrets set ...`
- ✅ Second module ported to Rust — `fsscan`'s directory-walk hot path is now
  `termaid_scan::fs` (`fs.walk` command, `native_walk` Tauri command), proving the
  port pattern scales beyond the first one
- ✅ Per-platform setup guide — `SETUP.md` (Termux, Linux, Windows 11)
- ✅ Split requirements — core / `requirements-termux.txt` (no native-build deps) /
  `requirements-postgres.txt`

- ✅ Multi-provider AI — 12 providers selectable via `AI_PROVIDER` (Gemini Pro/Flash,
  Claude, GPT-4o, Groq, Cerebras, OpenRouter, Ollama + xAI Grok, Together, Fireworks,
  DeepInfra). New ones merged at runtime via `providers_extra.py` — no CLI fork.
- ✅ `.env` keys reach the runtime — a loader pushes `.env` values into the
  environment so provider keys actually work without manual `export` (`settings.py`).

**Worth adding next**
- **CI/CD** — GitHub Actions: `pytest` + `tsc` + `cargo build` on push; Tauri's
  cross-platform build matrix for releases. (You already use GitHub heavily.)
- **Secrets** — move provider keys out of `.env` into the OS keychain on desktop
  (Tauri `keyring`) / platform secure storage on mobile.
- **Redis** — shared rate-limit + refresh-token revocation list once you run more
  than one backend process.
- **Audit/quotas per user** — you already log every command; add per-user daily
  token budgets for AI calls.
- **PWA fallback** — ship the Vite app as an installable PWA so even
  no-app-store users get an "installed" experience.
- **Observability** — structured logging + an `/api/metrics` Prometheus endpoint.
- **Tests for the web layer** — `httpx.AsyncClient` against the FastAPI app;
  a Playwright smoke test for the terminal.

---

## Security posture (read before exposing publicly)

- Generate a real `JWT_SECRET` (`openssl rand -hex 32`).
- Keep `DEPLOYMENT_MODE=server` for anything internet-facing.
- The deny-list in `policy.py` is conservative on purpose — widen it
  deliberately, never blanket-allow.
- Rate limiting is per-user and in-memory; behind multiple workers, move it to
  Redis or it resets per process.
- Sidecar/local mode trusts the device — that's the point — so don't reuse a
  "local" build's permissive policy for a hosted deployment.
