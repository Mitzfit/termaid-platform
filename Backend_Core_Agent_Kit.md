# Agent 02 — Backend Core & API (complete kit)

Attach this single file to the Backend Core agent window (or add to project knowledge). Contains the brief, baseline, start prompt, and all owned source.

---

# Agent 02 — Backend Core & API

**Role:** Backend engineer. The FastAPI app + the engine that loads the 120
modules and dispatches commands. The hub the frontend and CLI talk to.
**Baseline health:** 5.7 / 10 (set 2026-06-13).

## Owns
- `backend/main.py` — FastAPI app: REST (auth, /api/exec, /api/scan), WebSocket,
  streaming chat, lifespan, rate limit wiring.
- `backend/engine.py` — loads policy-permitted modules ONCE; native-command
  registry; command dispatch.
- `backend/schemas.py` — Pydantic request/response models (mirror models.py).

## Depends on / feeds
- Reads: Database (models/schema), Auth (auth + policy), AI (streaming).
- Feeds: Frontend (the API contract), Desktop/Mobile (sidecar).

## Inherited cross-window TODOs (from Database v2.3.1) — pick these up
- CI contract test diffing `models.py ↔ schemas.py ↔ types.ts` (you own schemas.py;
  coordinate with Frontend + QA). This is the platform's #1 cohesion risk.
- Confirm production startup uses `alembic upgrade head`, NOT `init_models()`.

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md
(incl. the Termaid spelling rule). Never touch another window's files.


---

# Health Report — Backend Core & API  (BASELINE, v2.3.1, 2026-06-13)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | Engine loads 120 modules; API exercised by test_api in CI. Dispatch edge cases untested. |
| Security | 6 | Wires auth + policy (owned elsewhere). Rate limit is in-memory (per-process); dev CORS permissive. |
| Performance | 7 | Modules load once at startup; async throughout. No profiling. |
| Architecture / maintainability | 6 | Clean layering but engine is a module global; main.py mixes concerns (routes + wiring). |
| Test coverage | 3 | Only test_api; no unit tests for engine dispatch / policy filtering / schema validation. |
| Documentation | 4 | File headers present; per-route / per-function docs thin. |
| Cross-window cohesion | 6 | schemas.py mirrors models.py UNENFORCED (inherited top risk). |
| **Overall** | **5.7** | Solid, working core; under-tested and under-documented, with the schema contract still unguarded. |

## Top 3 risks
1. Unenforced models↔schemas↔types contract — a field change diverges silently.
2. main.py concern-mixing — routes, auth wiring, rate limit, streaming in one file.
3. Thin tests — dispatch, policy filtering, and error paths unverified.

## Highest-value next action
Directive 1 (document main.py + engine.py + schemas.py to CODE_STYLE, Misfit) +
add engine/dispatch unit tests → target Documentation 4→8, Test coverage 3→6.
Then scope the CI contract test (with Frontend + QA).


---

## START PROMPT (paste into the new agent window)

```
This is the BACKEND CORE & API agent.

Your role: backend engineer. You own backend/main.py (FastAPI app, routes, WS,
streaming, rate-limit wiring, lifespan), backend/engine.py (loads the 120 modules
once, policy-aware, dispatch), and backend/schemas.py (Pydantic models that mirror
the DB). Work ONLY on these files; never touch another window's.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md (note the Termaid spelling rule), LESSONS.md, and
this agent's BASELINE_HEALTH.md.

Then run the kickoff brainstorm (BRAINSTORM_TEMPLATE.md) and follow the four
directives in order: 1) Document every file (what/does/why, attributed to Misfit),
2) Break down (BREAKDOWN.md), 3) Harden, 4) Health report.

Inherited cross-window TODOs to consider this session:
- CI contract test diffing models.py ↔ schemas.py ↔ types.ts (you own schemas.py).
- Confirm prod startup uses `alembic upgrade head`, not init_models().

Hand back with HANDOFF_TEMPLATE.md + updated files (as .py text, not PDF) + INDEX.md
+ BREAKDOWN + health report + appended HISTORY. Bump the version.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```

