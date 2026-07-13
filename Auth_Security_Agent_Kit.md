# Agent 03 — Auth & Security (complete kit)

Attach this single file to the Auth & Security agent window (or add to project knowledge). Contains the brief, baseline, start prompt, and all owned source.

---

# Agent 03 — Auth & Security

**Role:** Security engineer. Identity (JWT + passwords) and the deployment policy
that decides which of the 120 modules may run where. The platform's gatekeeper.
**Baseline health:** 5.9 / 10 (set 2026-06-13).

## Owns
- `backend/auth.py` — bcrypt password hashing; JWT access/refresh tokens.
- `backend/policy.py` — safe/ai/system/dangerous module sets; local vs server mode.
- `backend/tests/test_policy.py` — policy tests (maintain + extend).
- Governs (CLI side, do not rewrite logic blindly): security, sec, privesc, perms, sandbox.

## Depends on / feeds
- Reads: Database (User, RefreshSession).
- Feeds: Backend Core (main.py wires auth; engine.py reads policy).

## Security watch-items (verify this slice)
- Refresh-token ROTATION + revoke-on-use (RefreshSession has a `revoked` flag and
  stores the jti, not the token — confirm the flow actually rotates/revokes).
- JWT secret must come from settings/secrets, never a hardcoded default in prod.
- Dangerous modules are blocked in server mode; allow-list correct in local mode.

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md
(incl. Termaid spelling). Never touch another window's files.


---

# Health Report — Auth & Security  (BASELINE, v2.3.1, 2026-06-13)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | JWT access/refresh + bcrypt present; policy filtering works (test_policy green in CI). |
| Security | 6 | Good foundations. Gaps: confirm refresh rotation/revoke-on-use; JWT secret must be config-supplied; verify server-mode blocks dangerous modules. |
| Performance | 7 | bcrypt cost + JWT verify are fine; no hot-path concern. |
| Architecture / maintainability | 7 | Clean separation; policy sets are explicit and readable. |
| Test coverage | 4 | policy covered; auth.py token flows (issue/verify/refresh/revoke) untested. |
| Documentation | 4 | Headers present; per-function why-docs thin. |
| Cross-window cohesion | 6 | Feeds main.py + engine.py; contracts informal. |
| **Overall** | **5.9** | Sound security skeleton; auth flows need tests and the rotation/revoke path needs verifying. |

## Top 3 risks
1. Refresh-token rotation/revocation not verified — a stolen refresh token could be reusable.
2. JWT secret / config hardening — a default secret in any non-dev path is critical.
3. auth.py untested — token issue/verify/expiry/refresh paths unverified.

## Highest-value next action
Directive 1 (document auth.py + policy.py to CODE_STYLE, Misfit) + add auth token-flow
tests (issue, verify, expiry, refresh-rotation, revoke) → Documentation 4→8, Tests 4→7.
Verify server mode blocks every dangerous module.


---

## START PROMPT (paste into the new agent window)

```
This is the AUTH & SECURITY agent.

Your role: security engineer. You own backend/auth.py (bcrypt + JWT access/refresh),
backend/policy.py (safe/ai/system/dangerous sets; local vs server mode), and
backend/tests/test_policy.py. You govern the CLI security modules (security, sec,
privesc, perms, sandbox) but do not rewrite their logic blindly. Work ONLY on your
files; never touch another window's.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md (Termaid spelling), LESSONS.md, BASELINE_HEALTH.md.

Run the kickoff brainstorm, then the four directives: 1) Document (what/does/why,
Misfit), 2) Break down (BREAKDOWN.md), 3) Harden, 4) Health report.

Security watch-items to verify this session:
- Refresh-token ROTATION + revoke-on-use actually happens (RefreshSession.revoked + jti).
- JWT secret comes from settings/secrets, never a hardcoded prod default.
- Server mode blocks ALL dangerous modules; local-mode allow-list is correct.

Hand back with HANDOFF_TEMPLATE.md + updated files (as .py text, not PDF) + INDEX +
BREAKDOWN + health report + appended HISTORY. Bump the version.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```

---

## OWNED SOURCE CODE

### `backend/auth.py`

```python
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
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(user_id: int) -> tuple[str, str, dt.datetime]:
    token_id = uuid.uuid4().hex
    expires = _now() + dt.timedelta(days=settings.refresh_token_days)
    payload = {"sub": str(user_id), "type": "refresh", "jti": token_id, "exp": expires}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, token_id, expires


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")


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
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user

```

### `backend/policy.py`

