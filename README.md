# TermAId

A terminal-native AI assistant: a FastAPI backend drives a modular command
engine (115 modules, 854 commands) over REST + WebSocket, with an auth layer,
rate limiting, and a four-tier deployment-safety policy that gates what's
reachable depending on who's running it and where. It's exposed as a web app
(the backend serves the built frontend directly) and, since this pass, also
as a Tauri desktop shell with an in-process Rust path for scan/directory-walk
that works even without the Python backend running.

```
Termaid/
├── backend/                ← the actual running service
│   ├── main.py                FastAPI app: auth, /api/exec, /ws/terminal
│   ├── engine.py               Loads modules, dispatches "mod.cmd args" → handler(arg)
│   ├── policy.py                 SAFE / AI / SYSTEM / DANGEROUS module tiers
│   ├── settings.py                 Env config (.env): mode, AI provider, module overrides
│   ├── auth.py                       JWT auth (register/login/refresh)
│   └── database.py                    Users, sessions, command history (SQLite)
├── termaid-cli/
│   ├── termaid/extensions/       Module base class + ModuleManager (the loader)
│   └── modules/                    Every command module lives here, one folder each
├── frontend/                ← web UI + Tauri desktop shell (see "Frontend" below)
│   ├── src/                    Vanilla-TS terminal UI (api.ts, ws.ts, main.ts...)
│   ├── src-tauri/                Rust desktop host (native_scan/native_walk commands)
│   └── dist/                       Vite build output the backend serves at `/`
├── native/                  ← termaid_scan: Rust scan/walk, used by both
│   │                            the backend (as a CLI it can shell out to) and
│   │                            the Tauri app (in-process, offline-capable)
├── run_backend.py           ← entry point: `python run_backend.py`
└── .env                      Deployment mode + which module tiers are opted in
```

`_archive/` (superseded scaffolding — an older, fully duplicate `termaid-platform/`
tree with its own git history and planning docs, kept rather than deleted)
and `mobile/`/`mnt/` (a separate, currently-unused mobile API client and
misc uploads) round out the repo but aren't part of the running system.

## Run it

```bash
python -m venv .venv && .venv\Scripts\activate     # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
python run_backend.py
```

This starts uvicorn on `http://127.0.0.1:8000` with hot reload. Register a
user, log in (form-encoded, not JSON — see `/api/auth/login`), then either
hit `POST /api/exec` with `{"command": "calc.calc 2+2"}` or open a WebSocket
at `/ws/terminal?token=<access_token>` and send `{"type":"exec","payload":"..."}`.

## Command model

Every module is a Python class implementing `on_load()` (registers its
commands) and one `cmd_<name>(self, arg: str) -> str` method per command.
`ModuleManager` discovers module folders under `modules/`, imports each as
`modules.<name>`, instantiates the one `Module` subclass it finds, and
canonicalizes `instance.name` to the folder name — so a command is always
addressed as `<folder-name>.<command>`, e.g. `/calc.calc 2+2` or
`/git.status`. AI-capable modules get `self.ai` / `self.ask_ai(prompt,
system=)` if an `AI_PROVIDER` is configured; otherwise they degrade to
"no AI configured" rather than erroring.

## The four module tiers (`backend/policy.py`)

| Tier | Count | What it means |
|---|---|---|
| **SAFE** | 27 | Pure compute or own-data-only (calc, text, password, notes...). Loads everywhere. |
| **AI** | 12 | Needs an AI provider but is otherwise side-effect-free (brain, cognition, aiconfig...). |
| **SYSTEM** | 48 | Touches the host — filesystem, network, processes, git/docker (find, netscan, bots, vm, sandbox...). Local mode only. |
| **DANGEROUS** | 28 | Irreversible or privilege-escalating (syscmd, fastboot, disktool, selfmod, fswrite, crypto...). Local mode *and* explicit per-module opt-in required. |

Two deployment modes, set via `.env`'s `DEPLOYMENT_MODE`:

- **`local`** (default) — default-allow, except DANGEROUS modules, which need
  to be named individually in `MODULE_EXTRA_ALLOW` (comma-separated) even
  here. This machine's `.env` currently opts in all 27 DANGEROUS modules for
  testing — trim that list down to just what you actually want reachable
  before leaving it running unattended.
- **`server`** — default-deny; only SAFE + AI modules load. SYSTEM and
  DANGEROUS modules are never even imported. Use this if TermAId will be
  reachable by anyone other than the machine's own operator.

Every genuinely destructive command (in any tier) additionally requires a
literal `confirm` argument — or, for a handful of irreversible hardware
operations (`fastboot flash`, `disktool format`), a longer explicit
acknowledgement string — checked in the handler itself, on top of the tier
gating above.

## Root/admin account

One seeded account can manage other users and view system health — set
`ADMIN_USERNAME`/`ADMIN_PASSWORD` in `.env` (both default to a `CHANGE_ME_...`
sentinel, which disables this entirely — no default admin account is ever
created). Once set, that account is created (or re-affirmed: `is_admin` and
its password are re-applied every boot, so `.env` is always the source of
truth) on backend startup, and that exact username can never be claimed via
self-service `/api/auth/register` — there's no "first user becomes admin"
race, by design.

Log in as that account like any other user, then:
- `GET /api/admin/users`, `POST /api/admin/users/{id}/disable|enable`,
  `DELETE /api/admin/users/{id}` — manage other accounts (self-disable/delete
  is refused).
- `GET /api/admin/health` — engine status merged with the `debug` module's
  process/thread introspection.
- In the terminal UI: `admin-users` / `admin-health` (403s cleanly for
  non-admins).

This is a distinct concept from the `admin` CLI module (`/admin.status`,
`/admin.add-admin`, etc.), which manages OS-level Administrator/sudo group
membership on the host machine — same word, unrelated systems.

## Frontend

`frontend/` is a small, framework-free TypeScript terminal UI (login panel →
command line, streaming AI chat, command history). Two ways to run it:

- **Web, via the backend**: `cd frontend && npm run build`, then start the
  backend as above — `backend/main.py` mounts `frontend/dist/` at `/` when it
  exists, so the whole thing is served from `http://127.0.0.1:8000`.
- **Web, standalone dev server**: `cd frontend && npm run dev` — Vite on
  `:5173`, proxying `/api` and `/ws` to the backend on `:8000` (both must be
  running; see `vite.config.ts`).
- **Desktop (Tauri)**: `cd frontend && npm run tauri dev` — opens a native
  window around the same UI. Requires a Rust toolchain with a working linker
  (MSVC Build Tools on Windows) and pulls in `native/` (the `termaid_scan`
  crate) as an in-process dependency: `scan`/`walk` in the terminal call
  Rust directly (`native_scan`/`native_walk` Tauri commands) instead of going
  over HTTP, so they still work with the Python backend stopped — the
  offline/mobile-capable path. In a plain browser those same commands fall
  back to `/api/scan` and `/api/exec`.
- Production bundling (`tauri build`) and mobile targets (`tauri android/ios`)
  aren't set up yet — `tauri init`'s placeholder icons are fine for `dev` but
  not a real release, and shipping the Python backend as a bundled sidecar
  binary (the `externalBin` the original `tauri.conf.json` sketched out) would
  need a PyInstaller build of `run_backend.py` first. Mobile additionally
  needs the Android SDK / Xcode, neither installed here.

## Security notes

- Passwords are bcrypt-hashed (`passlib`); `bcrypt<4.1` is pinned in
  `requirements.txt` — newer bcrypt breaks passlib's own self-test on
  register/login.
- JWT access + refresh tokens; set a real `JWT_SECRET` in `.env` before
  this leaves your machine (the shipped one is `dev_only_...`).
- Rate limiting is enforced per-user on `/api/exec`.
- `GET /api/blocked` shows exactly what's disabled in the current mode and
  why — check it after any policy or module-tier change.