---

## OWNED SOURCE CODE

### `backend/main.py`

```python
"""
main.py — FastAPI application (policy-aware + streaming).

REST:
  POST /api/auth/register | login | refresh
  POST /api/exec                run one module command
  GET  /api/commands           list permitted commands
  GET  /api/modules            module metadata (+ category)
  GET  /api/blocked            what's disabled here and why
  GET  /api/history            caller's recent commands
  GET  /api/health             liveness + engine status

WebSocket  /ws/terminal?token=<access>
  client → {"type":"exec","payload":"calc.hex 255"}
  client → {"type":"chat","payload":"explain TCP handshake"}
  server → {"type":"result", ok, module, output, ms}
  server → {"type":"chat_delta","text":"..."}  (repeated)
  server → {"type":"chat_done"}

Run:  uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import datetime as dt
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import (
    Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth, schemas
from . import native
from . import secrets
from .providers_extra import merge_into_cli_specs
from .ai_stream import stream_chat
from .database import SessionLocal, get_db, init_models
from .engine import Engine
from .runtime import resolve_termaid_root, is_frozen
from .models import CommandHistory, RefreshSession, User
from .settings import settings

# One shared engine. Modules load once, filtered by the deployment policy.
engine = Engine(
    termaid_root=resolve_termaid_root(settings.termaid_root),
    mode=settings.deployment_mode,
    ai_provider=settings.ai_provider,
    extra_allow=settings.extra_allow_set,
    extra_deny=settings.extra_deny_set,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    loaded = secrets.hydrate_env()
    if loaded:
        print(f"[startup] hydrated {loaded} provider key(s) from the OS keychain")
    added = merge_into_cli_specs()
    if added:
        print(f"[startup] added {added} extra AI provider(s): xai, together, fireworks, deepinfra")
    report = engine.load_all()
    # Wire the Rust scanner in as a native command — but only in local mode,
    # since exposing a port scanner to remote users invites abuse.
    if engine.mode == "local" and native.is_available():
        engine.register_native(
            "scan.ports", _scan_command, module="scan",
            description="fast Rust TCP port scan: scan.ports <host> [start] [end]",
        )
        if native.walker_path():
            engine.register_native(
                "fs.walk", _walk_command, module="fs",
                description="fast Rust directory walk: fs.walk <path> [top_n]",
            )
        print("[startup] native Rust commands registered (scan.ports, fs.walk)")
    print(f"[startup] mode={report['mode']} loaded={report['loaded']} "
          f"blocked={report['blocked']} commands={len(engine.commands())} "
          f"ai={'on' if engine.has_ai() else 'off'}")
    yield


def _scan_command(arg: str) -> str:
    """Terminal handler: 'scan.ports <host> [start] [end] [timeout_ms]'."""
    parts = arg.split()
    if not parts:
        return "usage: scan.ports <host> [start] [end] [timeout_ms]"
    host = parts[0]
    start = int(parts[1]) if len(parts) > 1 else 1
    end = int(parts[2]) if len(parts) > 2 else 1024
    timeout = int(parts[3]) if len(parts) > 3 else 300
    return native.format_scan(native.scan_ports(host, start, end, timeout))


def _walk_command(arg: str) -> str:
    """Terminal handler: 'fs.walk <path> [top_n]'."""
    parts = arg.split()
    if not parts:
        return "usage: fs.walk <path> [top_n]"
    path = parts[0]
    top_n = int(parts[1]) if len(parts) > 1 else 10
    return native.format_walk(native.walk_dir(path, top_n))


app = FastAPI(title="TermAId Platform", version="2.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Tiny in-memory rate limiter (per user). Swap for Redis in a scaled deploy.
# --------------------------------------------------------------------------- #
_buckets: dict[int, list[float]] = defaultdict(list)


def _rate_ok(user_id: int) -> bool:
    now = time.time()
    window = _buckets[user_id]
    window[:] = [t for t in window if now - t < 60]
    if len(window) >= settings.exec_rate_per_minute:
        return False
    window.append(now)
    return True


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.post("/api/auth/register", response_model=schemas.UserOut)
async def register(body: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username taken")
    user = User(username=body.username, email=body.email,
                password_hash=auth.hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@app.post("/api/auth/login", response_model=schemas.TokenPair)
async def login(form: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == form.username))).scalar_one_or_none()
    if not user or not auth.verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")
    user.last_login = dt.datetime.now(dt.timezone.utc)
    access = auth.create_access_token(user.id)
    refresh, token_id, expires = auth.create_refresh_token(user.id)
    db.add(RefreshSession(user_id=user.id, token_id=token_id, expires_at=expires))
    await db.commit()
    return schemas.TokenPair(access_token=access, refresh_token=refresh)


@app.post("/api/auth/refresh", response_model=schemas.TokenPair)
async def refresh_token(body: schemas.RefreshIn, db: AsyncSession = Depends(get_db)):
    payload = auth.decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    sess = (await db.execute(
        select(RefreshSession).where(RefreshSession.token_id == payload.get("jti"))
    )).scalar_one_or_none()
    if not sess or sess.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")
    return schemas.TokenPair(
        access_token=auth.create_access_token(int(payload["sub"])),
        refresh_token=body.refresh_token,
    )


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
async def _record(db: AsyncSession, user_id: int, result: dict) -> None:
    db.add(CommandHistory(
        user_id=user_id, command=result.get("command") or "",
        module=result.get("module"), output=(result.get("output") or "")[:8000],
        ok=result.get("ok", False), duration_ms=result.get("ms", 0.0),
    ))
    await db.commit()


@app.post("/api/exec", response_model=schemas.CommandOut)
async def exec_command(
    body: schemas.CommandIn,
    user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not _rate_ok(user.id):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limit exceeded")
    result = engine.execute(body.command)
    result.setdefault("command", body.command.strip().lstrip("/").split(maxsplit=1)[0])
    await _record(db, user.id, result)
    return result


@app.get("/api/commands")
async def list_commands(user: User = Depends(auth.get_current_user)):
    return {"count": len(engine.commands()), "commands": engine.commands()}


@app.get("/api/modules")
async def list_modules(user: User = Depends(auth.get_current_user)):
    return engine.modules()


@app.get("/api/blocked")
async def list_blocked(user: User = Depends(auth.get_current_user)):
    return {"mode": engine.mode, "blocked": engine.blocked()}


@app.get("/api/history", response_model=list[schemas.HistoryItem])
async def history(
    limit: int = 50,
    user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(CommandHistory).where(CommandHistory.user_id == user.id)
        .order_by(CommandHistory.created_at.desc()).limit(min(limit, 200))
    )).scalars().all()
    return rows


@app.get("/api/health")
async def health():
    return {"status": "ok", "mode": engine.mode,
            "commands": len(engine.commands()), "ai": engine.has_ai()}


@app.post("/api/scan")
async def scan(
    body: schemas.ScanIn,
    user: User = Depends(auth.get_current_user),
):
    """Structured Rust port scan. Local mode only (network action)."""
    if engine.mode != "local":
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "scanning is disabled in server mode")
    if not native.is_available():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "scanner binary not built (cd native && cargo build --release)")
    return native.scan_ports(body.host, body.start, body.end, body.timeout_ms)


# --------------------------------------------------------------------------- #
# WebSocket terminal — module dispatch + streaming AI chat
# --------------------------------------------------------------------------- #
@app.websocket("/ws/terminal")
async def ws_terminal(ws: WebSocket):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4401)
        return
    try:
        payload = auth.decode_token(token)
        user_id = int(payload["sub"])
    except Exception:
        await ws.close(code=4401)
        return

    await ws.accept()
    await ws.send_json({"type": "banner",
                        "text": f"TermAId [{engine.mode}] — {len(engine.commands())} commands, "
                                f"AI {'enabled' if engine.has_ai() else 'disabled'}."})
    try:
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            payload_text = (msg.get("payload") or "").strip()

            if kind == "chat":
                if not engine.has_ai():
                    await ws.send_json({"type": "chat_delta",
                                        "text": "[AI disabled: set AI_PROVIDER + key]"})
                    await ws.send_json({"type": "chat_done"})
                    continue
                full = []
                async for chunk in stream_chat(settings.ai_provider, payload_text):
                    full.append(chunk)
                    await ws.send_json({"type": "chat_delta", "text": chunk})
                await ws.send_json({"type": "chat_done"})
                async with SessionLocal() as db:
                    await _record(db, user_id, {
                        "command": "chat", "module": "ai", "ok": True,
                        "output": "".join(full)[:8000], "ms": 0.0})

            else:  # exec
                if not _rate_ok(user_id):
                    await ws.send_json({"type": "result", "ok": False,
                                        "output": "rate limit exceeded", "ms": 0.0})
                    continue
                result = engine.execute(payload_text)
                result["command"] = payload_text.lstrip("/").split(maxsplit=1)[0] if payload_text else ""
                await ws.send_json({"type": "result", **result})
                async with SessionLocal() as db:
                    await _record(db, user_id, result)
    except WebSocketDisconnect:
        return


# Serve the built frontend (Vite build output) when present.
import os
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")

```

