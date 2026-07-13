# TermAId — MASTER INDEX

> **Platform version: 2.3.3** &nbsp;|&nbsp; update this on every integrated hand-back. See the Orchestration Playbook (PDF) and GAME_PLAN.md for the workflow.

**This is the core "main TermAId" reference.** Save it to the Project so every
segmented chat window can read it first. When you open a focused window
("this is database", "this is ai", etc.), point me here, attach the listed
files for that segment, and we work only that slice.

Two things live side by side:

- **The Platform** (`termaid-platform/`) — the full-stack app we built: Python
  API, TypeScript UI, Rust native, Tauri desktop/mobile, CI/CD.
- **The TermAId CLI** (your `TERMAID_ROOT`) — the original engine and **120
  modules / 1949 commands** the platform wraps unchanged.

Totals: **120 modules · 1949 commands**, plus ~40 platform files across
backend / frontend / native / desktop-mobile / CI.

---

# PART 1 — THE PLATFORM (what we built)

## 1. Backend — Python / FastAPI  (`backend/`)
| file | owns |
|---|---|
| `main.py` | FastAPI app: REST + WebSocket, auth routes, exec, /api/scan, streaming chat, startup wiring |
| `engine.py` | loads the 120 modules once, policy-filtered; native-command registry; dispatch |
| `policy.py` | module allow-list + local/server deployment modes (safe/ai/system/dangerous sets) |
| `ai_stream.py` | async token streaming for every provider (gemini/openai/anthropic/ollama formats) |
| `providers_extra.py` | adds xAI Grok, Together, Fireworks, DeepInfra at runtime (no CLI fork) |
| `secrets.py` | OS keychain for API keys + env fallback + `python -m backend.secrets` CLI |
| `native.py` | bridge to the Rust binaries (scan.ports, fs.walk): locate, run, parse, format |
| `auth.py` | bcrypt password hashing + JWT access/refresh tokens |
| `database.py` | async SQLAlchemy engine + session (SQLite↔Postgres on one env var) |
| `models.py` | ORM tables: User, CommandHistory, RefreshSession |
| `schemas.py` | Pydantic request/response models |
| `settings.py` | config + the `.env`→environment loader |
| `runtime.py` | frozen-binary path resolution (PyInstaller sidecar) |
| `sidecar.py` | uvicorn entry point for the bundled local backend |
| `termaid-backend.spec` | PyInstaller spec (freezes backend + bundles the CLI) |
| `alembic.ini`, `migrations/` | SQL migrations (env.py, versions/0001_initial.py) |
| `requirements*.txt` | core / `-termux` / `-postgres` dependency sets |
| `tests/` | test_policy, test_stream_parser, test_native, test_api |

## 2. Frontend — TypeScript / Vite  (`frontend/`)
| file | owns |
|---|---|
| `src/main.ts` | app wiring: login → terminal → routes (exec / chat / scan / walk) |
| `src/api.ts` | typed REST client + token refresh |
| `src/ws.ts` | typed WebSocket client (exec results + streaming chat) |
| `src/terminal.ts` | DOM terminal renderer (incl. streaming line) |
| `src/native.ts` | Tauri-invoke ↔ REST bridge for scan/walk |
| `src/types.ts` | shared API/WS type contracts |
| `index.html`, `src/style.css` | terminal UI shell + styling |
| `package.json`, `tsconfig.json`, `vite.config.ts` | build config (proxy to :8000) |

## 3. Native — Rust  (`native/`)
| file | owns |
|---|---|
| `src/lib.rs` | port scanner (`scan`, service names, JSON) + `pub mod fs` |
| `src/fs.rs` | recursive directory walker (fsscan hot path) |
| `src/main.rs` | `termaid-scan` CLI |
| `src/bin/termaid-walk.rs` | `termaid-walk` CLI |
| `tests/scan_test.rs`, `tests/fs_test.rs` | integration tests |

