# SETUP — Termux · Linux · Windows 11

Step-by-step commands to configure and run TermAId Platform on each OS. Read the
matrix first, then jump to your platform.

## What runs where

| Component | Linux | Windows 11 | Termux (Android) |
|-----------|:-----:|:----------:|:----------------:|
| Backend (Python API) | ✅ | ✅ | ✅ |
| Frontend (web UI, dev/build) | ✅ | ✅ | ✅ (use in phone browser) |
| Native crate (`cargo build/test`) | ✅ | ✅ | ✅ |
| Desktop app (Tauri installer) | ✅ | ✅ | ❌ (no webview/display) |
| Mobile app (APK/IPA) | build on desktop | build on desktop | ❌ build here |
| OS keychain for secrets | ✅ (Secret Service) | ✅ (Cred Manager) | ⚠ falls back to env |

Everywhere: set `TERMAID_ROOT` to your extracted TermAId CLI folder, and pick
`DEPLOYMENT_MODE` — `local` (full power, native scan/walk commands) or `server`
(locked-down allow-list). Generate a JWT secret with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## A. Linux (Debian / Ubuntu / Kali)

### 1. System prerequisites

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git build-essential curl

# Node 22 (apt's node is often too old — use NodeSource)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Rust (for the native crate + Tauri)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
. "$HOME/.cargo/env"

# Tauri desktop build deps (skip if you only run the web app)
sudo apt install -y libwebkit2gtk-4.1-dev libssl-dev libayatana-appindicator3-dev \
  librsvg2-dev libxdo-dev file wget
```

### 2. Get the code & backend

```bash
tar -xzf termaid-platform.tar.gz
cd termaid-platform

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# optional Postgres driver: pip install -r requirements-postgres.txt

cp .env.example .env
# edit .env: set TERMAID_ROOT, JWT_SECRET, DEPLOYMENT_MODE=local
nano .env

cd backend && alembic upgrade head && cd ..
```

### 3. Secrets (keychain)

```bash
# stores in GNOME Keyring / KWallet if a desktop session is running
python -m backend.secrets set GEMINI_API_KEY
python -m backend.secrets list
# headless server with no Secret Service? it auto-falls back to env vars.
```

### 4. Native crate (enables scan.ports / fs.walk in local mode)

```bash
cd native && cargo build --release && cargo test && cd ..
```

### 5. Run (two terminals)

```bash
# terminal 1 — API
source .venv/bin/activate
uvicorn backend.main:app --reload --port 8000

# terminal 2 — web UI (proxies /api and /ws to :8000)
cd frontend && npm install && npm run dev
```

Open <http://localhost:5173>.

### 6. Build the desktop app (optional)

```bash
cd desktop-mobile && npm install && npm run build
# installers land in src-tauri/target/release/bundle/ (.AppImage, .deb)
```

---

## B. Windows 11 (PowerShell)

Run PowerShell as your normal user. `winget` ships with Windows 11.

### 1. System prerequisites

```powershell
winget install -e --id Python.Python.3.12
winget install -e --id OpenJS.NodeJS.LTS
winget install -e --id Git.Git
winget install -e --id Rustlang.Rustup

# Tauri on Windows needs the MSVC C++ build tools (WebView2 is already on Win 11)
winget install -e --id Microsoft.VisualStudio.2022.BuildTools `
  --override "--quiet --add Microsoft.VisualStudio.Workload.VCTools"

rustup default stable
```

Close and reopen PowerShell so PATH updates take effect.

### 2. Get the code & backend

```powershell
tar -xzf termaid-platform.tar.gz
cd termaid-platform

py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
notepad .env    # set TERMAID_ROOT, JWT_SECRET, DEPLOYMENT_MODE=local

cd backend; alembic upgrade head; cd ..
```

If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

### 3. Secrets (Windows Credential Manager — works out of the box)

```powershell
python -m backend.secrets set GEMINI_API_KEY
python -m backend.secrets status
```

