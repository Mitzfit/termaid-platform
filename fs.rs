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
