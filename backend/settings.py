"""
settings.py — Centralised config, read from environment / .env file.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_dotenv_into_environ(path: str = ".env") -> None:
    """Push KEY=value lines from .env into os.environ (without overwriting
    anything already exported in the shell).

    pydantic-settings only maps .env values onto *defined* Settings fields, so
    provider keys like GEMINI_API_KEY would otherwise never reach the code that
    reads os.environ. This makes a key placed in .env "just work" everywhere —
    the streaming path, the CLI's provider code, and the sidecar.
    """
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# Run before Settings is constructed so everything sees the same environment.
_load_dotenv_into_environ()


def _split(v: str) -> set[str]:
    return {x.strip() for x in v.split(",") if x.strip()}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- where your existing TermAId CLI project lives ---
    termaid_root: str = str(
        Path(__file__).resolve().parents[2] /
        "termaid-cli")

    # --- deployment mode: "local" (trusted device) | "server" (remote/multi-user) ---
    deployment_mode: str = "server"

    # comma-separated overrides, e.g. MODULE_EXTRA_ALLOW="git,docker"
    module_extra_allow: str = ""
    module_extra_deny: str = ""

    # --- AI provider (enables streaming chat + AI modules) ---
    # one of: gemini-flash, gemini, groq, cerebras, openai, anthropic,
    # openrouter, ollama
    ai_provider: str | None = None

    # --- database ---
    database_url: str = "sqlite+aiosqlite:///./termaid_web.db"
    sql_echo: bool = False

    # --- auth ---
    jwt_secret: str = "CHANGE_ME_use_openssl_rand_hex_32"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    # --- seeded root/admin account (app-level is_admin role, NOT the OS-level
    # /admin CLI module) --- left as the sentinel below, bootstrap is skipped
    # entirely and no default admin account is ever created. Set both to
    # enable it; the operator's .env is always the source of truth for this
    # one account (re-applied on every boot), and self-registering this exact
    # username is rejected — it can never be claimed by anyone else.
    admin_username: str = "CHANGE_ME_admin_username"
    admin_password: str = "CHANGE_ME_use_a_real_password"

    # --- rate limiting (per client) ---
    exec_rate_per_minute: int = 60

    # --- server ---
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:8000",
        "tauri://localhost",
        "https://tauri.localhost",
    ]

    @property
    def extra_allow_set(self) -> set[str]:
        return _split(self.module_extra_allow)

    @property
    def extra_deny_set(self) -> set[str]:
        return _split(self.module_extra_deny)


settings = Settings()