## 4. Desktop / Mobile — Rust / Tauri 2  (`desktop-mobile/`)
| file | owns |
|---|---|
| `src-tauri/src/lib.rs` | app shell; native commands (sha256, scan, walk); spawns the sidecar |
| `src-tauri/src/main.rs` | desktop entry point |
| `src-tauri/Cargo.toml` | deps incl. the native crate path dep |
| `src-tauri/tauri.conf.json` | window, bundle, externalBin (sidecar) |
| `src-tauri/capabilities/default.json` | permissions |

## 5. Deploy / CI  (root + `.github/`)
| file | owns |
|---|---|
| `.github/workflows/ci.yml` | Python + TS + Rust tests on every push |
| `.github/workflows/release.yml` | desktop installers + Android APK on tag |
| `.github/workflows/release-bundled.yml` | self-contained desktop (freezes backend) |
| `scripts/` | build_sidecar.sh/.ps1, name_sidecar.py, fetch_cli.py |
| `Dockerfile`, `docker-compose.yml` | containers (backend + Postgres) |
| `.env.example` | full config template (12 providers + tunables) |

## 6. Docs (root)
`ARCHITECTURE.md` · `SETUP.md` · `GAME_PLAN.md` · `CODE_STYLE.md` · `HANDOFF_TEMPLATE.md` · `CUSTOM_INSTRUCTIONS.txt` · `TermAId_Orchestration_Playbook.pdf` · `SETUP.md` (Termux/Linux/Windows) · `BUILD_LOCAL_APP.md` ·
`NATIVE_PORT.md` · `README.md` · this `MASTER_INDEX.md`

---

# PART 2 — THE TERMAID CLI (your TERMAID_ROOT)

## Core package  (`termaid/`)
| file | owns |
|---|---|
| `__main__.py`, `cli.py` | CLI entry + argument handling |
| `repl.py` | the REPL loop + command dispatch |
| `config.py` | config loader / paths |
| `platform_detect.py` | OS / Termux / WSL detection |
| `providers/__init__.py` | **PROVIDER_SPECS** + AIClient (the 8 built-in providers) |
| `extensions/__init__.py` | **ModuleManager** — discovers/loads modules, command registry |
| `session.py` | session state |
| `boot/loader.py` | boot sequence |
| `setup_wizard.py` | first-run setup |
| `tools/`, `utils/` | shared helpers |

## Shared module helpers  (`modules/_shared/`)
`db.py` (sqlite helper) · `paths.py` · `output.py` · `error_helper.py` ·
`confirm.py` · `atomic.py` · `locking.py` · `subprocess_helper.py` ·
`explain.py` · `health.py`

---

# PART 3 — ALL 120 MODULES (by safety category)

Category drives the deployment policy: **safe + ai** load in server mode;
**system** loads only in local mode; **dangerous** is opt-in even locally.

### SAFE — pure compute / own-data (load everywhere)  (27 modules)

Exposable to anyone. Good first targets for the web app.

| module | cmds | what it does |
|---|---|---|
| `aliases` | 11 | User-defined command shortcuts |
| `banner` | 9 | Dynamic rotating welcome banners with quotes |
| `calc` | 12 | Calculator, unit conversion, base conversion (safe — no eval) |
| `catalog` | 11 | Discover modules and commands across TermAId |
| `clip` | 11 | Cross-platform clipboard manager with history |
| `diff` | 11 | File and directory comparison via difflib |
| `errors` | 13 | Error log inspection, analysis, and fix suggestions |
| `header` | 13 | Top-of-terminal dashboard: version, user, IPs, MAC, device, storage |
| `learn` | 25 | Knowledge base, memory, and curated learning resources |
| `lessons` | 13 | User-validated patterns shaping future AI behavior |
| `manifest` | 11 | Verify module command manifests vs docstrings |
| `markets` | 33 | Read-only crypto and stock data, watchlists, portfolio tracking, educa |
| `memory` | 13 | Long-term facts the AI should remember about user/setup |
| `notes` | 16 | Quick local note-taking with tags and search |
| `paper` | 23 | Paper trading simulator with real market data |
| `password` | 10 | Password generation, strength analysis, HIBP breach check |
| `persona` | 11 | AI identity and communication style |
| `qr` | 8 | QR code generation for terminal and PNG export |
| `quick` | 9 | Favorites system for frequently-used commands |
| `regex` | 13 | Regex testing, debugging, and library with AI assistance |
| `research` | 13 | Web fetch + AI summarization for research workflows |
| `rules` | 15 | Restrictions and instructions for AI behavior |
| `style` | 15 | Customize TermAId colors, themes, prompt, banner style |
| `text` | 29 | Text processing utilities: case, sort, dedupe, wrap, count, replace |
| `translate` | 9 | Translation via configured AI (no separate API key) |
| `weather` | 10 | Weather and forecast via wttr.in (no API key needed) |
| `welcome` | 9 | Login flow orchestrator: banner + dashboard + suggestions |
### AI — need a provider, otherwise side-effect-free  (12 modules)

