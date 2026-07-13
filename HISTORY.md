# HISTORY — running log (append every session, every window)

- 2026-06-15 · main · Configuration alignment across Python backend, Vite frontend, and Tauri desktop GUI to support the unified root workspace. Fixed port mismatches and spelling conventions. Platform v2.3.2→2.3.3.
- 2026-06-13 · main · Built full platform + orchestration system (master index,
  playbook PDF, window directives, universal/local rules, brainstorm + health +
  hand-back templates, lessons, glossary, 5.7 baseline). Captured 4 future modules
  (design, stock/trading, marketing, cloud) and the vision. Shifted this window to
  senior-developer / supervisor role. Added the "history at end of every PDF" rule.
- 2026-06-13 · database · First session integrated. Documented + hardened 6 files,
  added 12 tests (helper 6/6 verified live; model suite for CI). created_at server
  defaults; get_db rollback-on-exception. Health 5.8→7.0. Promoted Universal rule
  (Termaid spelling). Platform v2.3.0→2.3.1.
- 2026-06-14 · ai · Documented+hardened model layer; NEW brain_config.py (presets,
  compile, wrap_untrusted injection boundary); cancel/timeout-safe streaming +
  events=True; providers_extra validation; tests 6→28. Health 5.9→7.3.
- 2026-06-14 · auth · Documented auth.py+policy.py; implemented refresh rotation/
  revoke-on-use + server-mode JWT-secret guard + revoke_all_for_user; deconflicted
  policy (find→SYSTEM-only, SAFE=27); auth+category tests. Health 5.9→7.3.
- 2026-06-14 · main · Integrated both at v2.3.2. Verified live: policy integrity,
  brain_config, parser, provider validation. Ops-desk hotfix: added shipped default
  to auth _FORBIDDEN_SECRETS. Promoted Universal rule 9 (structured error contract).
  OPEN: Backend Core must wire rotate_refresh_token + events=True. Platform 2.3.1→2.3.2.
- 2026-06-14 · main · Orchestration upgrade: adopted review-and-reject QC gate,
  mission-brief format, and ARCHITECTURE.md state ownership. No version bump (process).
