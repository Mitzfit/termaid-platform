// native_scan / native_walk wrap termaid_scan's in-process Rust implementations
// (native/src/lib.rs, native/src/fs.rs) so the desktop app can scan/walk
// without a Python backend running — the offline-mobile-capable path
// native.ts's isTauri() branch calls into. termaid_scan is intentionally
// dependency-free, so rather than adding serde there, we round-trip through
// its existing to_json() string into a serde_json::Value (serde_json is
// already part of this crate's own dependency graph via `tauri`).

#[tauri::command]
fn native_scan(host: String, start: u16, end: u16, timeout_ms: u64) -> Result<serde_json::Value, String> {
    let result = termaid_scan::scan(&host, start, end, timeout_ms);
    let json = termaid_scan::to_json(&result);
    serde_json::from_str(&json).map_err(|e| e.to_string())
}

#[tauri::command]
fn native_walk(path: String, top_n: usize) -> Result<serde_json::Value, String> {
    let result = termaid_scan::fs::walk(&path, top_n);
    let json = termaid_scan::fs::to_json(&result);
    serde_json::from_str(&json).map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
  tauri::Builder::default()
    .invoke_handler(tauri::generate_handler![native_scan, native_walk])
    .setup(|app| {
      if cfg!(debug_assertions) {
        app.handle().plugin(
          tauri_plugin_log::Builder::default()
            .level(log::LevelFilter::Info)
            .build(),
        )?;
      }
      Ok(())
    })
    .run(tauri::generate_context!())
    .expect("error while running tauri application");
}
