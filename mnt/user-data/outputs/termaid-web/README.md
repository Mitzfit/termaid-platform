# TermAId Web

A full-stack web layer for your existing **TermAId** CLI — Python + database
backend, vanilla HTML/CSS/JS terminal frontend. It reuses your `termaid/`
package and all 120 modules **without changing a single line of them**.

---

## Why this works so cleanly

Your CLI is already built on a command registry where every command has the
shape:

```python
handler(arg: str) -> str
```

That is *exactly* the shape a web request handler wants. So the web backend
doesn't reimplement anything — it loads your modules once at startup and maps
incoming `mod.cmd args` strings straight onto your existing handlers.

Verified against the real package: **120 modules load, 1948 commands dispatch.**

```
Browser  ──HTTP/WebSocket──▶  FastAPI  ──▶  Engine  ──▶  your ModuleManager
(HTML/CSS/JS terminal)         (REST + WS)   (thin wrap)    (unchanged code)
                                  │
                                  ▼
                            SQLAlchemy ──▶ SQLite (dev) / Postgres (prod)
                            users · sessions · command history
```

---

## Quick start (local, SQLite, ~2 min)

```bash
cd termaid-web
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

cp .env.example .env
# edit .env: set TERMAID_ROOT to your extracted CLI folder, set a real JWT_SECRET
#   openssl rand -hex 32

uvicorn backend.main:app --reload --port 8000
```

Open <http://localhost:8000>, click **register**, then run commands like
`calc.hex 255`, `text.upper hello`, `regex.test \d+ abc123`, or `help`.

## Production (Docker + Postgres)

```bash
export JWT_SECRET=$(openssl rand -hex 32)
docker compose up --build
```

This mounts your CLI project read-only into the container and runs Postgres
alongside the API.

---

## What's in the box

| Path | Purpose |
|------|---------|
| `backend/engine.py` | Loads modules once, dispatches `mod.cmd → str`. The bridge. |
| `backend/main.py` | FastAPI app: REST `/api/exec`, `/api/commands`, `/api/history`, auth, and a `/ws/terminal` WebSocket for the live REPL feel. |
| `backend/database.py` | Async SQLAlchemy engine; one env var switches SQLite↔Postgres. |
| `backend/models.py` | `User`, `CommandHistory`, `RefreshSession` tables. |
| `backend/auth.py` | bcrypt hashing + JWT access/refresh tokens. |
| `frontend/` | Vanilla HTML/CSS/JS web terminal — no build step, no framework. |

### API surface

```
POST /api/auth/register     {username, password}        → user
POST /api/auth/login        form: username, password     → {access, refresh}
POST /api/auth/refresh      {refresh_token}              → {access, refresh}
POST /api/exec              {command}                    → {ok, module, output, ms}
GET  /api/commands                                       → all 1948 commands
GET  /api/modules                                        → module metadata
GET  /api/history?limit=50                               → your recent commands
WS   /ws/terminal?token=<access>                         → live terminal stream
```

---

## Enabling the AI commands

Many modules call AI. To turn those on, set in `.env`:

```
AI_PROVIDER=gemini-flash
GEMINI_API_KEY=your_key
```

The engine builds a real `AIClient` from your existing `termaid/providers`
and hands it to every module — same code path as the CLI.

---

## Recommended next steps

1. **Alembic** for real DB migrations (right now tables are auto-created on
   startup, which is fine for dev, risky for prod schema changes).
2. **Per-command authorization** — some of your modules touch the host system
   (`privesc`, `netscan`, `disktool`, `fwown`…). On a server you almost
   certainly want an allow-list of web-safe modules and to gate the rest behind
   admin or disable them entirely. Add a `WEB_ENABLED_MODULES` set in
   `settings.py` and filter in `engine.load_all()`.
3. **Rate limiting** (slowapi) on `/api/exec` and the WebSocket.
4. **Streaming AI output** — upgrade AI commands to stream tokens over the
   existing WebSocket instead of returning one block.

---

## A note on safety

Your CLI runs as a trusted local tool. A web server is a different threat
model: anything that shells out, scans networks, or modifies firmware should
**not** be exposed to arbitrary authenticated users without an explicit
allow-list. Start with the pure-compute modules (`calc`, `text`, `regex`,
`diff`, `json`, `qr`, `password`, `base`…) and add others deliberately.
