"""Pytest config — set env BEFORE the app imports settings."""
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_termaid.db")
os.environ.setdefault("JWT_SECRET", "test_secret_not_for_production")
os.environ.setdefault("DEPLOYMENT_MODE", "server")
