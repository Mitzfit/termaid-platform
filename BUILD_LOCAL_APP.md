# Building the self-contained local app

This ties the Python backend, the Rust/Tauri shell, and the TypeScript UI into
one installable program that runs fully on-device — the answer to "I want it to
work as a local tool, on any desktop or mobile device."

## How it fits together

```
        ┌──────────── TermAId.app (one installable bundle) ───────────┐
        │                                                             │
        │   Tauri shell (Rust)                                        │
        │     ├─ loads the TypeScript UI (webview)                    │
        │     └─ on launch, spawns ↓                                  │
        │                                                             │
        │   termaid-backend  (PyInstaller-frozen FastAPI sidecar)     │
        │     ├─ DEPLOYMENT_MODE=local  → 94 modules / 1459 commands  │
        │     ├─ binds 127.0.0.1:8765  (never network-exposed)        │
        │     └─ bundles your termaid-cli source + all modules        │
        │                                                             │
        └─────────────────────────────────────────────────────────────┘
```

The UI talks to `http://127.0.0.1:8765`. With a local Ollama model set as
`AI_PROVIDER`, the whole thing works with no internet at all.

## Desktop build (Windows / macOS / Linux)

```bash
# 1. Freeze the backend into a single binary, named for Tauri
#    (Windows: use scripts\build_sidecar.ps1)
export TERMAID_ROOT=/path/to/termaid-complete-windows
scripts/build_sidecar.sh
#    → desktop-mobile/src-tauri/binaries/termaid-backend-<your-triple>

# 2. Build the native installer (also builds the TS frontend via beforeBuildCommand)
cd desktop-mobile
npm install
npm run build
#    → src-tauri/target/release/bundle/   (.msi / .dmg / .AppImage / .deb)
```

## Mobile note (important + honest)

Tauri 2 produces **real native iOS and Android apps** from this same UI:

```bash
cd desktop-mobile
npm run android:init && npm run android:build   # needs Android Studio + NDK
npm run ios:init && npm run ios:build           # needs Xcode (macOS only)
```

But bundling a **Python** runtime inside a phone app is impractical, so on
mobile the app does **not** spawn the sidecar (`lib.rs` gates `spawn_backend`
behind `#[cfg(desktop)]`). Mobile builds instead point at a backend you host
(set `VITE_API_BASE` to your server URL at build time). So:

- **Desktop** → fully self-contained, offline-capable, full local policy.
- **Mobile** → native app, talks to your hosted backend (server policy).

If you truly need an offline mobile engine later, the path is to port the
hot-path modules to Rust (you already have the `native/` crate pattern) and call
them directly from Tauri — no Python on the phone.

## CI does this for you

`.github/workflows/release.yml` runs the desktop matrix (3 OSes) + Android on a
version tag. The sidecar step is included but commented — uncomment it and make
your TermAId CLI source available in the workflow to ship the bundled-backend
desktop variant.