Load in server mode when a key is configured.

| module | cmds | what it does |
|---|---|---|
| `agent` | 16 | AI middleman: auto-detect problems, propose fixes |
| `aiconfig` | 19 | AI behavior config profiles bundling persona + rules + hardlines |
| `aitools` | 18 | Unified launcher for free + paid AI CLI agents |
| `assistant` | 20 | Proactive AI guidance with tutorials and admin-aware mode |
| `brain` | 16 | Layered system prompt orchestrator — the AI's brain |
| `chain` | 11 | Sequence multiple TermAId commands |
| `cognition` | 21 | Configure how the AI reasons: depth, planning, self-check, verbosity,  |
| `cortex` | 11 | Persistent AI memory, persona, and logic rules |
| `imagegen` | 10 | Gemini Nano Banana image generation |
| `learner` | 14 | Learn user, system, and hardware for personalized AI suggestions |
| `qa` | 18 | Universal tester + configurator + improver across all modules |
| `smart` | 13 | Auto-detect wrong commands, suggest corrections |
### SYSTEM — touch the host (local mode only)  (48 modules)

Shell out, scan, manage files/processes/VMs/repos. Blocked on servers.

| module | cmds | what it does |
|---|---|---|
| `apikeys` | 17 | Multiple API keys per provider + model selection |
| `autoconfig` | 9 | AI-powered automatic system configuration |
| `backup` | 11 | Back up TermAId user data and config |
| `bench` | 18 | CPU, memory, disk, and network benchmarks |
| `bots` | 28 | Bot creation, deployment, management, and monitoring |
| `cleanup` | 16 | Detect and remove stale TermAId artifacts |
| `config` | 23 | Generate configuration files (Docker, k8s, YAML, shell, langs) |
| `dashboard` | 12 | Comprehensive login info screen |
| `dbkeys` | 13 | Relational DB with comprehensive keys and relationship analysis |
| `debug` | 19 | In-process debugger, introspection, and AI trace console |
| `devdetect` | 10 | OS, hardware, and capability detection |
| `diskspace` | 15 | Disk space analysis: largest files, duplicates, cleanup |
| `docker` | 19 | Container management: ps, run, logs, compose, prune, lint |
| `doctor` | 15 | Auto-detect problems and offer fixes (Termux-aware) |
| `env` | 15 | Environment variable and PATH management |
| `extras` | 32 | Wrappers for 36 popular open-source CLI tools |
| `filetools` | 12 | File operations: hash, compress, encrypt, analyze |
| `find` | 10 | Fast cross-module command search and drill-down help |
| `fsscan` | 14 | File system health scan and AI-powered cleanup |
| `git` | 28 | Multi-repo git workflow + GitHub CLI integration |
| `hardware` | 16 | Deep hardware inventory, sensors, and driver update checks |
| `improve` | 14 | AI-assisted source code improvement (review + apply with consent) |
| `keyring` | 16 | Encrypted secret storage with categories, tags, audit |
| `log` | 14 | Log file tail, follow, filter, and AI analysis |
| `netdeep` | 16 | Deep network inspection: WiFi, Ethernet, Bluetooth, VPN |
| `netscan` | 15 | Network overview, threat assessment, and effectiveness scoring |
| `nettools` | 17 | Active networking utilities: ping, dns, whois, tcp, ssl |
| `notify` | 11 | Desktop and webhook notifications (cross-platform) |
| `perftune` | 17 | Performance tuning on your own machine |
| `proj` | 19 | Project discovery, inventory, and portfolio stats |
| `pyenv` | 20 | Python interpreters, virtualenvs, packages, and tooling |
| `repo` | 26 | GitHub repo cloning + AI security/improvement analysis + tool registra |
| `router` | 12 | Smart API routing + .env key management |
| `sandbox` | 11 | Isolated testing environment with snapshot / restore |
| `schedule` | 15 | Scheduled task management with cron/systemd/Windows Task generation |
| `selftest` | 12 | Automated smoke tests across all modules |
| `serve` | 15 | Quick local HTTP server for sharing, uploading, tunneling |
| `session` | 9 | Track session history, last logins, command counts |
| `sql` | 14 | SQLite database operations with AI query generation |
| `sync` | 13 | File synchronization via rsync (local/SSH) and rclone (cloud) |
| `sysmonitor` | 9 | System resource monitoring |
| `termux` | 17 | Termux:API integration (battery, sensors, vibrate, etc.) |
| `tmx` | 17 | Deep Termux environment control |
| `tools` | 12 | Registry for repo-installed tools with /tools run interface |
| `verify` | 14 | Hash and GPG signature verification for downloads |
| `vm` | 25 | Container + VM inventory: Docker/Podman/VBox/VMware/Hyper-V/WSL/LXC |
| `workspace` | 21 | Projects + tasks + artifacts for workflow streamlining |
| `wsl` | 18 | WSL / WSL2 management on Windows |
### DANGEROUS — privilege / firmware / irreversible (opt-in)  (26 modules)

