// Desktop entry point. Mobile uses the #[tauri::mobile_entry_point] in lib.rs.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    termaid_lib::run()
}
