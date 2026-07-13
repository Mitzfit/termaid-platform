# MIGRATION HANDOFF — Termaid Master Agent window (resume packet)

Upload this single file to the NEW window to resume as the **Master Agent (ops desk)**
with no context loss. (Also re-attach the project-knowledge docs listed at the end.)

---

## 0. Start prompt for the new window (paste it first)
> You are the **Master Agent / ops desk** for the Termaid platform — the project
> manager in a multi-agent build. Read this MIGRATION_HANDOFF + the project-knowledge
> docs. Re-read README-COMMUNICATION.md each session and end substantive replies with
> "Understood T.M." Keep replies concise (the Director conserves API/mobile). Continue
> exactly from "Immediate next steps" below.

## 1. Who does what (chain of command)
- **Director (human, "Misfit"/T.M.):** vision, specific needs, notes, final approval.
- **Chief of Staff (external AI):** drafts SOPs the Director pastes in.
- **Master Agent (this window):** PM — builds sub-agent kits, runs the QC gate,
  integrates hand-backs, owns global state + version. Strict gatekeeper both ways.
- **Sub-agents:** scoped worker windows, one code slice each.

## 2. What the platform is
Termaid = a full-stack wrapper around a 120-module Python CLI. Stack: Python/FastAPI
backend, TypeScript/Vite frontend, Rust hot-path crate (`native/`), Tauri desktop+mobile,
GitHub Actions CI. **Current platform version: 2.3.2.** Single-file source of the whole
platform: `TermAId_Full_Source.md` (97 files; regenerate on every integration).
- Platform workspace (integration): /home/claude/termaid-platform
- CLI project (separate TERMAID_ROOT): /home/claude/termaid_project/termaid-complete-windows
- All deliverables: /mnt/user-data/outputs

## 3. SOPs in force (Chief-of-Staff)
- **Protocol A — Review & Reject:** gate every hand-back against REVIEW_CHECKLIST.md
  (in bounds? Cross-Window Impact filled? Universal rules? independent live verify?).
  Fail → reject back to the agent, don't integrate, don't forward.
- **Protocol B — Mission briefs:** dispatch every task with explicit
  **Context / Objective / Boundaries**.
- **Protocol C — Global state ownership:** on accept, Master updates MASTER_INDEX.md +
  ARCHITECTURE.md "Platform state" + version bump + LESSONS + HISTORY; regenerate bundle.
- Note-taking: Director says "make a note" → append to IDEAS_BACKLOG.md, reply briefly.
- Efficiency lesson: agents hand code back as **.py/.ts/.rs TEXT, not PDF** (PDFs mangle code).

## 4. The loop
Master builds kit → Director deploys to a sub-agent window → sub-agent does its slice →
returns hand-back → Master QC-reviews (Protocol A), integrates, bumps version, updates
global state → Director pushes to GitHub. Each sub-agent runs: Orient → Brainstorm →
Document → Break down → Harden → Health report.

## 5. 14-agent roster + status
| # | Agent | Status |
|---|---|---|
| 00 | Main/Architecture (this window) | active |
| 01 | Database | INTEGRATED v2.3.1 (health 7.0) |
| 02 | Backend Core & API | KITTED — **the linchpin, run next** |
| 03 | Auth & Security | INTEGRATED v2.3.2 (7.3) |
| 04 | AI & The Brain | INTEGRATED v2.3.2 (7.3) |
| 05 | Knowledge & Learning | KITTED (baseline 5.0) |
| 06 | Networking & Scanning | KITTED (5.3) |
| 07 | Native / Rust | KITTED (6.1) |
| 08 | Frontend / UI | KITTED (5.4) |
| 09 | Desktop & Mobile (Tauri) | KITTED (5.2) — **partial hand-back IN REVIEW** |
| 10 | Docker / Deploy / CI-CD | not yet kitted — **next kit to build** |
| 11 | Secrets & Config | not yet kitted |
| 12 | Modules System & Engine | not yet kitted |
| 13 | Testing & QA | not yet kitted |

## 6. OPEN ITEMS (carry these over)
1. **Director ruling needed — brand vs rule.** Agent 09's tauri.conf.json keeps
   productName/title/description as stylized **"TermAId"**. Universal rule 8 says
   normalize stylized→"Termaid" (a Protocol-A reject trigger), BUT it reads as
   intentional branding (Term+AI+aid). Master ESCALATED, did not auto-reject. Pending:
   (A) keep "TermAId" as brand → add an exception to rule 8; or (B) it's a typo → bounce
   to Agent 09. **Also align the CSP:** comment says sidecar 127.0.0.1:8765 but CSP value
   uses http://localhost:8765 (localhost may resolve ::1; sidecar binds 127.0.0.1).
2. **Agent 09 partial hand-back.** Received: tauri.conf.json, main.rs, Cargo.toml,
   build_sidecar.sh, name_sidecar.py (documented+hardened; CSP wildcard removed — good).
   Missing before integration: sidecar.py, runtime.py, build.rs, capabilities/default.json,
   package.json, build_sidecar.ps1, fetch_cli.py + HANDOFF/BREAKDOWN/health/INDEX/HISTORY.
3. **Backend Core (02) is the linchpin** — wiring these closes several open items:
   - `/api/auth/refresh` → `auth.rotate_refresh_token` (returns NEW pair); the Auth
     rotation security fix is INERT until this is wired.
   - `/api/auth/login` → `auth.persist_refresh_session`.
   - Adopt `stream_chat(events=True)` and forward `{kind}` over WS.
4. **Frontend (08)** — store the ROTATED refresh token; handle structured stream events.
5. **Reasoning modules (brain/cognition/cortex/smart/agent/chain)** — adopt
   `brain_config.wrap_untrusted()` on external input + a BrainConfig preset.
6. **Database TODOs** — CI contract test diffing models.py↔schemas.py↔types.ts;
   confirm prod uses `alembic upgrade head` not init_models(); Postgres test run.

## 7. IMMEDIATE NEXT STEPS
1. Get the Director's ruling on the brand question (#6.1); update RULES.md accordingly.
2. Await the rest of the Agent 09 hand-back, then finish the Protocol-A review and
   integrate to v2.3.3 (update MASTER_INDEX + ARCHITECTURE state + LESSONS + HISTORY,
   regenerate TermAId_Full_Source.md).
3. Build the **Agent 10 (Docker/Deploy/CI-CD)** kit next (pattern below), then 11/12/13.

## 8. Kit-build pattern (established)
Gather the slice's owned files → write INDEX.md + BASELINE_HEALTH.md (honest 0–10 scoring)
+ START_PROMPT.txt (with Context/Objective/Boundaries) → bundle a lightweight
`<Slice>_Agent_Kit.md` (+ a separate `<Slice>_Code.md` if the code is large) + a reportlab
PDF brief → copy to /mnt/user-data/outputs → present. Always: code back as text; warn the
agent its hand-back is reviewed against REVIEW_CHECKLIST.md.

## 9. Re-attach these project-knowledge docs to the new window
MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md, WINDOW_DIRECTIVES.md, RULES.md,
LESSONS.md, HISTORY.md, GAME_PLAN.md, REVIEW_CHECKLIST.md, IDEAS_BACKLOG.md,
HANDOFF_TEMPLATE.md, HEALTH_REPORT_TEMPLATE.md, BRAINSTORM_TEMPLATE.md,
README-COMMUNICATION.md, and the latest TermAId_Full_Source.md. (All are in
/mnt/user-data/outputs from this session.)
