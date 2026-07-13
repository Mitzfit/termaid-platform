//! TermAId Tauri shell.
//!
//! This compiles the TypeScript web UI into a native app for **all** targets:
//! Windows / macOS / Linux desktops AND iOS / Android phones — one codebase.
//!
//! Two backend strategies, chosen at runtime:
//!   • LOCAL  — spawn the bundled Python backend as a sidecar on 127.0.0.1.
//!              The device is the trusted operator, so policy.py runs in
//!              "local" mode. Works fully offline (with a local Ollama model).
//!   • SERVER — skip the sidecar and point the UI at a remote URL.
//!
//! It also exposes a couple of *native* commands implemented in Rust — the
//! "drop to Rust when Python is too slow" path. `native_sha256` is a tiny,
//! honest example; the same pattern hosts a real fast port-scanner or file
//! walker later.

use serde::Serialize;
use sha2::{Digest, Sha256};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;

#[derive(Serialize)]
struct Hashed {
    algo: String,
    hex: String,
}

/// Native SHA-256 — callable from the UI via `invoke("native_sha256", { input })`.
#[tauri::command]
fn native_sha256(input: String) -> Hashed {
    let mut hasher = Sha256::new();
    hasher.update(input.as_bytes());
    Hashed {
        algo: "sha256".into(),
        hex: format!("{:x}", hasher.finalize()),
    }
}

/// Report which platform the app is running on (handy for UI tweaks).
#[tauri::command]
fn platform() -> String {
    std::env::consts::OS.to_string()
}

#[derive(Serialize)]
struct ScanPort {
    port: u16,
    service: String,
}

#[derive(Serialize)]
struct ScanOut {
    host: String,
    open: Vec<ScanPort>,
    scanned: usize,
    ms: u128,
}

/// In-process port scan — the SAME Rust code the Python sidecar uses, but called
/// directly. This is the offline-mobile path: on a phone there's no Python, so
/// the UI invokes this command and the scan runs natively in the app.
#[tauri::command]
fn native_scan(host: String, start: u16, end: u16, timeout_ms: u64) -> ScanOut {
    let r = termaid_scan::scan(&host, start, end, timeout_ms);
    ScanOut {
        host: r.host,
        open: r
            .open
            .into_iter()
            .map(|p| ScanPort { port: p.port, service: p.service.to_string() })
            .collect(),
        scanned: r.scanned,
        ms: r.ms,
    }
}

#[derive(Serialize)]
struct LargeFile {
    path: String,
    bytes: u64,
}

#[derive(Serialize)]
struct WalkOut {
    root: String,
    files: usize,
    dirs: usize,
    bytes: u64,
    largest: Vec<LargeFile>,
    ms: u128,
}

/// In-process directory walk — the second ported module, offline-capable.
#[tauri::command]
fn native_walk(path: String, top_n: usize) -> WalkOut {
    let r = termaid_scan::fs::walk(&path, top_n);
    WalkOut {
        root: r.root,
        files: r.files,
        dirs: r.dirs,
        bytes: r.bytes,
        largest: r
            .largest
            .into_iter()
            .map(|(path, bytes)| LargeFile { path, bytes })
            .collect(),
        ms: r.ms,
    }
}

/// Spawn the bundled Python backend (PyInstaller sidecar) on 127.0.0.1.
/// The sidecar prints "TERMAID_SIDECAR_READY <url>"; we forward its output to
/// the Tauri log so failures are visible. If the sidecar isn't bundled (e.g. a
/// dev build pointing at a remote backend), this fails gracefully.
fn spawn_backend(app: &tauri::App) {
    let shell = app.shell();
    match shell.sidecar("termaid-backend") {
        Ok(cmd) => match cmd.spawn() {
            Ok((mut rx, _child)) => {
                tauri::async_runtime::spawn(async move {
                    while let Some(event) = rx.recv().await {
                        if let CommandEvent::Stdout(line) = event {
                            let text = String::from_utf8_lossy(&line);
                            println!("[backend] {text}");
                        }
                    }
                });
            }
            Err(e) => eprintln!("[backend] sidecar spawn failed: {e}"),
        },
        Err(e) => eprintln!("[backend] no bundled sidecar ({e}); using remote backend"),
    }
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .invoke_handler(tauri::generate_handler![native_sha256, platform, native_scan, native_walk])
        .setup(|app| {
            // Local mode: bring up the on-device backend. Desktop only — on
            // mobile, bundling a Python runtime is impractical, so mobile builds
            // talk to a remote backend instead.
            #[cfg(desktop)]
            spawn_backend(app);
            let _ = app; // silence unused warning on mobile
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running TermAId");
}
