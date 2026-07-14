"""Native scanner wrapper tests — mock the binary so no Rust build is needed."""
import json
import subprocess
from types import SimpleNamespace

from backend import native


def test_format_scan_with_open_ports():
    result = {"host": "10.0.0.1", "open": [{"port": 22, "service": "ssh"},
                                           {"port": 443, "service": "https"}],
              "scanned": 1024, "ms": 12}
    out = native.format_scan(result)
    assert "10.0.0.1" in out and "ssh" in out and "https" in out
    assert "2 open" in out


def test_format_scan_no_ports():
    out = native.format_scan(
        {"host": "h", "open": [], "scanned": 100, "ms": 5})
    assert "no open ports" in out


def test_format_scan_error():
    assert native.format_scan({"error": "boom"}) == "[scan error] boom"


def test_scan_ports_parses_json(monkeypatch):
    payload = {"host": "127.0.0.1", "open": [{"port": 80, "service": "http"}],
               "scanned": 100, "ms": 3}

    monkeypatch.setattr(native, "scanner_path", lambda: "/fake/termaid-scan")
    monkeypatch.setattr(subprocess,
                        "run",
                        lambda *a,
                        **k: SimpleNamespace(returncode=0,
                                             stdout=json.dumps(payload),
                                             stderr=""),
                        )
    result = native.scan_ports("127.0.0.1", 1, 100)
    assert result["open"][0]["service"] == "http"


def test_scan_ports_missing_binary(monkeypatch):
    monkeypatch.setattr(native, "scanner_path", lambda: None)
    result = native.scan_ports("127.0.0.1")
    assert "error" in result and "not found" in result["error"]


def test_scan_ports_nonzero_exit(monkeypatch):
    monkeypatch.setattr(native, "scanner_path", lambda: "/fake/termaid-scan")
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=2, stdout="", stderr="bad args"),
    )
    result = native.scan_ports("127.0.0.1")
    assert result["error"] == "bad args"


def test_format_walk():
    result = {"root": "/tmp/x", "files": 3, "dirs": 1, "bytes": 2048,
              "largest": [{"path": "/tmp/x/big.bin", "bytes": 2000}], "ms": 7}
    out = native.format_walk(result)
    assert "/tmp/x" in out and "3 files" in out and "big.bin" in out


def test_walk_dir_parses_json(monkeypatch):
    payload = {"root": "/tmp", "files": 1, "dirs": 0, "bytes": 5,
               "largest": [{"path": "/tmp/a", "bytes": 5}], "ms": 1}
    monkeypatch.setattr(native, "walker_path", lambda: "/fake/termaid-walk")
    monkeypatch.setattr(subprocess,
                        "run",
                        lambda *a,
                        **k: SimpleNamespace(returncode=0,
                                             stdout=json.dumps(payload),
                                             stderr=""),
                        )
    r = native.walk_dir("/tmp", 10)
    assert r["files"] == 1 and r["largest"][0]["bytes"] == 5


def test_walk_dir_missing_binary(monkeypatch):
    monkeypatch.setattr(native, "walker_path", lambda: None)
    r = native.walk_dir("/tmp")
    assert "error" in r and "not found" in r["error"]


def test_human_readable_sizes():
    assert native._human(0) == "0B"
    assert native._human(1024) == "1.0KB"
    assert native._human(1048576) == "1.0MB"
