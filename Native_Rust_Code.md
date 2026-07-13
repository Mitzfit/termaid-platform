# Agent 07 — Native / Rust Performance: OWNED SOURCE CODE

Hand edits back as .rs/.toml text. Keep cargo build/test/clippy green.

## `native/Cargo.toml`

```toml
[package]
name = "termaid-scan"
version = "0.1.0"
edition = "2021"
description = "Native fast-ops for TermAId: concurrent TCP port scan (netscan) + recursive directory walk (fsscan). Usable as CLI sidecars or as a library (Tauri, incl. mobile)."

# No external dependencies on purpose: compiles on any Rust toolchain, offline.
[dependencies]

[lib]
name = "termaid_scan"
path = "src/lib.rs"

[[bin]]
name = "termaid-scan"
path = "src/main.rs"

[[bin]]
name = "termaid-walk"
path = "src/bin/termaid-walk.rs"

[profile.release]
opt-level = 3
lto = true

```

## `native/src/lib.rs`

```rust
//! termaid_scan — fast concurrent TCP port scanning.
//!
//! This is the Rust port of `netscan`'s slow part. Pure `std`, no dependencies,
//! so it compiles anywhere and runs both as:
//!   • a CLI binary the Python backend shells out to (desktop local mode), and
//!   • an in-process library the Tauri app calls directly (incl. on mobile,
//!     where there is no Python runtime — this is the offline-mobile path).

pub mod fs;

use std::net::{TcpStream, ToSocketAddrs};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
pub struct OpenPort {
    pub port: u16,
    pub service: &'static str,
}

#[derive(Debug, Clone)]
pub struct ScanResult {
    pub host: String,
    pub open: Vec<OpenPort>,
    pub scanned: usize,
    pub ms: u128,
}

/// Well-known service names for common ports (the bit `netscan` annotates).
pub fn service_name(port: u16) -> &'static str {
    match port {
        21 => "ftp",
        22 => "ssh",
        23 => "telnet",
        25 => "smtp",
        53 => "dns",
        80 => "http",
        110 => "pop3",
        143 => "imap",
        443 => "https",
        445 => "smb",
        587 => "smtp-submission",
        3306 => "mysql",
        3389 => "rdp",
        5432 => "postgresql",
        5900 => "vnc",
        6379 => "redis",
        8000 | 8080 => "http-alt",
        8443 => "https-alt",
        9200 => "elasticsearch",
        11434 => "ollama",
        27017 => "mongodb",
        _ => "unknown",
    }
}

/// Scan `host` over the inclusive port range with a per-port connect timeout.
/// Uses a bounded thread pool so even a /16 of ports stays fast and predictable.
pub fn scan(host: &str, start: u16, end: u16, timeout_ms: u64) -> ScanResult {
    assert!(start <= end, "start port must be <= end port");
    let t0 = Instant::now();
    let total = (end - start + 1) as usize;

    let workers = 128usize;
    let chunk = (total / workers).max(1);
    let timeout = Duration::from_millis(timeout_ms);

    let (tx, rx) = mpsc::channel::<u16>();
    let mut handles = Vec::new();
    let mut p = start;
    loop {
        let lo = p;
        let hi = ((p as usize + chunk - 1).min(end as usize)) as u16;
        let host = host.to_string();
        let tx = tx.clone();
        handles.push(thread::spawn(move || {
            for port in lo..=hi {
                if is_open(&host, port, timeout) {
                    let _ = tx.send(port);
                }
            }
        }));
        if hi >= end {
            break;
        }
        p = hi + 1;
    }
    drop(tx);

    let mut ports: Vec<u16> = rx.iter().collect();
    for h in handles {
        let _ = h.join();
    }
    ports.sort_unstable();

    let open = ports
        .into_iter()
        .map(|port| OpenPort {
            port,
            service: service_name(port),
        })
        .collect();

    ScanResult {
        host: host.to_string(),
        open,
        scanned: total,
        ms: t0.elapsed().as_millis(),
    }
}

fn is_open(host: &str, port: u16, timeout: Duration) -> bool {
    let addr = format!("{host}:{port}");
    match addr.to_socket_addrs() {
        Ok(mut addrs) => match addrs.next() {
            Some(sock) => TcpStream::connect_timeout(&sock, timeout).is_ok(),
            None => false,
        },
        Err(_) => false,
    }
}

/// Serialise a result to JSON by hand (keeps the crate dependency-free).
pub fn to_json(r: &ScanResult) -> String {
    let ports: Vec<String> = r
        .open
        .iter()
        .map(|p| format!("{{\"port\":{},\"service\":\"{}\"}}", p.port, p.service))
        .collect();
    format!(
        "{{\"host\":\"{}\",\"open\":[{}],\"scanned\":{},\"ms\":{}}}",
        r.host,
        ports.join(","),
        r.scanned,
        r.ms
    )
}

```

