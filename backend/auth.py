"""
auth.py — Password hashing (bcrypt) + JWT access/refresh tokens.

Your `auth` CLI module uses PBKDF2-SHA256, which is fine. For the web tier we
use bcrypt via passlib (battle-tested, easy). If you'd rather keep one hashing
scheme everywhere, swap CryptContext for your existing pbkdf2 helper — the rest
of this file is unaffected.
"""

from __future__ import annotations

import datetime as dt
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .models import User
from .settings import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "type": "access",
        "exp": _now() + dt.timedelta(minutes=settings.access_token_minutes),
        "iat": _now(),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, str, dt.datetime]:
    token_id = uuid.uuid4().hex
    expires = _now() + dt.timedelta(days=settings.refresh_token_days)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": token_id,
        "exp": expires}
    token = jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm)
    return token, token_id, expires


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[
                settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    user_id = int(payload["sub"])
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "User not found or inactive")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Gate for the app-level admin role (User.is_admin) — the seeded root
    account for user management + system health. Not to be confused with the
    unrelated `admin` CLI module, which manages OS-level Administrator/sudo
    group membership on the host machine."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user
