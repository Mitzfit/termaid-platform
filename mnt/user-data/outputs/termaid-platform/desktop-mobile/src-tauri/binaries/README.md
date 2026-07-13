# Sidecar binaries

Tauri looks here for the bundled backend, named with the Rust **target triple**:

    termaid-backend-x86_64-pc-windows-msvc.exe
    termaid-backend-aarch64-apple-darwin
    termaid-backend-x86_64-unknown-linux-gnu

Build it with `scripts/build_sidecar.*`, which runs PyInstaller and copies the
correctly-named binary in here. This directory is gitignored except for this
README — sidecars are build artifacts.