Never auto-exposed in either mode. Opt in per-module, deliberately.

| module | cmds | what it does |
|---|---|---|
| `adb` | 25 | Android Debug Bridge wrapper for user-owned devices |
| `admin` | 18 | Single-admin authentication, advanced features, source-improvement rep |
| `bootmgr` | 18 | Boot manager (GRUB / systemd-boot / Windows BCD) inspection + repair |
| `crypto` | 23 | Local cryptography toolkit: hash, sign, encrypt, keys, passwords |
| `device` | 35 | Direct phone & app access (Termux:API + ADB), no third-party keys. |
| `devicescan` | 16 | Cross-platform device enumeration (USB, Bluetooth, LAN, etc.) |
| `disktool` | 19 | Disk operations: partitions, SMART, encryption, imaging |
| `dualboot` | 15 | Dual-boot setup, sharing, and recovery |
| `fastboot` | 15 | Fastboot wrapper for user-owned device bootloader operations |
| `firmware` | 13 | BIOS/UEFI introspection and pre-boot recovery helpers |
| `firstrun` | 10 | Comprehensive first-run setup wizard |
| `fwown` | 16 | PC firmware inventory + vendor update guidance |
| `hardlines` | 22 | Immutable AI rules with categorization, comments, effectiveness scorin |
| `multiboot` | 11 | ISO library, verification, and bootable USB creation |
| `perms` | 13 | Permission detection and elevation walkthroughs |
| `privesc` | 21 | Defensive privilege escalation audit for YOUR own machine |
| `recovery` | 16 | Bootable recovery USB creation walkthroughs |
| `rootguide` | 24 | Vendor-specific mobile rooting walkthroughs |
| `sec` | 24 | Local security hardening audit |
| `security` | 39 | Comprehensive security policies for user and admin with auto-apply at  |
| `selfmod` | 15 | Self-modification: read, edit, harden, improve own code |
| `sudo` | 6 | Pseudo-sudo for one-shot elevation of TermAId commands |
| `syscmd` | 25 | Cross-OS command add-ons, symbols, loops, problem patterns |
| `sysint` | 17 | Sysinternals frontend + Linux equivalents for system audit |
| `uefi` | 19 | UEFI / BIOS inspection and education on your own PC |
| `usbdeep` | 15 | USB device deep inspection and troubleshooting |
### UNCATEGORISED — review & classify  (7 modules)