## `native/src/fs.rs`

```rust
//! termaid_scan::fs — fast recursive directory walking.
//!
//! The second module ported from Python (`fsscan`). An iterative, allocation-
//! light walk that reports file/dir counts, total bytes, and the largest files
//! — the kind of summary `fsscan` produces, but without Python's per-entry
//! object overhead. Pure `std`, no dependencies, same three transports as the
//! scanner (CLI sidecar, /api/exec, in-process Tauri).

use std::fs;
use std::path::PathBuf;
use std::time::Instant;

#[derive(Debug, Clone)]
pub struct WalkResult {
    pub root: String,
    pub files: usize,
    pub dirs: usize,
    pub bytes: u64,
    /// (path, size) for the largest files, biggest first.
    pub largest: Vec<(String, u64)>,
    pub ms: u128,
}

/// Walk `root` recursively. `top_n` controls how many largest files to keep.
/// Symlinks are not followed (avoids cycles). Unreadable entries are skipped.
pub fn walk(root: &str, top_n: usize) -> WalkResult {
    let t0 = Instant::now();
    let mut files = 0usize;
    let mut dirs = 0usize;
    let mut bytes = 0u64;
    let mut largest: Vec<(String, u64)> = Vec::new();

    let mut stack: Vec<PathBuf> = vec![PathBuf::from(root)];
    while let Some(dir) = stack.pop() {
        let entries = match fs::read_dir(&dir) {
            Ok(e) => e,
            Err(_) => continue, // permission denied etc. — skip
        };
        for entry in entries.flatten() {
            let path = entry.path();
            let meta = match entry.metadata() {
                Ok(m) => m,
                Err(_) => continue,
            };
            if meta.file_type().is_symlink() {
                continue;
            }
            if meta.is_dir() {
                dirs += 1;
                stack.push(path);
            } else if meta.is_file() {
                files += 1;
                let size = meta.len();
                bytes += size;
                track_largest(&mut largest, path.to_string_lossy().into_owned(), size, top_n);
            }
        }
    }

    largest.sort_by(|a, b| b.1.cmp(&a.1));
    WalkResult {
        root: root.to_string(),
        files,
        dirs,
        bytes,
        largest,
        ms: t0.elapsed().as_millis(),
    }
}

fn track_largest(top: &mut Vec<(String, u64)>, path: String, size: u64, n: usize) {
    if n == 0 {
        return;
    }
    if top.len() < n {
        top.push((path, size));
        return;
    }
    // Replace the current smallest if this one is bigger.
    if let Some((idx, _)) = top
        .iter()
        .enumerate()
        .min_by(|a, b| a.1 .1.cmp(&b.1 .1))
    {
        if size > top[idx].1 {
            top[idx] = (path, size);
        }
    }
}

pub fn to_json(r: &WalkResult) -> String {
    let largest: Vec<String> = r
        .largest
        .iter()
        .map(|(p, s)| format!("{{\"path\":{},\"bytes\":{}}}", json_str(p), s))
        .collect();
    format!(
        "{{\"root\":{},\"files\":{},\"dirs\":{},\"bytes\":{},\"largest\":[{}],\"ms\":{}}}",
        json_str(&r.root),
        r.files,
        r.dirs,
        r.bytes,
        largest.join(","),
        r.ms
    )
}

/// Minimal JSON string escaper (paths can contain quotes/backslashes).
fn json_str(s: &str) -> String {
    let mut out = String::with_capacity(s.len() + 2);
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            _ => out.push(c),
        }
    }
    out.push('"');
    out
}

```

## `native/src/main.rs`

