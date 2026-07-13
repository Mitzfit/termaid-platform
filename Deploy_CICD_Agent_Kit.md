# Agent 10 — Docker / Deploy / CI-CD (kit)

Attach BOTH this file and `Deploy_CICD_Code.md` to the agent window. Hand back via HANDBACK_TEXT_PROTOCOL.md (text only).

---

# Agent 10 — Docker / Deploy / CI-CD

**Role:** Release engineer. The lane that builds, tests, and ships every other
slice — Python, TypeScript, Rust, and the Tauri bundles. The platform's gate to prod.
**Baseline health:** 5.4 / 10 (set 2026-06-14).

## Owns
- `Dockerfile` — the server-mode backend image.
- `docker-compose.yml` — local stack (backend + Postgres).
- `.github/workflows/ci.yml` — lint/test/build across py/ts/rust.
- `.github/workflows/release.yml` — Tauri desktop/mobile bundles.
- `.github/workflows/release-bundled.yml` — frozen-sidecar bundle release.
- `.dockerignore` (if present).

## Depends on / feeds
- Builds the slices owned by: Backend (02), Native/Rust (07), Frontend (08),
  Desktop/Mobile (09). You orchestrate their builds; you don't edit their source.
- Reads: backend/requirements*.txt (owned by Backend/Secrets) — you consume, not edit.

## Findings to fix this slice (already spotted by the Master Agent)
1. **Dockerfile runs as ROOT**, single-stage. Add a non-root USER; consider
   multi-stage; pin the base image (ideally by digest).
2. **CI test deps incomplete** — ci.yml installs only pytest/pytest-asyncio, but the
   new suites need `aiosqlite`, `passlib[bcrypt]`, `python-jose`, `httpx` (auth-flow,
   model, stream tests). Install them or those suites silently don't run.
3. **`cargo clippy -- -D warnings || true`** — the `|| true` defeats the gate;
   clippy failures pass CI. Remove it so clippy actually blocks.

## Inherited cross-window TODOs (this is their natural home)
- The CI **contract test** diffing models.py ↔ schemas.py ↔ types.ts (with Backend + Frontend + QA).
- Confirm the deploy path runs `alembic upgrade head` (not init_models()).

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md.
Never touch another window's source. Hand back via HANDBACK_TEXT_PROTOCOL.md (text only).


---

# Health Report — Docker / Deploy / CI-CD  (BASELINE, v2.3.2, 2026-06-14)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | CI has py/ts/rust lanes + 2 release workflows; Docker builds. Not run in this sandbox. |
| Security | 5 | Dockerfile runs as ROOT, single-stage, unpinned base. CI secret handling otherwise ok. |
| Performance | 5 | Build caching minimal/unconfirmed; image not size-optimized. |
| Architecture / maintainability | 6 | Workflows are readable; Dockerfile is thin. |
| Test coverage (of the pipeline) | 5 | Runs suites, BUT may miss test deps (aiosqlite/passlib/jose/httpx) so new suites don't run; `clippy ... || true` disables the lint gate. |
| Documentation | 4 | Workflow/Dockerfile comments thin. |
| Cross-window cohesion | 6 | Builds 02/07/08/09; release bundles tie it together. |
| **Overall** | **5.4** | A working pipeline that doesn't yet enforce what it should: root container, a disabled lint gate, and test suites that may not actually execute. |

## Top 3 risks
1. Root container + unpinned base — image hardening.
2. New test suites may not run in CI (missing deps); clippy gate disabled by `|| true`.
3. No confirmed `alembic upgrade head` in the deploy path (DB drift risk).

## Highest-value next action
Harden the Dockerfile (non-root USER, multi-stage, pinned base) + fix ci.yml (install
full test deps so auth/model/stream suites run; drop `|| true` on clippy) + add the
models↔schemas↔types contract job → Security 5→7, Test coverage 5→7.


---

## START PROMPT (paste into the new agent window)

```
This is the DOCKER / DEPLOY / CI-CD agent.

CONTEXT: Platform v2.3.2. CI must build and test four slices — Python backend (02),
Rust crate (07), TypeScript frontend (08), and the Tauri bundles (09). Recent
integrations added test suites (auth-flow, model, stream/brain) that need their deps
present in CI to actually run.

OBJECTIVE: Document → break down → harden the Dockerfile, docker-compose, and the CI
+ release workflows. Specifically fix the three findings below, then health report.

KNOWN FINDINGS TO FIX:
1. Dockerfile runs as ROOT, single-stage, unpinned base — add a non-root USER,
   consider multi-stage, pin the base image (by digest if possible).
2. ci.yml installs only pytest/pytest-asyncio — also install aiosqlite, passlib[bcrypt],
   python-jose, httpx so the auth-flow/model/stream suites actually run.
3. `cargo clippy -- -D warnings || true` — remove the `|| true` so clippy gates.

BOUNDARIES: you own Dockerfile, docker-compose.yml, .github/workflows/*, .dockerignore.
You orchestrate other slices' builds; you do NOT edit their source. requirements*.txt
are Backend/Secrets' — consume, don't edit. Never touch other windows' files.

INHERITED (your natural home): add the CI contract test diffing models.py↔schemas.py↔
types.ts (coordinate with Backend/Frontend/QA); confirm the deploy path runs
`alembic upgrade head`.

Read project knowledge first (MASTER_INDEX, ARCHITECTURE, CODE_STYLE, WINDOW_DIRECTIVES,
RULES, LESSONS, BASELINE_HEALTH). Run the brainstorm, then the four directives. Hand
back via HANDBACK_TEXT_PROTOCOL.md — TEXT ONLY, no files, no PDF. Your hand-back is
reviewed against REVIEW_CHECKLIST.md and rejected if it strays out of bounds.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```


---
## HISTORY (append each session)

- 2026-06-14 · main · Kit created (baseline 5.4). Awaiting first session.
