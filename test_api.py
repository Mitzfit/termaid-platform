"""
API integration tests using FastAPI's TestClient.

The engine is replaced with a fake so these run in CI WITHOUT needing the
TermAId CLI package or its 120 modules present. They exercise the real auth,
DB, rate-limit, and exec plumbing.

Requires the backend deps (fastapi, httpx, sqlalchemy, …) — installed by CI.
"""
import importlib
import os

import pytest


class FakeEngine:
    """Stand-in matching the Engine interface used by main.py."""
    mode = "server"

    def load_all(self):
        return {"mode": self.mode, "discovered": 1, "loaded": 1,
                "blocked": 0, "failed": 0, "commands": 1, "failures": []}

    def execute(self, line: str):
        line = (line or "").strip().lstrip("/")
        cmd = line.split(maxsplit=1)[0] if line else ""
        if cmd == "echo.say":
            arg = line.split(maxsplit=1)[1] if " " in line else ""
            return {"ok": True, "module": "echo", "command": cmd, "output": arg, "ms": 0.1}
        return {"ok": False, "command": cmd, "output": f"unknown command: {cmd}", "ms": 0.1}

    def commands(self):
        return ["echo.say"]

    def modules(self):
        return {"echo": {"version": "1.0", "description": "test", "commands": ["say"], "category": "safe"}}

    def blocked(self):
        return {}

    def has_ai(self):
        return False


@pytest.fixture()
def client(tmp_path, monkeypatch):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tmp_path/'t.db'}"
    os.environ["JWT_SECRET"] = "test_secret"
    os.environ["DEPLOYMENT_MODE"] = "server"

    # import fresh so settings pick up the env above
    import backend.settings as s
    importlib.reload(s)
    import backend.database as d
    importlib.reload(d)
    import backend.main as m
    importlib.reload(m)

    monkeypatch.setattr(m, "engine", FakeEngine())

    from fastapi.testclient import TestClient
    with TestClient(m.app) as c:
        yield c


def _auth(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "secret1"})
    r = client.post("/api/auth/login", data={"username": "alice", "password": "secret1"})
    return r.json()["access_token"]


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_login_and_exec(client):
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}

    ok = client.post("/api/exec", json={"command": "echo.say hi there"}, headers=h)
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True and body["output"] == "hi there"

    bad = client.post("/api/exec", json={"command": "nope.cmd"}, headers=h)
    assert bad.json()["ok"] is False


def test_exec_requires_auth(client):
    r = client.post("/api/exec", json={"command": "echo.say hi"})
    assert r.status_code == 401


def test_history_records_commands(client):
    token = _auth(client)
    h = {"Authorization": f"Bearer {token}"}
    client.post("/api/exec", json={"command": "echo.say one"}, headers=h)
    hist = client.get("/api/history", headers=h).json()
    assert any(item["command"] == "echo.say" for item in hist)
