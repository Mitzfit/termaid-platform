# Agent 07 — Native / Rust Performance (kit)

Attach BOTH this file and `Native_Rust_Code.md` to the agent window. This file = brief/baseline/start; the code file = the owned Rust source.

---

# Agent 07 — Native / Rust Performance

**Role:** Systems engineer. The Rust hot-path crate (port scanner + filesystem
walker) — the "we ported the slow part to Rust" layer. Memory-safe, std-only,
dependency-free.
**Baseline health:** 6.1 / 10 (set 2026-06-14).

## Owns
- `native/Cargo.toml`
- `native/src/lib.rs` — port scanner + `pub mod fs`.
- `native/src/fs.rs` — directory walker.
- `native/src/main.rs` — `termaid-scan` CLI (JSON out).
- `native/src/bin/termaid-walk.rs` — `termaid-walk` CLI.
- `native/tests/scan_test.rs`, `native/tests/fs_test.rs`.
- Shared edge: `desktop-mobile/src-tauri/src/lib.rs` native commands
  (`native_scan`/`native_walk`/`native_sha256`) — coordinate with Agent 09, who
  owns the rest of `desktop-mobile/`.

## Depends on / feeds
- Feeds: Networking (Agent 06) bridges the scanner via `backend/native.py`;
  Desktop/Mobile (Agent 09) calls the Tauri commands.
- Tied to: the Networking safety story — the scanner's timeout + thread-pool caps
  are part of "bounded, local-only scans". Keep those bounds sane.

## Standing job (WINDOW_DIRECTIVES)
Brainstorm → Document (`///` doc-comments) → Break down → Harden → Health report.
Obey RULES.md. Never touch another window's files. CI builds Rust — keep `cargo
build`, `cargo test`, and `cargo clippy` green.


---

# Health Report — Native / Rust  (BASELINE, v2.3.2, 2026-06-14)

| Category | Score | Notes |
|---|---|---|
| Correctness / reliability | 6 | Crate compiles in CI; scan_test + fs_test exist. Never built in this sandbox (no Rust toolchain) — CI is the source of truth. |
| Security | 7 | Memory-safe Rust, std-only (no third-party supply chain). Scanner bounds tie to the networking safety story. |
| Performance | 8 | The whole point of this slice — bounded thread pool, fast scan/walk. |
| Architecture / maintainability | 7 | Clean, dependency-free, small modules. |
| Test coverage | 5 | scan_test + fs_test present but not run here; coverage of edge cases (timeouts, bad input) light. |
| Documentation | 4 | Some comments; needs `///` doc-comments per CODE_STYLE, Misfit-attributed. |
| Cross-window cohesion | 6 | Bridged by native.py (06) + Tauri lib.rs (09); the JSON contract is informal. |
| **Overall** | **6.1** | Strong, fast, safe core; under-documented and lightly tested, with an informal JSON contract to its consumers. |

## Top 3 risks
1. JSON output contract (scan/walk → native.py) is informal — a field change breaks the bridge silently.
2. Doc-comments thin — the hot path should be the best-explained code in the repo.
3. Edge-case tests light (timeouts, unreachable hosts, permission-denied dirs).

## Highest-value next action
Directive 1 (`///` doc-comments on every public item) + document the JSON output
schema as the contract Networking depends on; add edge-case tests (timeout,
refused, denied) → Documentation 4→8, Tests 5→7. `cargo clippy` clean.


---

## START PROMPT (paste into the new agent window)

```
This is the NATIVE / RUST PERFORMANCE agent.

CONTEXT: Platform v2.3.2. Agent 06 (Networking) owns backend/native.py, the Python
bridge that shells out to this crate's termaid-scan binary and parses its JSON — so
this crate is its upstream dependency, and your JSON output is a contract.

OBJECTIVE: Document → break down → harden the Rust hot-path crate (scanner + fs
walker). Document every public item with /// doc-comments per CODE_STYLE
(Misfit-attributed), write down the JSON output schema as the contract, and add
edge-case tests. End with a health report.

BOUNDARIES: you own native/ fully (Cargo.toml, src/, tests/). The Tauri
desktop-mobile/src-tauri/src/lib.rs native commands are a SHARED edge with Agent 09
— you may refine the native command bodies, but do NOT take over the rest of
desktop-mobile/ (config, packaging, sidecar). Never touch other windows' files.

Read from project knowledge first: MASTER_INDEX.md, ARCHITECTURE.md, CODE_STYLE.md,
WINDOW_DIRECTIVES.md, RULES.md, LESSONS.md, BASELINE_HEALTH.md. Run the kickoff
brainstorm, then the four directives. Keep cargo build/test/clippy green (CI builds Rust).

Hand back with HANDOFF_TEMPLATE.md + updated files (as .rs text, not PDF) + INDEX +
BREAKDOWN + health report + appended HISTORY. Bump the version. Note: your hand-back
is reviewed against REVIEW_CHECKLIST.md and rejected if it strays out of bounds.

Your files are attached. Today's task: <I will set this in the brainstorm>.

```


---
## HISTORY (append each session)

- 2026-06-14 · main · Kit created (baseline 6.1). Awaiting first session.
