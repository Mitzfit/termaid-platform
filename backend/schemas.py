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


class AdminUserOut(BaseModel):
    """Fuller user view for the admin user-management endpoints — UserOut
    doesn't carry is_active/created_at/last_login."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str | None
    is_admin: bool
    is_active: bool
    created_at: dt.datetime
    last_login: dt.datetime | None


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
