# TermAId — Orchestration Game Plan (editable companion to the PDF playbook)

**You = orchestrator/middleman. This window = ops desk + source of truth.**
Focused windows own one slice each and never see each other live; you carry work
between them, and the master index keeps everything honest.

## The loop
1. **Issue** — ops desk hands you a window kit (PDF brief + full source + master index).
2. **Assign** — you open the window, paste its start prompt, attach its files, set the task.
3. **Work** — the window does only its slice; ends with a HANDOFF + files/ + INDEX.md.
4. **Return** — you bring the hand-back here.
5. **Integrate** — ops desk merges it, updates master index + ARCHITECTURE, bumps the
   version, flags cross-window effects, regenerates affected source.
6. **Push** — you commit on a `window/<name>` branch and push; CI verifies.

## Versioning
`MAJOR.MINOR.PATCH` at the top of `MASTER_INDEX.md`. PATCH per integrated hand-back,
MINOR for a new feature, MAJOR for a breaking change.

## GitHub flow
```
git checkout -b window/database
# paste integrated files from the ops desk
git add -A && git commit -m "database: <summary>"
git push -u origin window/database   # open PR → merge when CI is green
```

## The windows (build order = dependencies first)
0. Main / Architecture — this thread (hub)
1. Database & Data Structures
2. Backend Core & API
3. Auth & Security
4. AI & The Brain
5. Knowledge & Learning
6. Networking & Scanning
7. Native / Rust Performance
8. Frontend / UI
9. Desktop & Mobile (Tauri)
10. Docker / Deploy / CI-CD
11. Secrets & Config
12. Modules System & Engine
13. Testing & QA

Each window's owned files + role are in `MASTER_INDEX.md` (Part 4) and the PDF playbook (§5).

## The one rule
When a change affects the architecture, update `ARCHITECTURE.md` and `MASTER_INDEX.md`
here before pushing. Those two files are the live state every window reads first.

## Mission brief format (Protocol B — how the Master Agent dispatches a task)
Every task dispatched to a sub-agent states three things explicitly:
- **Context:** what recently changed in the platform (version, relevant hand-backs).
- **Objective:** the exact task, with its Definition of Done.
- **Boundaries:** the precise files it may touch; everything else is read-only.

## Chain of command
Director (human, vision + approval) → Chief of Staff (external, SOP drafts) →
Master Agent (this window: PM, QC gate, global-state owner) → sub-agents (scoped
workers). The Master Agent is a strict gatekeeper: hand-backs are reviewed against
REVIEW_CHECKLIST.md and rejected if they fail.
