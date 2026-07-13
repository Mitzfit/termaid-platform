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
