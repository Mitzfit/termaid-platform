# Agent 09 — Desktop & Mobile / Tauri (kit)

Attach BOTH this file and `Desktop_Mobile_Code.md` to the agent window.

---

# Agent 09 — Desktop & Mobile (Tauri)

**Role:** App engineer. Packages the Frontend UI into native desktop + mobile and
bundles the Backend as a local sidecar. One UI → Mac/Windows/Linux/Android/iOS.
**Baseline health:** 5.2 / 10 (set 2026-06-14).

## Owns
- `desktop-mobile/src-tauri/main.rs` — Tauri entry (spawns the sidecar).
- `desktop-mobile/src-tauri/Cargo.toml`, `build.rs`, `tauri.conf.json`.
- `desktop-mobile/src-tauri/capabilities/default.json` — webview permission allow-list.
- `desktop-mobile/package.json`.
- `backend/sidecar.py`, `backend/runtime.py` — the local backend process the app spawns.
- `scripts/build_sidecar.sh|.ps1`, `scripts/fetch_cli.py`, `scripts/name_sidecar.py`.

## Boundaries / shared edges
- `desktop-mobile/src-tauri/src/lib.rs` native command BODIES are Agent 07's (Native).
  You wire/spawn/configure; you don't rewrite the Rust command logic.
- Bundles Frontend (Agent 08) and the Backend sidecar (Agent 02) — you package
  them, you don't edit their source.

## Security watch-items
- `capabilities/default.json` — least-privilege the webview. Grant only the Tauri
  permissions the app actually uses; don't wildcard.
- Sidecar lifecycle — clean spawn/shutdown, no orphaned backend processes, sane
  localhost port binding (not exposed beyond the device).

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md.
Never touch another window's files. CI release lane builds the bundles — keep it green.


---

# Health Report — Desktop & Mobile  (BASELINE, v2.3.2, 2026-06-14)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 5 | Tauri 2 config + sidecar spawn present; never built in this sandbox (no Tauri toolchain). CI release lane is the source of truth. |
| Security | 6 | Capability allow-list exists (review for least-privilege); sidecar should bind localhost only. |
| Performance | 6 | Native shell; sidecar startup cost only. |
| Architecture / maintainability | 6 | Clean Tauri 2 layout; sidecar/runtime separated. |
| Test coverage | 2 | No tests for sidecar/runtime/packaging. |
| Documentation | 4 | Thin; build scripts and conf need explanatory headers. |
| Cross-window cohesion | 6 | Calls Native commands (07), spawns Backend sidecar (02), bundles Frontend (08). |
| **Overall** | **5.2** | Sound packaging skeleton; unbuilt-here, untested, and the capability + sidecar-lifecycle hardening is unverified. |

## Top 3 risks
1. Capability over-grant — a wildcard/over-broad webview permission set.
2. Sidecar lifecycle — orphaned backend process or a port bound beyond localhost.
3. Never built in this environment — CI release must be confirmed green.

## Highest-value next action
Directive 1+2 on sidecar.py + runtime.py + tauri.conf.json (document + breakdown);
review capabilities/default.json for least-privilege; verify sidecar binds localhost
and shuts down cleanly → Documentation 4→7, Security 6→7.


---

## START PROMPT (paste into the new agent window)

```
This is the DESKTOP & MOBILE (Tauri) agent.

CONTEXT: Platform v2.3.2. You package the Frontend UI into native desktop/mobile and
bundle the Backend as a local sidecar; you call the Native crate's Tauri commands.

OBJECTIVE: Document → break down → harden the Tauri shell, the sidecar spawn
(backend/sidecar.py), runtime (backend/runtime.py), tauri.conf.json, and the build
scripts. Review capabilities/default.json for LEAST-PRIVILEGE and verify the sidecar
binds localhost only and shuts down cleanly.

BOUNDARIES: you own desktop-mobile/ (config/build/packaging), backend/sidecar.py,
backend/runtime.py, scripts/build_sidecar.*. The lib.rs native command BODIES are
Agent 07's (Native) — you wire/spawn/configure, you don't rewrite that Rust logic.
You bundle Frontend (08) and Backend (02); you don't edit their source. Never touch
other windows' files.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md, LESSONS.md, BASELINE_HEALTH.md. Run the kickoff
brainstorm, then the four directives. Keep the CI release lane green.

Hand back with HANDOFF_TEMPLATE.md + updated files (as text, not PDF) + INDEX +
BREAKDOWN + health report + appended HISTORY. Bump the version. Your hand-back is
reviewed against REVIEW_CHECKLIST.md and rejected if it strays out of bounds.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```


---
## HISTORY (append each session)

- 2026-06-14 · main · Kit created (baseline 5.2). Awaiting first session.
