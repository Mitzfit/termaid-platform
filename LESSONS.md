# LESSONS — the team's running memory

Every window appends here; the main thread and every new window read it first.
This is how we "learn as a team" despite windows not sharing live memory:
written knowledge > tribal memory.

Format:  `YYYY-MM-DD · <window> · <lesson / decision / gotcha>`

## Seeded (workflow decisions so far)
- 2026-06-13 · main · Windows are isolated; the orchestrator carries work between
  them and the master index is the single source of truth.
- 2026-06-13 · main · Standard hand-back contract (HANDOFF_TEMPLATE) makes
  integration mechanical; the Cross-Window Impact line is the most important field.
- 2026-06-13 · main · Code is documented per CODE_STYLE.md, attributed to Misfit,
  commented as each window is worked (not all 120 modules at once).
- 2026-06-13 · main · Every session: Document → Break down → Harden → Health report.
- 2026-06-13 · main · Health reports are scored and trend-tracked so we can prove
  the platform is improving, not just changing.

## Process improvements (add as we find them)
- 2026-06-13 · main · Two rule layers: UNIVERSAL (permanent) + LOCAL (session,
  promotable). Local rules that earn their keep get promoted in the hand-back.
- 2026-06-13 · main · Every session opens with a kickoff brainstorm (brain-dump →
  review → priorities → Definition of Done) to set a baseline and stay on task.
- 2026-06-13 · main · Guard against process bloat: small tasks use the 60-second
  brainstorm fast path; process should accelerate work, never gate it.
- 2026-06-13 · database · A non-optional column needs a server_default in the
  migration too, or the ORM default and the DB disagree on non-ORM inserts.
- 2026-06-13 · database · async get_db must roll back on exception before close,
  or a half-finished transaction can ride a pooled connection into the next request.
- 2026-06-13 · main · Agents deliver code as PDF when on mobile; reconstruct to clean
  source on integration and re-run/verify before trusting it.
- 2026-06-14 · auth · A security capability is worthless until it's wired: refresh
  rotation existed only as minted helpers; the route still returned the same token.
  Implement AND wire (or flag the wire-up as blocking) — 'available' ≠ 'enforced'.
- 2026-06-14 · auth · A secret-guard's deny-list must include the value the app
  actually ships as its default, or the guard is decorative. (Caught at integration.)
- 2026-06-14 · ai · Writing the error-path tests surfaced a real bug (httpx imported
  before validation). Error-path tests pay for themselves.
- 2026-06-14 · main · Adopted Chief-of-Staff SOPs: explicit review-and-reject QC
  gate (REVIEW_CHECKLIST.md), standardized mission briefs (Context/Objective/
  Boundaries), and Master-Agent ownership of MASTER_INDEX + ARCHITECTURE state.
- 2026-06-14 · main · Context-rot fix: ARCHITECTURE.md now carries a versioned
  'Platform state' section, updated on every accepted hand-back.
