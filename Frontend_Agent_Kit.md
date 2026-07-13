# Agent 08 — Frontend / UI (kit)

Attach BOTH this file and `Frontend_Code.md` to the agent window. This file = brief/baseline/start; the code file = the owned source.

---

# Agent 08 — Frontend / UI

**Role:** Frontend engineer. The TypeScript terminal UI + the typed API/WS/native
clients — the face of the platform across browser, desktop, and mobile.
**Baseline health:** 5.4 / 10 (set 2026-06-14).

## Owns (frontend/)
- `src/api.ts` — typed REST client (auth + token storage + auto-refresh).
- `src/ws.ts` — WebSocket client (streaming chat).
- `src/terminal.ts` — terminal UI.
- `src/main.ts` — app entry/wiring.
- `src/native.ts` — Tauri-invoke ↔ REST bridge.
- `src/types.ts` — TS types mirroring the API (schemas.py).
- `index.html`, `src/style.css`, `vite.config.ts`, `tsconfig.json`, `package.json`.

## Depends on / feeds
- Reads: Backend Core — the API/WS contract. Mirror it; don't redefine it.
- Reads: Native — the Tauri command names/shapes via native.ts.

## Inherited cross-window TODOs (pick up this slice)
1. **Store the rotated refresh token** — Auth now rotates on /api/auth/refresh; the
   refresh flow must call `store.set(newPair)` with the NEW token, never reuse the old.
2. **Structured stream events** — once Backend forwards `{kind: delta|error|done}`
   over WS, handle each kind (render delta, surface error, finalize on done) instead
   of treating everything as text.
3. **types.ts side** of the models↔schemas↔types contract test (with Backend + QA).

## Security note
Tokens are in `localStorage` (XSS-exposed). Hardening (e.g. httpOnly refresh cookie)
crosses into Backend — flag it, don't unilaterally change the contract.

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md.
Never touch another window's files.


---

# Health Report — Frontend / UI  (BASELINE, v2.3.2, 2026-06-14)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | Type-checks strict; UI works. Refresh flow must re-store rotated tokens (inherited). |
| Security | 5 | Tokens in localStorage (XSS surface). Must store rotated refresh token; consider hardening. |
| Performance | 7 | Vite build; lightweight clients. |
| Architecture / maintainability | 7 | Clean separation: api / ws / terminal / native / types. |
| Test coverage | 2 | No frontend tests at all. |
| Documentation | 4 | Some file headers (api.ts); per-function docs thin. |
| Cross-window cohesion | 5 | types.ts mirrors schemas.py UNENFORCED (shared top risk); WS event shape about to change. |
| **Overall** | **5.4** | Clean, typed UI; zero tests, localStorage tokens, and two inherited integrations to land. |

## Top 3 risks
1. Zero frontend tests — UI/client regressions unverified.
2. Token storage in localStorage — XSS-exposed; rotated-refresh handling not yet wired.
3. types.ts ↔ schemas.py contract unenforced — silent divergence.

## Highest-value next action
Directive 1 (document the clients) + wire the rotated-refresh handling and the
structured stream-event handling; add a few vitest tests for api.ts token logic →
Documentation 4→7, Tests 2→5.


---

## START PROMPT (paste into the new agent window)

```
This is the FRONTEND / UI agent.

CONTEXT: Platform v2.3.2. Two backend changes affect you: (1) Auth now ROTATES the
refresh token on /api/auth/refresh — the client must store the NEW token; (2) AI
streaming offers a structured events mode ({kind: delta|error|done}) that Backend
will forward over WS — handle each kind instead of treating all output as text.

OBJECTIVE: Document → break down → harden the TypeScript UI + typed clients (api,
ws, terminal, native, types). Land the two inherited integrations above. Own the
types.ts side of the models↔schemas↔types contract.

BOUNDARIES: you own frontend/ only. The API/WS shapes are the Backend window's
contract — mirror them, do not redefine them. Token-storage hardening that changes
the contract (e.g. httpOnly cookie) must be FLAGGED for Backend, not done unilaterally.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md, LESSONS.md, BASELINE_HEALTH.md. Run the kickoff
brainstorm, then the four directives. Document with JSDoc, Misfit-attributed.

Hand back with HANDOFF_TEMPLATE.md + updated files (as .ts text, not PDF) + INDEX +
BREAKDOWN + health report + appended HISTORY. Bump the version. Your hand-back is
reviewed against REVIEW_CHECKLIST.md and rejected if it strays out of bounds.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```


---
## HISTORY (append each session)

- 2026-06-14 · main · Kit created (baseline 5.4). Awaiting first session.