```python
"""
policy.py — Module safety policy.

The core of "what can we do about it running as a local tool?".

Your CLI assumes a trusted operator on their own machine. A network service
does not get that assumption. We solve it with two deployment modes:

  • DEPLOYMENT_MODE = "local"   → the app runs on the user's own device
                                  (e.g. inside the Tauri desktop/mobile bundle,
                                  talking to a localhost sidecar). Everything is
                                  allowed except an explicit, tiny deny-list of
                                  irreversibly destructive operations.

  • DEPLOYMENT_MODE = "server"  → the app is exposed to remote / multiple users.
                                  ONLY the curated SAFE allow-list loads. System,
                                  device, firmware, and network-attack modules are
                                  never even imported.

Categories below are derived from your 120 modules. Adjust freely; the policy
engine just consumes these sets.
"""

from __future__ import annotations

# Pure compute or own-data-only. Safe to expose to anyone, anywhere.
SAFE_MODULES: frozenset[str] = frozenset({
    "calc", "text", "regex", "diff", "qr", "password",
    "notes", "translate", "weather", "markets", "paper", "research",
    "learn", "lessons", "persona", "style", "banner", "header", "welcome",
    "errors", "clip", "find", "catalog", "manifest", "rules", "memory",
    "quick", "aliases", "calc", "regex",
})

# Need an AI provider but otherwise side-effect-free. Safe with a key configured.
AI_MODULES: frozenset[str] = frozenset({
    "assistant", "brain", "cognition", "cortex", "smart", "aitools",
    "aiconfig", "imagegen", "learner", "improve", "qa", "agent", "chain",
})

# Touch the host: shell out, scan, modify files, manage processes/VMs/repos.
# Allowed in LOCAL mode, blocked in SERVER mode.
SYSTEM_MODULES: frozenset[str] = frozenset({
    "git", "repo", "docker", "vm", "wsl", "pyenv", "env", "schedule",
    "backup", "sync", "cleanup", "filetools", "find", "diskspace",
    "sysmonitor", "hardware", "devdetect", "doctor", "bench", "perftune",
    "log", "debug", "session", "workspace", "proj", "serve", "sandbox",
    "netscan", "nettools", "netdeep", "fsscan", "dbkeys", "sql", "apikeys",
    "keyring", "dashboard", "bots", "notify", "router", "config", "autoconfig",
    "selftest", "verify", "improve", "extras", "tools", "tmx", "termux",
})

# Irreversible / privilege-escalating / firmware-level. NEVER auto-exposed.
# Blocked in BOTH modes unless an operator explicitly opts in per-module.
DANGEROUS_MODULES: frozenset[str] = frozenset({
    "privesc", "sudo", "perms", "admin", "fwown", "firmware", "uefi",
    "bootmgr", "dualboot", "multiboot", "recovery", "rootguide", "device",
    "devicescan", "adb", "fastboot", "usbdeep", "disktool", "syscmd",
    "sysint", "selfmod", "security", "sec", "hardlines", "firstrun",
    "boot", "crypto",  # crypto can sign/encrypt destructively; opt-in only
})


def allowed_modules(
    discovered: list[str],
    mode: str,
    extra_allow: set[str] | None = None,
    extra_deny: set[str] | None = None,
) -> tuple[set[str], dict[str, str]]:
    """Decide which modules may load.

    Returns (allowed_set, blocked_with_reason).
    """
    extra_allow = extra_allow or set()
    extra_deny = extra_deny or set()

    allowed: set[str] = set()
    blocked: dict[str, str] = {}

    for name in discovered:
        if name in extra_deny:
            blocked[name] = "operator deny-list"
            continue
        if name in extra_allow:
            allowed.add(name)
            continue

        if mode == "server":
            # Default-deny. Dangerous is checked FIRST so a module that is ever
            # double-classified can never leak through the safe path.
            if name in DANGEROUS_MODULES:
                blocked[name] = "dangerous (blocked in server mode)"
            elif name in SAFE_MODULES or name in AI_MODULES:
                allowed.add(name)
            elif name in SYSTEM_MODULES:
                blocked[name] = "system access (blocked in server mode)"
            else:
                blocked[name] = "not in server allow-list"
        else:  # local mode → default-allow, except the irreversible deny set
            if name in DANGEROUS_MODULES:
                blocked[name] = "dangerous (opt-in required even locally)"
            else:
                allowed.add(name)

    return allowed, blocked

```

### `backend/tests/test_policy.py`

```python
"""Policy unit tests — no termaid package required."""
from backend.policy import allowed_modules, SAFE_MODULES, DANGEROUS_MODULES

DISCOVERED = ["calc", "text", "privesc", "git", "assistant", "fwown", "weather"]


def test_server_mode_allows_only_safe_and_ai():
    allowed, blocked = allowed_modules(DISCOVERED, "server")
    assert "calc" in allowed and "weather" in allowed       # safe
    assert "assistant" in allowed                           # ai
    assert "privesc" in blocked and "fwown" in blocked      # dangerous
    assert "git" in blocked                                 # system → blocked on server


def test_local_mode_allows_system_but_not_dangerous():
    allowed, blocked = allowed_modules(DISCOVERED, "local")
    assert "git" in allowed                                 # system ok locally
    assert "calc" in allowed
    assert "privesc" in blocked and "fwown" in blocked      # still blocked


def test_dangerous_never_leaks_in_either_mode():
    for mode in ("server", "local"):
        allowed, _ = allowed_modules(list(DANGEROUS_MODULES), mode)
        assert not (allowed & DANGEROUS_MODULES)


def test_operator_overrides():
    allowed, blocked = allowed_modules(
        ["git", "weather"], "server",
        extra_allow={"git"}, extra_deny={"weather"},
    )
    assert "git" in allowed         # force-allowed
    assert "weather" in blocked     # force-denied

```


---
## HISTORY (append each session)

- 2026-06-13 · main · Kit created (baseline 5.9). Awaiting first session.