```rust
//! termaid-scan CLI — thin wrapper over the library. Emits JSON on stdout so
//! the Python backend can parse it.
//!
//! Usage: termaid-scan <host> [start_port] [end_port] [timeout_ms]

use std::env;
use termaid_scan::{scan, to_json};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: termaid-scan <host> [start_port] [end_port] [timeout_ms]");
        std::process::exit(2);
    }
    let host = &args[1];
    let start: u16 = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(1);
    let end: u16 = args.get(3).and_then(|s| s.parse().ok()).unwrap_or(1024);
    let timeout: u64 = args.get(4).and_then(|s| s.parse().ok()).unwrap_or(300);

    if start > end {
        eprintln!("error: start_port must be <= end_port");
        std::process::exit(2);
    }
    let result = scan(host, start, end, timeout);
    println!("{}", to_json(&result));
}

```

## `native/src/bin/termaid-walk.rs`

```rust
//! termaid-walk CLI — fast directory walk, JSON on stdout.
//! Usage: termaid-walk <path> [top_n]

use std::env;
use termaid_scan::fs::{to_json, walk};

fn main() {
    let args: Vec<String> = env::args().collect();
    if args.len() < 2 {
        eprintln!("usage: termaid-walk <path> [top_n]");
        std::process::exit(2);
    }
    let root = &args[1];
    let top_n: usize = args.get(2).and_then(|s| s.parse().ok()).unwrap_or(10);
    println!("{}", to_json(&walk(root, top_n)));
}

```

## `native/tests/scan_test.rs`

```rust
//! Integration tests — bind a real listener on an ephemeral port and confirm
//! the scanner detects it. Pure std, runs offline in CI.

use std::net::TcpListener;
use termaid_scan::{scan, service_name};

#[test]
fn detects_an_open_port() {
    let listener = TcpListener::bind("127.0.0.1:0").expect("bind");
    let port = listener.local_addr().unwrap().port();

    let result = scan("127.0.0.1", port, port, 500);
    assert_eq!(result.scanned, 1);
    assert_eq!(result.open.len(), 1);
    assert_eq!(result.open[0].port, port);
}

#[test]
fn closed_ports_report_nothing() {
    // Pick a port we then drop so it's almost certainly closed.
    let port = {
        let l = TcpListener::bind("127.0.0.1:0").unwrap();
        l.local_addr().unwrap().port()
    }; // listener dropped here
    let result = scan("127.0.0.1", port, port, 200);
    assert_eq!(result.open.len(), 0);
}

#[test]
fn known_services_are_named() {
    assert_eq!(service_name(22), "ssh");
    assert_eq!(service_name(443), "https");
    assert_eq!(service_name(11434), "ollama");
    assert_eq!(service_name(12345), "unknown");
}

#[test]
fn json_shape_is_stable() {
    let r = scan("127.0.0.1", 1, 1, 50);
    let json = termaid_scan::to_json(&r);
    assert!(json.starts_with("{\"host\":\"127.0.0.1\""));
    assert!(json.contains("\"scanned\":1"));
}

```

## `native/tests/fs_test.rs`

```rust
//! Walk tests — build a known temp tree and verify counts/sizes. Offline.

use std::fs;
use std::env;
use termaid_scan::fs::walk;

#[test]
fn walks_a_known_tree() {
    let base = env::temp_dir().join(format!("termaid_walk_test_{}", std::process::id()));
    let sub = base.join("sub");
    fs::create_dir_all(&sub).unwrap();
    fs::write(base.join("a.txt"), b"hello").unwrap();       // 5 bytes
    fs::write(sub.join("b.bin"), vec![0u8; 1000]).unwrap(); // 1000 bytes

    let r = walk(base.to_str().unwrap(), 5);
    assert_eq!(r.files, 2);
    assert!(r.dirs >= 1);
    assert_eq!(r.bytes, 1005);
    assert_eq!(r.largest[0].1, 1000); // biggest first

    fs::remove_dir_all(&base).ok();
}

#[test]
fn missing_path_is_empty_not_panic() {
    let r = walk("/no/such/path/termaid", 5);
    assert_eq!(r.files, 0);
    assert_eq!(r.bytes, 0);
}

```

## `desktop-mobile/src-tauri/src/lib.rs  (SHARED edge with Agent 09)`

```rust
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

```
