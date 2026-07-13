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
