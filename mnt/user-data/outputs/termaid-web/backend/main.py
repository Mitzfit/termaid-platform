"""
main.py — FastAPI application.

Exposes your TermAId command engine over:
  • REST   POST /api/exec           run one command (auth required)
  •         GET  /api/commands       list all 1948 commands
  •         GET  /api/modules        module metadata
  •         GET  /api/history        the caller's recent commands
  •         auth: register / login / refresh
  • WS      /ws/terminal             live REPL-style terminal (auth via ?token=)

Run:
    uvicorn backend.main:app --reload --port 8000
"""

from __future__ import annotations

import datetime as dt

from fastapi import (
    Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth, schemas
from .database import SessionLocal, get_db, init_models
from .engine import Engine
from .models import CommandHistory, RefreshSession, User
from .settings import settings

app = FastAPI(title="TermAId Web", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# One shared engine for the whole process. Modules load once at startup.
engine = Engine(termaid_root=settings.termaid_root, ai_provider=settings.ai_provider)


@app.on_event("startup")
async def _startup() -> None:
    await init_models()
    report = engine.load_all()
    print(f"[startup] {report['loaded']} modules / {report['commands']} commands ready")
    if report["failed"]:
        print(f"[startup] {report['failed']} modules failed to load")


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
@app.post("/api/auth/register", response_model=schemas.UserOut)
async def register(body: schemas.UserCreate, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(User).where(User.username == body.username))).scalar_one_or_none()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username taken")
    user = User(
        username=body.username,
        email=body.email,
        password_hash=auth.hash_password(body.password),
    )
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
    jti = payload.get("jti")
    sess = (await db.execute(
        select(RefreshSession).where(RefreshSession.token_id == jti)
    )).scalar_one_or_none()
    if not sess or sess.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")
    user_id = int(payload["sub"])
    return schemas.TokenPair(
        access_token=auth.create_access_token(user_id),
        refresh_token=body.refresh_token,
    )


# --------------------------------------------------------------------------- #
# Command execution
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


@app.get("/api/history", response_model=list[schemas.HistoryItem])
async def history(
    limit: int = 50,
    user: User = Depends(auth.get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(CommandHistory)
        .where(CommandHistory.user_id == user.id)
        .order_by(CommandHistory.created_at.desc())
        .limit(min(limit, 200))
    )).scalars().all()
    return rows


# --------------------------------------------------------------------------- #
# WebSocket terminal — the REPL feel, in the browser
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
                        "text": f"TermAId Web — {len(engine.commands())} commands ready. "
                                f"Type 'help' or any /mod.cmd."})
    try:
        while True:
            line = await ws.receive_text()
            result = engine.execute(line)
            result["command"] = line.strip().lstrip("/").split(maxsplit=1)[0]
            await ws.send_json({"type": "result", **result})
            # persist history off the hot path
            async with SessionLocal() as db:
                await _record(db, user_id, result)
    except WebSocketDisconnect:
        return


# Serve the static frontend (so one process serves API + UI in dev).
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
