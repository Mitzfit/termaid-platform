# Case study: porting `netscan`'s hot path to Rust

This is the worked example of "drop to Rust when Python is the bottleneck," and
the proof of the offline-mobile path. We took the slow part of `netscan` —
TCP port scanning — and moved it to a dependency-free Rust crate that's reachable
from one codebase in three ways.

## One scanner, three transports

```
                       termaid_scan  (native/ — pure std Rust)
                       scan(host, start, end, timeout) -> ScanResult
                                   │
        ┌──────────────────────────┼───────────────────────────┐
        ▼                          ▼                            ▼
  CLI binary                 in-process lib              in-process lib
  termaid-scan               (Tauri dep)                 (Tauri dep, mobile)
        │                          │                            │
  Python backend            desktop app                  phone app
  shells out                native_scan command          native_scan command
  (backend/native.py)       (no Python needed)           (NO Python — offline)
        │                          │                            │
  /api/scan + scan.ports     UI "scan <host>"             UI "scan <host>"
```

- **Desktop, with backend** — `scan.ports 10.0.0.1 1 1024` in the terminal, or
  `POST /api/scan`. The backend shells out to the compiled binary
  (`backend/native.py`). Gated to **local mode** — never exposed on a server.
- **Desktop/mobile, in-process** — the Tauri app depends on the `termaid_scan`
  crate directly and exposes `native_scan` (`src-tauri/src/lib.rs`). The UI's
  `scan <host>` command calls it via `invoke` (`frontend/src/native.ts`). No
  HTTP, no Python — which is exactly what makes it work on a phone.

## Why it's faster

Python's socket scanning is serial-ish and GIL-bound; the Rust version fans the
range across 128 worker threads with per-port connect timeouts. Same logic,
parallel, native. It also annotates well-known ports with service names
(`ssh`, `https`, `ollama`, …) the way `netscan` did.

## Tested both sides

- Rust: `native/tests/scan_test.rs` binds a real ephemeral listener and asserts
  detection, confirms closed ports report nothing, checks service naming and the
  JSON shape. Runs offline in CI (`cargo test`).
- Python: `backend/tests/test_native.py` mocks the binary to test path
  resolution, JSON parsing, formatting, and error handling — no Rust build
  required in that job.

## The pattern, reusable

To port the next bottleneck module:
1. Add the pure function to `native/src/lib.rs` (+ a test).
2. Expose it on the CLI in `main.rs` (JSON out) and add a Tauri command in
   `lib.rs` (in-process).
3. Wrap the CLI in `backend/native.py`, register it via `engine.register_native`
   in the mode where it's safe.
4. Add a `frontend/src/native.ts` branch so the UI uses `invoke` on Tauri and
   the backend in the browser.
