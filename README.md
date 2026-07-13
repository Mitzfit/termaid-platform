# TermAId — Web Edition

This turns your TermAId terminal assistant into a full-stack web app **without
rewriting any of your 121 modules**. The web layer drives the exact same engine
your REPL drives: `ModuleManager` loads the modules, `get_all_commands()` returns
the `{ "mod.cmd": (module, handler) }` dispatch table, and each `handler(arg)`
still returns a string. The browser is just a new front door.

Validated against your `termaid-v3.22.0` tree: **1948 commands across 119 modules
load with zero errors** through the bridge.

```
web/
├── backend/
│   ├── bridge.py        ← boots TermAId's engine once; the only seam to your code
│   ├── server.py        ← FastAPI: REST + WebSocket + serves the frontend
│   ├── db.py            ← web-tier DB (users, sessions, history) — SQLite, Postgres-ready
│   └── requirements.txt
├── frontend/
│   ├── index.html       ← module palette + web terminal
│   ├── style.css        ← palette derived from your prompt_toolkit theme colors
│   └── app.js           ← WebSocket terminal, syntax lexer, history, auth (no framework)
└── README.md
```

## Run it

```bash
cd web/backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# point the bridge at your TermAId tree (the folder containing termaid/ and modules/)
export TERMAID_ROOT=/path/to/termaid-complete-windows   # Windows: set TERMAID_ROOT=...

uvicorn server:app --reload --port 8000
```

Open http://localhost:8000. Click a command in the left rail or type one in the
prompt. Slash input (`/text.upper hi`) runs a module; plain text goes to the AI
provider (set a key like `GEMINI_API_KEY` first, same as the CLI).

## How the layering works

```
browser  ──WebSocket /ws──►  server.py  ──►  bridge.Engine.execute(line)
   ▲                                              │
   └───────── JSON {output, kind, ok} ◄───────────┘
                                                  │
                          your existing ModuleManager + handlers (unchanged)
```

`bridge.py` is the whole integration. It adds your project root to `sys.path`,
constructs `ModuleManager(modules/)`, loads every discovered module, and routes a
line the same way the REPL's `_handle_command` does — including the
`/mod sub` → `mod.sub` rewrite. Module exceptions are caught per-request so one
bad command can never take the server down, and stdout is captured for the
modules that print instead of returning.

## Backend language: Python is the right call

Keep the backend in **Python**. Your engine, your modules, and your provider
clients are all Python; a different backend language would mean either rewriting
1948 commands or shelling out to Python anyway. **FastAPI** is the pick over
Flask/Django here because it gives you native **WebSocket** support (essential for
a streaming terminal feel) and async I/O for the provider calls, with very little
ceremony.

## Other languages worth adding (and where)

You already have a Rust component (`tools/termaid-splash`), so a polyglot setup
fits your project. In rough priority for *this* app:

- **TypeScript** — the highest-leverage add. The frontend is plain JS today so it
  runs offline on Kali with no build step. The moment the UI grows past a few
  hundred lines (multiple panels, shared state), move `app.js` to TypeScript for
  type-checked API payloads. Pair with Vite only if/when you want a build step.
- **SQL** — not optional once there's a real database. You're already writing it
  in `auth` and `dbkeys`; keep schema/migrations as first-class SQL files rather
  than hiding them in Python strings.
- **Rust** — you have it already. Good for any single hot path that's slow in
  Python (a fast log/packet scanner for `netscan`, hashing, etc.) exposed to the
  backend via a small subprocess or a PyO3 extension. Don't rewrite modules in it
  wholesale — reach for it only where a profiler tells you to.
- **Go** — consider only if you later split a always-on networked piece (a device
  bridge, a websocket fan-out service) into its own daemon. Its concurrency story
  and single-binary deploy are nice there. Skip it otherwise; it'd just be a
  second runtime to babysit.

Bottom line: **Python backend + TypeScript/JS frontend + SQL**, with Rust kept as
the surgical-speed tool you already started using.

## Frontend: your HTML/CSS/JS instinct is correct

For a command-driven tool, plain **HTML/CSS/JS is a feature, not a compromise** —
it loads instantly, has zero supply chain, and runs on a locked-down Kali box with
no Node toolchain. What I built leans into that:

- A **custom web terminal** instead of a heavy library, so the syntax highlighting
  mirrors your actual prompt_toolkit lexer (command blue, subcmd cyan, number
  amber, string green, symbol magenta, flag lavender). The web app reads as the
  same product as the CLI.
- A **live command palette** in the left rail, populated from `/api/commands`,
  filterable, click-to-insert. With 1948 commands, discovery is the real UX
  problem and this solves it.

When to reach for a framework: if you start building stateful dashboards (the
`sysmonitor` / `markets` / `netscan` modules would make great live panels), that's
the point to introduce **React or Svelte** for one section — not the terminal,
which is better as the lean custom widget it is. Svelte is the lighter choice and
fits the offline-friendly ethos better.

## Database: SQLite → Postgres

`db.py` ships on **SQLite** on purpose: zero setup, one file, already proven across
your `auth` and `dbkeys` modules. The schema is written in plain SQL so the upgrade
to Postgres — worth doing once you have concurrent web users or want server-side
deploys — is mechanical:

1. `pip install "psycopg[binary]"` (already commented in `requirements.txt`).
2. In `db.py`, swap the connection helper to psycopg and read a `DATABASE_URL`.
3. Find-and-replace the two dialect differences, both isolated to `db.py`:
   - `INTEGER PRIMARY KEY AUTOINCREMENT` → `BIGINT GENERATED ALWAYS AS IDENTITY`
   - parameter placeholders `?` → `%s`
4. `REAL` timestamps → `TIMESTAMPTZ` if you want proper time types (optional).

Because every query lives in `db.py`, nothing else in the app changes. For your
**modules'** own SQLite data (auth users, dbkeys graph), keep them as-is for now;
migrate them the same way, one module at a time, only if they need to be shared
across web sessions.

## Security notes before you expose this

- Web passwords use PBKDF2-SHA256 (200k iterations) + per-user salt. Fine to start;
  consider `argon2` for production.
- Set `REQUIRE_AUTH=1` to force login before any command runs.
- Some modules touch the filesystem, network, or devices. Before putting this on a
  LAN, decide which modules are safe to expose and gate the rest — the catalog
  endpoint makes it easy to all-/deny-list by module name in `bridge.execute`.
- Add CORS limits and a reverse proxy (caddy/nginx) with TLS when it leaves
  localhost.
```