Not yet placed in the policy sets — decide safe/system/dangerous per module.

| module | cmds | what it does |
|---|---|---|
| `api` | 19 | HTTP client for REST/GraphQL API testing |
| `auth` | 10 | User accounts, sessions, password hashing |
| `dev` | 50 | AI-native development suite: editor, project intel, codegen, runners. |
| `health` | 12 | Aggregate health check across security, hardware, network, performance |
| `pdf` | 11 | PDF inspection, text extraction, merge, split, rotate |
| `ratelimit` | 10 | Track AI provider usage vs free-tier limits |
| `repl` | 13 | Meta-commands for the TermAId REPL itself |
---

# PART 4 — SUGGESTED CHAT-WINDOW MAP

Each row = one focused window. Open it, tell me the role, attach the files.

| window | owns | attach these |
|---|---|---|
| **main / architecture** (this one) | index, cross-cutting decisions, roadmap | `MASTER_INDEX.md`, `ARCHITECTURE.md` |
| **database** | schema, migrations, ORM | `models.py`, `database.py`, `migrations/`, `_shared/db.py` |
| **backend-core** | API, auth, engine, policy, rate limit | `main.py`, `auth.py`, `engine.py`, `policy.py`, `schemas.py`, `settings.py` |
| **ai / brain** | providers, streaming, AI modules | `ai_stream.py`, `providers_extra.py`, `providers/__init__.py`; modules: assistant, brain, cognition, cortex, smart, agent, chain |
| **native-rust** | scanner, walker, Tauri commands | `native/`, `desktop-mobile/src-tauri/` |
| **frontend** | TS UI + bridges | `frontend/src/` |
| **modules-system** | how modules load + the registry | `extensions/__init__.py`, `_shared/` |
| **docker / deploy / CI** | containers + pipelines | `Dockerfile`, `docker-compose.yml`, `.github/`, `scripts/` |
| **secrets / config** | keychain + `.env` | `secrets.py`, `settings.py`, `.env.example` |
| **learning / knowledge** (CLI modules) | the learn/lessons/memory features | modules: learn, learner, lessons, memory, cognition, brain |

**The rule that keeps it sane:** when a decision changes the architecture,
update `ARCHITECTURE.md` (and this index) in the Project. That file is the single
source of truth every window reads — the windows don't see each other live.

## Cross-window TODOs (open)
HIGH — security fix is inert until wired (Auth v2.3.2):
- [Backend Core] `/api/auth/refresh` must call `auth.rotate_refresh_token(db, token)`
  and return the NEW pair (currently returns the same token = no rotation).
- [Backend Core] `/api/auth/login` should call `auth.persist_refresh_session(...)`.
- [Frontend] store the NEW refresh_token returned by /api/auth/refresh; stop reusing the old.
From AI v2.3.2:
- [Backend Core] adopt `stream_chat(..., events=True)` and forward `{kind}` over WS
  (stop string-sniffing `[err]` chunks).
- [Reasoning modules brain/cognition/cortex/smart/agent/chain] adopt
  `brain_config.wrap_untrusted()` on external input + a `BrainConfig` preset.
From Database v2.3.1 (still open):
- [Backend+Frontend+QA] CI contract test diffing models.py ↔ schemas.py ↔ types.ts.
- [Backend] confirm prod startup uses `alembic upgrade head`, not init_models().
- [QA] Postgres-backed run of test_models.py.
Ops-desk finding (2026-06-14):
- settings.py default `jwt_secret="CHANGE_ME_use_openssl_rand_hex_32"` was NOT in
  auth `_FORBIDDEN_SECRETS` — FIXED in auth.py this integration; [Config] should also
  avoid shipping a guess-proof-looking default.
