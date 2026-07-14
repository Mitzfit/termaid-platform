# TermAId

A terminal-native AI assistant, exposed as a web app: a FastAPI backend drives
a modular command engine (114 modules, 783 commands) over REST + WebSocket,
with an auth layer, rate limiting, and a four-tier deployment-safety policy
that gates what's reachable depending on who's running it and where.

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
├── run_backend.py           ← entry point: `python run_backend.py`
└── .env                      Deployment mode + which module tiers are opted in
```

Everything else at the repo root (`bridge.py`, `app.js`, `native.py`,
`termaid-platform/`, the `*_Agent_Kit.md` files, tarballs, PDFs) is leftover
scaffolding from an earlier, incomplete build attempt and isn't part of the
running system — the two directories above are what actually executes.

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
| **DANGEROUS** | 27 | Irreversible or privilege-escalating (syscmd, fastboot, disktool, selfmod, crypto...). Local mode *and* explicit per-module opt-in required. |

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

## Security notes

- Passwords are bcrypt-hashed (`passlib`); `bcrypt<4.1` is pinned in
  `requirements.txt` — newer bcrypt breaks passlib's own self-test on
  register/login.
- JWT access + refresh tokens; set a real `JWT_SECRET` in `.env` before
  this leaves your machine (the shipped one is `dev_only_...`).
- Rate limiting is enforced per-user on `/api/exec`.
- `GET /api/blocked` shows exactly what's disabled in the current mode and
  why — check it after any policy or module-tier change.
