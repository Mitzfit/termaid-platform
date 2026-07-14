"""Bench Module — CPU, disk, and network micro-benchmarks.

All measurements are done in-process with the standard library — no
shelling out, so there's no command-construction/injection surface here
at all (the network test uses a raw `socket.connect` for TCP handshake
timing, not a `ping` subprocess). Read-only: writes one small temp file
for the disk test and removes it immediately after.

Commands (~4):
  /bench cpu               Pure-Python CPU loop benchmark (rough, relative)
  /bench disk [path]         Sequential write+read speed in a directory
  /bench net <host> [port]     TCP connect latency (default port 443)
  /bench explain                 How this module works
"""

import os
import socket
import tempfile
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_DISK_TEST_SIZE = 32 * 1024 * 1024  # 32MB


class BenchModule(Module):
    name = "bench"
    version = "1.0.0"
    description = "CPU, disk, and network micro-benchmarks"
    author = "termaid"

    def on_load(self):
        for cmd in ["cpu", "disk", "net", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_cpu(self, arg=""):
        """Pure-Python CPU loop benchmark (rough, relative — not a real FLOPS measure)"""
        start = time.perf_counter()
        total = 0
        for i in range(5_000_000):
            total += i * i % 97
        elapsed = time.perf_counter() - start
        ops_per_sec = 5_000_000 / elapsed
        return (f"[bench] CPU: 5,000,000 iterations in {elapsed:.3f}s "
                f"({ops_per_sec:,.0f} ops/sec)\n"
                f"  Rough and single-core only — compare runs on the same machine, "
                f"not across machines.")

    @safe
    def cmd_disk(self, arg=""):
        """Sequential write+read speed in a directory: /bench disk [path]"""
        target_dir = Path((arg or tempfile.gettempdir()).strip()).expanduser()
        if not target_dir.is_dir():
            return f"[bench] Not a directory: {target_dir}"
        test_file = target_dir / f".termaid_bench_{os.getpid()}.tmp"
        data = os.urandom(1024 * 1024)  # 1MB chunk, written repeatedly
        chunks = _DISK_TEST_SIZE // len(data)
        try:
            start = time.perf_counter()
            with test_file.open("wb") as f:
                for _ in range(chunks):
                    f.write(data)
                f.flush()
                os.fsync(f.fileno())
            write_elapsed = time.perf_counter() - start
            write_mbps = (_DISK_TEST_SIZE / (1024 * 1024)) / write_elapsed

            start = time.perf_counter()
            with test_file.open("rb") as f:
                while f.read(1024 * 1024):
                    pass
            read_elapsed = time.perf_counter() - start
            read_mbps = (_DISK_TEST_SIZE / (1024 * 1024)) / read_elapsed
        except Exception as e:
            return f"[bench] Disk test failed: {e}"
        finally:
            test_file.unlink(missing_ok=True)
        return (f"[bench] Disk ({target_dir}), {_DISK_TEST_SIZE // (1024*1024)}MB test file:\n"
                f"  Write: {write_mbps:.1f} MB/s\n"
                f"  Read:  {read_mbps:.1f} MB/s")

    @safe
    def cmd_net(self, arg=""):
        """TCP connect latency (default port 443): /bench net <host> [port]"""
        parts = (arg or "").split()
        if not parts:
            return "[bench] Usage: /bench net <host> [port]"
        host = parts[0]
        try:
            port = int(parts[1]) if len(parts) > 1 else 443
        except ValueError:
            return f"[bench] Invalid port: {parts[1]}"
        samples = []
        for _ in range(4):
            start = time.perf_counter()
            try:
                with socket.create_connection((host, port), timeout=3) as s:
                    pass
                samples.append((time.perf_counter() - start) * 1000)
            except Exception as e:
                return f"[bench] Could not connect to {host}:{port} — {e}"
        avg = sum(samples) / len(samples)
        return (f"[bench] TCP connect to {host}:{port} (4 samples):\n"
                f"  avg {avg:.1f}ms  min {min(samples):.1f}ms  max {max(samples):.1f}ms")

    @safe
    def cmd_explain(self, arg=""):
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{self.name}] {self.description}", "", "Commands:"]
            for c in cmds:
                lines.append(f"  /{self.name} {c}")
            return "\n".join(lines)
