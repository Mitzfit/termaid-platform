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
