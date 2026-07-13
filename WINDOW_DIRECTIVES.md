# Window Operating Directives  (every window, every session)

These are the standing first-instructions for every focused window. The kit's
start prompt points here. Follow them in order.

## Session order of operations
1. **Orient.** Read `MASTER_INDEX.md`, `ARCHITECTURE.md`, `CODE_STYLE.md`,
   `RULES.md`, `LESSONS.md`, and this window's latest health report before touching code.
2. **Kickoff brainstorm** (`BRAINSTORM_TEMPLATE.md`). Plan before you build:
   brain-dump, review the code, weigh priorities, agree today's ONE task + a
   Definition of Done. Small task → 60-second fast path.
3. **Directive 1 — Document.**
4. **Directive 2 — Break down.**
5. **Directive 3 — Harden.**
6. **Directive 4 — Health report.**
7. **Hand back** using `HANDOFF_TEMPLATE.md` (includes the breakdown + health report;
   note any Local→Universal rule promotions).

**Rules:** obey all UNIVERSAL rules in `RULES.md` plus any LOCAL rules I set for
the session. Local rules can be promoted to universal in the hand-back.

---

## Directive 1 — Document every portion of the code
Comment **every** meaningful portion of this window's code: what it is, what it
does, and **why**. Follow `CODE_STYLE.md` (file headers, function docstrings,
why-not-what inline comments, full type hints).
- **Attribution:** every file header and documented block carries `Author: Misfit`.
- Comment as you go — fully document this window's files this session; don't
  touch other windows' files.

## Directive 2 — Full code breakdown
Isolate each section of this window's code and produce a written breakdown:
each component, **how it works and why** it's built that way, its inputs/outputs,
its dependencies, and where it touches other windows. Deliver this as
`BREAKDOWN.md` in the hand-back. The goal: anyone can understand this slice from
the breakdown alone.

## Directive 3 — Harden & improve
Only after the code is fully understood, improve it where genuinely possible —
performance, architecture, design clarity, and fitness for purpose. Rules:
- Propose changes with rationale; don't change behavior silently.
- Don't break CI or other windows; flag any cross-window impact.
- Prefer the smallest change that meaningfully helps. "No change needed" is a
  valid, honest outcome — say so rather than churn.

## Directive 4 — Health report
End every session with a scored health report (`HEALTH_REPORT_TEMPLATE.md`),
comparing against the baseline/last session so we can see the trend. Include the
top risks and the single highest-value next action.

---

## Why this order
Document → understand → improve → measure. You can't safely harden code you
haven't documented and explained, and you can't tell if hardening helped without
a score to compare. The health reports flow back to the main thread so we can
see, across sessions, whether the platform is actually getting healthier.

## Hand-backs are reviewed (and can be rejected)
The Master Agent runs REVIEW_CHECKLIST.md on every hand-back. It will be REJECTED (sent back to you to fix, not integrated) if you touched files you don't own, left Cross-Window Impact blank, broke a Universal rule (e.g. the Termaid spelling), or skipped a directive. Adhere strictly to your domain.
