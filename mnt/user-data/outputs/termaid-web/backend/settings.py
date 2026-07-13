"""
settings.py — Centralised config, read from environment / .env file.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- where your existing TermAId CLI project lives ---
    termaid_root: str = str(Path(__file__).resolve().parents[2] / "termaid-complete-windows")

    # --- optional: enable AI-backed commands by naming a provider ---
    # one of: gemini-flash, gemini, groq, cerebras, openai, anthropic, openrouter, ollama
    # the provider's API key must be present in the environment (same names as the CLI).
    ai_provider: str | None = None

    # --- database ---
    database_url: str = "sqlite+aiosqlite:///./termaid_web.db"
    sql_echo: bool = False

    # --- auth ---
    jwt_secret: str = "CHANGE_ME_use_openssl_rand_hex_32"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    # --- server ---
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:8000"]


settings = Settings()
