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