### 4. Native crate

```powershell
cd native; cargo build --release; cargo test; cd ..
```

### 5. Run (two PowerShell windows)

```powershell
# window 1 — API
.\.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --port 8000

# window 2 — web UI
cd frontend; npm install; npm run dev
```

Open <http://localhost:5173>.

### 6. Build the desktop app (optional)

```powershell
cd desktop-mobile; npm install; npm run build
# → src-tauri\target\release\bundle\  (.msi and .exe installers)
```

---

## C. Termux (Android)

Termux runs the **backend + web UI + native Rust binaries** directly on the
phone. You use it through the phone's browser. It can **not** build the Tauri
desktop or Android app — build the APK on a desktop (see `release.yml`).

### 1. Packages

```bash
pkg update && pkg upgrade -y
pkg install -y python rust nodejs-lts git clang make binutils openssl libffi
# prebuilt cryptography avoids a slow/fragile source build:
pkg install -y python-cryptography
```

### 2. Get the code & backend

```bash
tar -xzf termaid-platform.tar.gz
cd termaid-platform

# venv that can see the prebuilt python-cryptography from pkg
python -m venv .venv --system-site-packages
source .venv/bin/activate

# Termux-specific deps: no uvloop/httptools/asyncpg native builds
pip install -r requirements-termux.txt

cp .env.example .env
# Termux has no system editor by default; use nano:
pkg install -y nano && nano .env
# set TERMAID_ROOT (e.g. /data/data/com.termux/files/home/termaid-complete-windows),
# JWT_SECRET, and DEPLOYMENT_MODE=local

cd backend && alembic upgrade head && cd ..
```

### 3. Secrets on Termux

There's no Secret Service, so the keychain isn't available — that's expected and
handled. Keep keys in `.env` (or export them), and verify:

```bash
python -m backend.secrets status      # → keyring available: False (fine)
```

### 4. Native crate (works — pure std Rust)

```bash
cd native && cargo build --release && cargo test && cd ..
```

### 5. Run

```bash
# terminal 1 (Termux session) — API. Plain uvicorn (no [standard]); WS via websockets.
source .venv/bin/activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000

# terminal 2 (swipe from left → NEW SESSION) — web UI
cd frontend && npm install && npm run dev -- --host 127.0.0.1
```

Open <http://localhost:5173> in the phone browser, register, and you're in.

### 6. Want a real Android app?

Build the APK on a desktop with Android Studio + NDK (the `android` job in
`.github/workflows/release.yml` does exactly this), then sideload it. Mobile
builds talk to a backend you host; on-device offline scanning uses the in-process
Rust `native_scan` / `native_walk` commands.

---

## Smoke test (any platform)

In the web terminal, try:

```
calc.hex 255                 # a pure-compute module command
text.upper hello world       # string ops
? explain the TCP handshake  # streams an AI answer (needs an AI_PROVIDER + key)
scan 127.0.0.1 1 1024        # Rust port scan  (local mode + native binary)
walk .                       # Rust directory walk (local mode + native binary)
clear
```

## Troubleshooting

- **`uvicorn: command not found`** — activate the venv first, or run
  `python -m uvicorn backend.main:app`.
- **`alembic` can't find the app** — run it from inside `backend/`
  (`cd backend && alembic upgrade head`).
- **`scan.ports`/`fs.walk` say "binary not found"** — run `cargo build --release`
  in `native/`, or set `TERMAID_SCAN_BIN` / `TERMAID_WALK_BIN`.
- **Native commands missing entirely** — they only register in
  `DEPLOYMENT_MODE=local`; in `server` mode they're intentionally off.
- **Windows: scripts won't run** — `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
- **Termux: `cryptography` build fails** — ensure `pkg install python-cryptography`
  ran and the venv used `--system-site-packages`.
- **Tauri build fails on Linux** — install the `libwebkit2gtk-4.1-dev` group from
  step A.1.
