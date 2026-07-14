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

import sys
import os

# Add root directory to sys.path so we can run this file directly
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import datetime as dt
import time
from collections import defaultdict
from contextlib import asynccontextmanager

import native
from fastapi import (
    Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend import auth, schemas
from backend import key_vault
from backend.providers_extra import merge_into_cli_specs
from backend.ai_stream import stream_chat
from backend.database import SessionLocal, get_db, init_models
from backend.engine import Engine
from backend.runtime import resolve_termaid_root
from backend.models import CommandHistory, RefreshSession, User
from backend.settings import settings

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
    loaded = key_vault.hydrate_env()
    if loaded:
        print(
            f"[startup] hydrated {loaded} provider key(s) from the OS keychain")
    added = merge_into_cli_specs()
    if added:
        print(
            f"[startup] added {added} extra AI provider(s): xai, together, fireworks, deepinfra")
    report = engine.load_all()
    # Wire the Rust scanner in as a native command — but only in local mode,
    # since exposing a port scanner to remote users invites abuse.
    if engine.mode == "local" and native.is_available():
        engine.register_native(
            "scan.ports",
            _scan_command,
            module="scan",
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
async def register(
        body: schemas.UserCreate,
        db: AsyncSession = Depends(get_db)):
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
async def login(form: OAuth2PasswordRequestForm = Depends(),
                db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.username == form.username))).scalar_one_or_none()
    if not user or not auth.verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")
    user.last_login = dt.datetime.now(dt.timezone.utc)
    access = auth.create_access_token(user.id)
    refresh, token_id, expires = auth.create_refresh_token(user.id)
    db.add(
        RefreshSession(
            user_id=user.id,
            token_id=token_id,
            expires_at=expires))
    await db.commit()
    return schemas.TokenPair(access_token=access, refresh_token=refresh)


@app.post("/api/auth/refresh", response_model=schemas.TokenPair)
async def refresh_token(
        body: schemas.RefreshIn,
        db: AsyncSession = Depends(get_db)):
    payload = auth.decode_token(body.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    sess = (await db.execute(
        select(RefreshSession).where(RefreshSession.token_id == payload.get("jti"))
    )).scalar_one_or_none()
    if not sess or sess.revoked:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Refresh token revoked")
    return schemas.TokenPair(
        access_token=auth.create_access_token(int(payload["sub"])),
        refresh_token=body.refresh_token,
    )


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #
async def _record(db: AsyncSession, user_id: int, result: dict) -> None:
    db.add(
        CommandHistory(
            user_id=user_id,
            command=result.get("command") or "",
            module=result.get("module"),
            output=(
                result.get("output") or "")[
                :8000],
            ok=result.get(
                "ok",
                False),
            duration_ms=result.get(
                "ms",
                0.0),
        ))
    await db.commit()


@app.post("/api/exec", response_model=schemas.CommandOut)
async def exec_command(
    body: schemas.CommandIn,
    user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not _rate_ok(user.id):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Rate limit exceeded")
    result = engine.execute(body.command)
    parts = body.command.strip().lstrip("/").split(maxsplit=1)
    result.setdefault("command", parts[0] if parts else "")
    await _record(db, user.id, result)
    return result


@app.get("/api/commands")
async def list_commands(_user: User = Depends(auth.get_current_user)):
    return {"count": len(engine.commands()), "commands": engine.commands()}


@app.get("/api/modules")
async def list_modules(_user: User = Depends(auth.get_current_user)):
    return engine.modules()


@app.get("/api/blocked")
async def list_blocked(_user: User = Depends(auth.get_current_user)):
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
    _user: User = Depends(auth.get_current_user),
):
    """Structured Rust port scan. Local mode only (network action)."""
    if engine.mode != "local":
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "scanning is disabled in server mode")
    if not native.is_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
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
                result["command"] = payload_text.lstrip(
                    "/").split(maxsplit=1)[0] if payload_text else ""
                await ws.send_json({"type": "result", **result})
                async with SessionLocal() as db:
                    await _record(db, user_id, result)
    except WebSocketDisconnect:
        return


# Serve the built frontend (Vite build output) when present.
_dist = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    print("Starting TermAId backend server from main.py...")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
