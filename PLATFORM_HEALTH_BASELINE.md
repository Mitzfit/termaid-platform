# Platform Health — BASELINE  (v2.3.0, 2026-06-13, set by the ops desk)

The honest starting line. Every window inherits the relevant slice of this as its
own baseline; session reports are scored against it so we can see real movement.

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | Engine loads 120 modules cleanly; 20 tests green. But Rust + frontend never compiled here, and the 120 CLI modules are unaudited by us. |
| Security | 6 | JWT access/refresh, bcrypt, rate limit, local/server policy, keychain secrets, scan gated to local. Gaps: in-memory rate limit (per-process), no refresh-token rotation/revocation on use, no HTTPS/TLS config, dev CORS permissive. |
| Performance | 7 | Modules load once; Rust hot paths for scan/walk; async FastAPI. No load testing or profiling yet. |
| Architecture / maintainability | 7 | Clean layer separation; the command-registry reuse is elegant; conventions now defined. Minor: engine is a module global, the .env loader is a patch. |
| Test coverage | 3 | Light. Covers policy, stream parsing, native wrappers. No coverage for auth flows (CI-only), DB models, frontend (zero), most Rust, or the 120 modules. |
| Documentation | 5 | Strong at platform level (ARCHITECTURE/SETUP/INDEX, conventions set). Weak at code level — CLI modules largely uncommented; per-function docs inconsistent. |
| Cross-window cohesion | 6 | Contracts exist (types.ts mirrors schemas.py) but aren't enforced; the orchestration process is new and untested. Provisional. |
| **Overall** | **5.7** | A solid, well-architected skeleton with real gaps in tests and code-level docs — exactly what the per-window passes are designed to fix. |

## Top 3 risks (platform-wide)
1. **Low test coverage** — regressions outside the few covered areas won't be caught.
2. **120 CLI modules unaudited/undocumented** — unknown risk and quality surface.
3. **Server-deployment security gaps** — rate-limit persistence, token revocation, TLS.

## Highest-value next action
Start the per-window passes with **Database & Data Structures** — it's the
foundation every other window reads, so documenting, testing, and hardening it
first lifts the whole platform's floor.

## How we'll know it's working
Watch the Overall trend across sessions. Target near-term: Documentation 5→8 and
Test coverage 3→6 within the first pass through the windows, with no category
regressing.
