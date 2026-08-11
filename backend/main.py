from __future__ import annotations
from backend.pty_engine import pty_router

"""
main.py — FastAPI application (policy-aware + streaming).

REST:
  POST /api/auth/register | login | refresh
  POST /api/exec            run one module command
  GET  /api/commands        list permitted commands
  GET  /api/modules         module metadata (+ category)
  GET  /api/blocked         what's disabled here and why
  GET  /api/history         caller's recent commands
  GET  /api/health          liveness + engine status
  WebSocket /ws/terminal?token=<access>
      client → {"type":"exec","payload":"calc.hex 255"}
      client → {"type":"chat","payload":"explain TCP handshake"}
      server → {"type":"result", ok, module, output, ms}
      server → {"type":"chat_delta","text":"..."}  (repeated)
      server → {"type":"chat_error","text":"..."}  (on stream failure)
      server → {"type":"chat_done"}

Run: uvicorn backend.main:app --reload --port 8000
"""

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
import native
from . import key_vault as secrets
from .providers_extra import merge_into_cli_specs
from .ai_stream import stream_chat
from .database import SessionLocal, get_db, init_models
from .engine import Engine
from .runtime import resolve_termaid_root, is_frozen
from .models import CommandHistory, User
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
    start = int(parts[1]) if len(parts) > 1 else 1024
    end = int(parts[2]) if len(parts) > 2 else 300
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


app = FastAPI(title="TermAId Platform", version="2.3.4", lifespan=lifespan)

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
    user = User(username=body.username, email=body.email, password_hash=auth.hash_password(body.password))
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
    # Persist the refresh session through auth (owns the RefreshSession lifecycle
    # + revoke-on-use bookkeeping) rather than constructing the ORM row inline.
    await auth.persist_refresh_session(db, user.id, token_id, expires)
    await db.commit()
    return schemas.TokenPair(access_token=access, refresh_token=refresh)


@app.post("/api/auth/refresh", response_model=schemas.TokenPair)
async def refresh_token(body: schemas.RefreshIn, db: AsyncSession = Depends(get_db)):
    # Rotation-on-use lives in auth: it validates the presented token, revokes it,
    # and mints a fresh access+refresh pair. It raises 401 on a bad/revoked/expired
    # token, so no manual decode/lookup is needed here — and reusing an old refresh
    # token now fails, closing the replay window.
    new_access, new_refresh = await auth.rotate_refresh_token(db, body.refresh_token)
    return schemas.TokenPair(access_token=new_access, refresh_token=new_refresh)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
async def _record(db: AsyncSession, user_id: int, result: dict) -> None:
    db.add(CommandHistory(
        user_id=user_id,
        command=result.get("command") or "",
        module=result.get("module"),
        output=(result.get("output") or "")[:8000],
        ok=result.get("ok", False),
        duration_ms=result.get("ms", 0.0),
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



@app.get("/api/fs")
async def list_fs(path: str = "."):
    import os
    try:
        base = os.path.abspath(path)
        items = []
        if os.path.exists(base) and os.path.isdir(base):
            parent = os.path.dirname(base)
            if parent != base:
                items.append({"name": "..", "is_dir": True, "path": parent})
            for f in sorted(os.listdir(base)):
                full = os.path.join(base, f)
                items.append({"name": f, "is_dir": os.path.isdir(full), "path": full})
        return {"path": base, "items": items}
    except Exception as e:
        return {"error": str(e)}

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
        raise HTTPException(status.HTTP_403_FORBIDDEN, "scanning is disabled in server mode")
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
                # Structured streaming: ai_stream yields typed events
                # ({"kind": "delta"|"error"|"done"}) instead of bare text, so we
                # branch on kind rather than sniffing the string. Only real delta
                # text is accumulated for history; an error is surfaced as its own
                # WS frame and marks the turn failed.
                full: list[str] = []
                ok = True
                async for ev in stream_chat(settings.ai_provider, payload_text, events=True):
                    ev_kind = ev.get("kind")
                    if ev_kind == "delta":
                        text = ev.get("text", "")
                        full.append(text)
                        await ws.send_json({"type": "chat_delta", "text": text})
                    elif ev_kind == "error":
                        ok = False
                        await ws.send_json({"type": "chat_error", "text": ev.get("text", "")})
                    # "done" is handled once, after the loop, so the client always
                    # gets exactly one terminating chat_done frame.
                await ws.send_json({"type": "chat_done"})
                async with SessionLocal() as db:
                    await _record(db, user_id, {
                        "command": "chat", "module": "ai", "ok": ok,
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

app.include_router(pty_router)
