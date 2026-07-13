# Agent 06 — Networking & Scanning (kit)

Attach BOTH this file and `Networking_Code.md` to the agent window. This file = brief/baseline/start; the code file = the owned source.

---

# Agent 06 — Networking & Scanning

**Role:** Network engineer. Network analysis + the fast scanner bridge. Powerful,
host-touching, and LOCAL-MODE ONLY — handle with care.
**Baseline health:** 5.3 / 10 (set 2026-06-14).

## Owns
- `modules/netscan/__init__.py` — interfaces, DNS/gateway, port scan, threat detection.
- `modules/nettools/__init__.py` — networking utilities.
- `modules/netdeep/__init__.py` — deeper network analysis.
- `backend/native.py` — Python bridge to the Rust `termaid-scan` binary
  (locates binary via TERMAID_SCAN_BIN / dev build / PATH; parses JSON).
- `backend/tests/test_native.py` — native-bridge tests (maintain + extend).

## Depends on / feeds
- Reads: Native/Rust (Agent 07) for the compiled scanner; the `fs.walk` path in
  native.py overlaps with Native — coordinate, don't duplicate.
- Gated by: Auth & Security (Agent 03) — netscan/nettools/netdeep are SYSTEM
  modules, blocked in server mode. KEEP IT THAT WAY.

## Safety watch-items (this slice is sensitive)
- Scanning must stay LOCAL-MODE ONLY (confirm policy still classifies all three
  as SYSTEM, never SAFE). Never expose scanning over a server deployment.
- Default to bounded, local-target scans; do not ship aggressive/wide scans by
  default. Network scanning of third parties has legal/abuse implications.

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document → Break down → Harden → Health report. Obey RULES.md.
Never touch another window's files.


---

# Health Report — Networking & Scanning  (BASELINE, v2.3.2, 2026-06-14)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | Working cross-platform modules; native.py has binary-locate fallbacks. |
| Security | 5 | Sensitive: scanning tools. Correctly SYSTEM-gated (local-only) — must stay so. Default scan scope/bounds need review. |
| Performance | 7 | Hot path is the Rust scanner (fast); CLI modules shell out. |
| Architecture / maintainability | 5 | netscan ~769 lines, mixed concerns (interfaces + DNS + ports + threats). |
| Test coverage | 4 | native.py has test_native.py; the 3 CLI modules untested. |
| Documentation | 4 | Module docstrings exist; per-function/why docs thin. |
| Cross-window cohesion | 6 | native.py ↔ Rust crate (07); modules ↔ policy (03). |
| **Overall** | **5.3** | Capable, performance-minded networking layer; large modules, light tests, and a sensitivity that needs explicit guardrails. |

## Top 3 risks
1. Misuse/legal surface — scanning must remain local-only and bounded by default.
2. netscan is large and mixes concerns — hard to reason about until broken down.
3. The 3 CLI modules are untested.

## Highest-value next action
Directive 1 + 2 on netscan (document + breakdown) to understand it; verify the
local-mode gating and add sane default scan bounds; add tests for native.py JSON
parsing → Documentation 4→7, Tests 4→6.


---

## START PROMPT (paste into the new agent window)

```
This is the NETWORKING & SCANNING agent.

Your role: network engineer. You own the CLI networking modules (netscan, nettools,
netdeep) and backend/native.py (the Python bridge to the Rust termaid-scan binary),
plus backend/tests/test_native.py. Work ONLY on these; never touch another window's
files. The Rust scanner crate itself is the Native window's (Agent 07) — coordinate,
don't fork it.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md, LESSONS.md, BASELINE_HEALTH.md.

SENSITIVE SLICE — safety watch-items:
- Scanning must stay LOCAL-MODE ONLY. Confirm netscan/nettools/netdeep remain SYSTEM
  modules (blocked in server mode). Never expose scanning over a server deployment.
- Default to bounded, local-target scans; no aggressive/wide scans by default.
  Network scanning of third parties has legal/abuse implications.

Run the kickoff brainstorm (suggest focusing on netscan first — it's the largest),
then the four directives: 1) Document (what/does/why, Misfit), 2) Break down
(BREAKDOWN.md), 3) Harden (incl. scan bounds + gating), 4) Health report.

Hand back with HANDOFF_TEMPLATE.md + updated files (as .py text, not PDF) + INDEX +
BREAKDOWN + health report + appended HISTORY. Bump the version.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```


---
## HISTORY (append each session)

- 2026-06-14 · main · Kit created (baseline 5.3). Awaiting first session.
