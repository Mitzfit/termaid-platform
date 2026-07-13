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