### `backend/engine.py`

```python
"""
engine.py — Headless wrapper around TermAId's existing module system,
now policy-aware.

Loads modules ONCE at startup, but only the ones the deployment policy permits
(see policy.py). Each command stays a simple `handler(arg: str) -> str`, so the
web layer changes nothing inside your `termaid/` package or `modules/`.

Proven against the real package: 120 modules discovered, 1948 commands.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Optional

from .policy import allowed_modules, AI_MODULES, SAFE_MODULES, SYSTEM_MODULES, DANGEROUS_MODULES


class Engine:
    def __init__(
        self,
        termaid_root: str | Path,
        mode: str = "server",
        ai_provider: Optional[str] = None,
        extra_allow: Optional[set[str]] = None,
        extra_deny: Optional[set[str]] = None,
    ):
        self.root = Path(termaid_root).resolve()
        self.modules_dir = self.root / "modules"
        self.mode = mode
        self.ai_provider = ai_provider
        self.extra_allow = extra_allow or set()
        self.extra_deny = extra_deny or set()

        self._cmds: dict = {}      # "mod.cmd" -> (module_instance, handler)
        self._native: dict = {}    # "mod.cmd" -> (module_name, handler(arg)->str)
        self._meta: dict = {}      # module name -> {version, description, commands, category}
        self._blocked: dict = {}   # module name -> reason
        self._ai = None

        for p in (str(self.root), str(self.modules_dir)):
            if p not in sys.path:
                sys.path.insert(0, p)

    # ------------------------------------------------------------------ #
    def _category(self, name: str) -> str:
        if name in DANGEROUS_MODULES:
            return "dangerous"
        if name in SYSTEM_MODULES:
            return "system"
        if name in AI_MODULES:
            return "ai"
        if name in SAFE_MODULES:
            return "safe"
        return "uncategorised"

    def _build_ai(self):
        if not self.ai_provider:
            return None
        try:
            from termaid.providers import get_provider  # type: ignore
            return get_provider(self.ai_provider)
        except Exception as e:  # pragma: no cover
            print(f"[engine] AI provider '{self.ai_provider}' unavailable: {e}")
            return None

    def load_all(self) -> dict:
        from termaid.extensions import ModuleManager  # type: ignore
        import termaid.extensions  # noqa: F401

        self._ai = self._build_ai()
        mm = ModuleManager(self.modules_dir)
        discovered = mm.discover()

        permitted, blocked = allowed_modules(
            discovered, self.mode, self.extra_allow, self.extra_deny
        )
        self._blocked = blocked

        ok, failed = [], []
        for name in sorted(permitted):
            info = mm.load(name, ai=self._ai)
            if info.enabled:
                ok.append(name)
                self._meta[info.name] = {
                    "version": info.version,
                    "description": info.description,
                    "commands": info.commands,
                    "category": self._category(name),
                }
            else:
                failed.append({"name": name, "error": info.error[:200]})

        self._cmds = mm.get_all_commands()
        self._mm = mm
        return {
            "mode": self.mode,
            "discovered": len(discovered),
            "loaded": len(ok),
            "blocked": len(blocked),
            "failed": len(failed),
            "commands": len(self._cmds),
            "failures": failed,
        }

    # ------------------------------------------------------------------ #
    def register_native(self, name: str, handler, *, module: str, description: str = "") -> None:
        """Register a non-Python-module command (e.g. Rust-backed).
        `handler` has the same shape as module commands: (arg: str) -> str."""
        self._native[name] = (module, handler)
        self._meta.setdefault(module, {
            "version": "native", "description": description,
            "commands": [], "category": "native",
        })
        sub = name.split(".", 1)[1] if "." in name else name
        if sub not in self._meta[module]["commands"]:
            self._meta[module]["commands"].append(sub)

    def commands(self) -> list[str]:
        return sorted(set(self._cmds) | set(self._native))

    def modules(self) -> dict:
        return self._meta

    def blocked(self) -> dict:
        return self._blocked

    def has_ai(self) -> bool:
        return self._ai is not None

    def execute(self, line: str) -> dict:
        start = time.perf_counter()
        line = (line or "").strip().lstrip("/")
        if not line:
            return {"ok": False, "output": "empty command", "ms": 0.0}

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # Native (Rust-backed) commands take precedence and share the str shape.
        nat = self._native.get(cmd)
        if nat is not None:
            mod_name, handler = nat
            try:
                out = handler(arg)
                return {"ok": True, "module": mod_name, "command": cmd,
                        "output": str(out) if out is not None else "",
                        "ms": round((time.perf_counter() - start) * 1000, 2)}
            except Exception as e:
                return {"ok": False, "module": mod_name, "command": cmd,
                        "output": f"error: {e}",
                        "ms": round((time.perf_counter() - start) * 1000, 2)}

        entry = self._cmds.get(cmd)
        if entry is None:
            ms = round((time.perf_counter() - start) * 1000, 2)
            # Helpful: was it blocked by policy rather than nonexistent?
            mod_name = cmd.split(".", 1)[0]
            if mod_name in self._blocked:
                return {"ok": False, "command": cmd,
                        "output": f"'{mod_name}' is disabled here: {self._blocked[mod_name]}",
                        "ms": ms}
            return {"ok": False, "command": cmd,
                    "output": f"unknown command: {cmd}", "ms": ms}

        module, handler = entry
        try:
            out = handler(arg)
            return {
                "ok": True, "module": module.name, "command": cmd,
                "output": str(out) if out is not None else "",
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }
        except Exception as e:
            return {
                "ok": False, "module": module.name, "command": cmd,
                "output": f"error: {e}",
                "ms": round((time.perf_counter() - start) * 1000, 2),
            }

```

### `backend/schemas.py`

```python
"""schemas.py — Pydantic request/response models."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel, ConfigDict


class UserCreate(BaseModel):
    username: str
    password: str
    email: str | None = None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str | None
    is_admin: bool


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class CommandIn(BaseModel):
    command: str


class ScanIn(BaseModel):
    host: str
    start: int = 1
    end: int = 1024
    timeout_ms: int = 300


class CommandOut(BaseModel):
    ok: bool
    module: str | None = None
    command: str | None = None
    output: str
    ms: float


class HistoryItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    command: str
    module: str | None
    ok: bool
    duration_ms: float
    created_at: dt.datetime

```


---
## HISTORY (append each session)

- 2026-06-13 · main · Kit created (baseline 5.7). Awaiting first session.
