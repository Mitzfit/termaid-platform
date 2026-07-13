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
