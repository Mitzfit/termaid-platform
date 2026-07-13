# Agent 06 — Networking & Scanning: OWNED SOURCE CODE

Hand edits back as .py text. The Rust scanner crate is Agent 07's — coordinate, don't fork.

## `backend/native.py`

```python
"""
native.py — bridge from Python to the Rust `termaid-scan` binary.

This is the "we ported the slow part to Rust" integration. The backend shells
out to the compiled scanner and parses its JSON. Locating the binary:
  1. TERMAID_SCAN_BIN env var (explicit)
  2. native/target/release/termaid-scan (dev build)
  3. on PATH (installed)

Scanning is a network action, so the caller (main.py) only registers it in
LOCAL mode — never exposed to arbitrary users on a server.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path


def scanner_path() -> str | None:
    return _bin_path("termaid-scan", "TERMAID_SCAN_BIN")


def walker_path() -> str | None:
    return _bin_path("termaid-walk", "TERMAID_WALK_BIN")


def _bin_path(name: str, env_var: str) -> str | None:
    env = os.environ.get(env_var)
    if env and Path(env).exists():
        return env
    exe = f"{name}.exe" if os.name == "nt" else name
    dev = Path(__file__).resolve().parents[1] / "native" / "target" / "release" / exe
    if dev.exists():
        return str(dev)
    return shutil.which(name)


def is_available() -> bool:
    return scanner_path() is not None


def scan_ports(host: str, start: int = 1, end: int = 1024, timeout_ms: int = 300) -> dict:
    """Run the Rust scanner; return parsed JSON or an error dict."""
    binary = scanner_path()
    if not binary:
        return {"error": "termaid-scan binary not found — build it: "
                         "cd native && cargo build --release"}
    try:
        proc = subprocess.run(
            [binary, host, str(start), str(end), str(timeout_ms)],
            capture_output=True, text=True, timeout=120,
        )
    except subprocess.TimeoutExpired:
        return {"error": "scan timed out"}
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or f"scanner exited {proc.returncode}"}
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"error": f"unparseable scanner output: {proc.stdout[:200]}"}


def format_scan(result: dict) -> str:
    """Human-readable rendering for the terminal (engine commands return str)."""
    if "error" in result:
        return f"[scan error] {result['error']}"
    host = result.get("host", "?")
    open_ports = result.get("open", [])
    if not open_ports:
        return (f"[netscan/rust] {host}: no open ports in "
                f"{result.get('scanned', 0)} scanned ({result.get('ms', 0)}ms)")
    lines = [f"[netscan/rust] {host} — {len(open_ports)} open "
             f"of {result.get('scanned', 0)} scanned ({result.get('ms', 0)}ms):"]
    for p in open_ports:
        lines.append(f"  {p['port']:>5}/tcp  {p['service']}")
    return "\n".join(lines)


def walk_dir(path: str, top_n: int = 10) -> dict:
    """Run the Rust directory walker; return parsed JSON or an error dict."""
    binary = walker_path()
    if not binary:
        return {"error": "termaid-walk binary not found — build it: "
                         "cd native && cargo build --release"}
    try:
        proc = subprocess.run(
            [binary, path, str(top_n)],
            capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {"error": "walk timed out"}
    if proc.returncode != 0:
        return {"error": proc.stderr.strip() or f"walker exited {proc.returncode}"}
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"error": f"unparseable walker output: {proc.stdout[:200]}"}


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


def format_walk(result: dict) -> str:
    if "error" in result:
        return f"[walk error] {result['error']}"
    lines = [f"[fsscan/rust] {result.get('root', '?')} — "
             f"{result.get('files', 0)} files, {result.get('dirs', 0)} dirs, "
             f"{_human(result.get('bytes', 0))} total ({result.get('ms', 0)}ms)"]
    largest = result.get("largest", [])
    if largest:
        lines.append("  largest:")
        for item in largest:
            lines.append(f"    {_human(item['bytes']):>9}  {item['path']}")
    return "\n".join(lines)

```

## `backend/tests/test_native.py`

```python
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
    out = native.format_scan({"host": "h", "open": [], "scanned": 100, "ms": 5})
    assert "no open ports" in out


def test_format_scan_error():
    assert native.format_scan({"error": "boom"}) == "[scan error] boom"


def test_scan_ports_parses_json(monkeypatch):
    payload = {"host": "127.0.0.1", "open": [{"port": 80, "service": "http"}],
               "scanned": 100, "ms": 3}

    monkeypatch.setattr(native, "scanner_path", lambda: "/fake/termaid-scan")
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
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
    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""),
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

```

## `modules/netscan/__init__.py`

```python
"""NetScan Module — Network analysis, threats, and effectiveness assessment.

Provides:
- Detailed network interface overview
- DNS and gateway analysis
- Open port scanning (local + common services)
- Network speed and latency testing
- Threat detection (suspicious connections, weak configs)
- Actionable recommendations

Works cross-platform: Windows, Linux, macOS, Termux.
"""

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class NetScanModule(Module):
    name = "net"
    version = "1.0.0"
    description = "Network overview, threat assessment, and effectiveness scoring"
    author = "termaid"

    def on_load(self):
        for cmd in ["overview", "interfaces", "connections", "ports",
                    "scan", "dns", "gateway", "speed", "threats",
                    "score", "public_ip", "report", "watch", "listening"]:
            method = cmd.replace("-", "_")
            self.register_command(cmd, getattr(self, f"cmd_{method}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "network"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _run(self, cmd, timeout: int = 10):
        """v3.10: avoid shell=True. cmd can be str (split via shlex) or list."""
        try:
            if sys.platform == "win32":
                if isinstance(cmd, list):
                    cmd_str = " ".join(cmd)
                else:
                    cmd_str = cmd
                r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd_str],
                                   capture_output=True, text=True, timeout=timeout,
                                   encoding="utf-8", errors="replace")
            else:
                import shlex
                args = cmd if isinstance(cmd, list) else shlex.split(cmd)
                r = subprocess.run(args, capture_output=True, text=True,
                                   timeout=timeout, encoding="utf-8", errors="replace")
            return r
        except Exception:
            return subprocess.CompletedProcess(cmd, 1, "", "")

    # === OVERVIEW ===

    @safe
    def cmd_overview(self, args):
        """High-level network overview. Usage: /net.overview"""
        lines = ["=" * 55, "  🌐 NETWORK OVERVIEW", "=" * 55]

        # Interfaces summary
        lines.append("\n--- Interfaces ---")
        interfaces = self._get_interfaces()
        active = [i for i in interfaces if i.get("status") == "up"]
        lines.append(f"  Total:   {len(interfaces)}")
        lines.append(f"  Active:  {len(active)}")
        for iface in active[:5]:
            lines.append(f"  • {iface.get('name', '?'):15s} {iface.get('ip', '?'):15s}")

        # Gateway
        lines.append("\n--- Gateway ---")
        gw = self._get_gateway()
        lines.append(f"  Default: {gw.get('gateway', 'unknown')}")
        if gw.get("latency"):
            lines.append(f"  Latency: {gw['latency']:.1f} ms")

        # DNS
        lines.append("\n--- DNS ---")
        dns = self._get_dns_servers()
        for d in dns[:3]:
            lines.append(f"  Server: {d}")

        # Public IP
        lines.append("\n--- External ---")
        pub = self._get_public_ip()
        lines.append(f"  Public IP: {pub.get('ip', 'unavailable')}")
        if pub.get("country"):
            lines.append(f"  Location:  {pub.get('city', '?')}, {pub.get('country', '?')}")
            lines.append(f"  ISP:       {pub.get('isp', 'unknown')}")

        # Active connections
        lines.append("\n--- Activity ---")
        conns = self._count_connections()
        lines.append(f"  Open connections: {conns.get('total', 0)}")
        lines.append(f"  Listening ports:  {conns.get('listening', 0)}")

        return "\n".join(lines)

    # === INTERFACES ===

    @safe
    def cmd_interfaces(self, args):
        """List network interfaces. Usage: /net.interfaces"""
        lines = ["=== 🔌 Interfaces ===\n"]
        for iface in self._get_interfaces():
            status_icon = "🟢" if iface.get("status") == "up" else "⚫"
            lines.append(f"  {status_icon} {iface.get('name', '?')}")
            if iface.get("ip"):
                lines.append(f"       IP:     {iface['ip']}")
            if iface.get("mac"):
                lines.append(f"       MAC:    {iface['mac']}")
            if iface.get("mtu"):
                lines.append(f"       MTU:    {iface['mtu']}")
        return "\n".join(lines)

    def _get_interfaces(self) -> list:
        """Cross-platform interface listing."""
        interfaces = []
        try:
            if sys.platform == "win32":
                r = self._run(
                    "Get-NetAdapter | Select-Object Name,Status,MacAddress,LinkSpeed | ConvertTo-Json"
                )
                if r.stdout:
                    data = json.loads(r.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for d in data or []:
                        ip = self._get_ip_for_iface(d.get("Name", ""))
                        interfaces.append({
                            "name": d.get("Name", ""),
                            "status": "up" if d.get("Status") == "Up" else "down",
                            "mac": d.get("MacAddress", ""),
                            "ip": ip,
                        })
            else:
                # Try `ip` first, fall back to ifconfig
                r = self._run("ip -j addr show 2>/dev/null")
                if r.stdout.strip():
                    try:
                        data = json.loads(r.stdout)
                        for d in data:
                            addr_info = d.get("addr_info", [])
                            ipv4 = next((a["local"] for a in addr_info
                                         if a.get("family") == "inet"), "")
                            interfaces.append({
                                "name": d.get("ifname", ""),
                                "status": "up" if "UP" in d.get("flags", []) else "down",
                                "mac": d.get("address", ""),
                                "ip": ipv4,
                                "mtu": d.get("mtu", ""),
                            })
                    except json.JSONDecodeError:
                        pass

                if not interfaces:
                    r = self._run("ifconfig 2>/dev/null")
                    if r.stdout.strip():
                        current = None
                        for line in r.stdout.splitlines():
                            if line and not line.startswith(" ") and not line.startswith("\t"):
                                name = line.split(":")[0].split()[0]
                                current = {"name": name, "status": "up" if "UP" in line else "down"}
                                interfaces.append(current)
                            elif current:
                                m = re.search(r"inet\s+(?:addr:)?(\d+\.\d+\.\d+\.\d+)", line)
                                if m:
                                    current["ip"] = m.group(1)
                                m = re.search(r"(?:ether|HWaddr)\s+([0-9a-f:]{17})", line, re.I)
                                if m:
                                    current["mac"] = m.group(1)
        except Exception:
            pass
        return interfaces

    def _get_ip_for_iface(self, name: str) -> str:
        """Get IPv4 for a Windows interface."""
        if sys.platform != "win32" or not name:
            return ""
        r = self._run(
            f"Get-NetIPAddress -InterfaceAlias '{name}' -AddressFamily IPv4 "
            f"-ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty IPAddress"
        )
        return r.stdout.strip()

    # === CONNECTIONS ===

    @safe
    def cmd_connections(self, args):
        """Active network connections. Usage: /net.connections"""
        lines = ["=== 🔗 Active Connections ===\n"]
        if sys.platform == "win32":
            r = self._run(
                "Get-NetTCPConnection -State Established | "
                "Select-Object -First 30 LocalAddress,LocalPort,RemoteAddress,RemotePort,OwningProcess | "
                "Format-Table -AutoSize"
            )
            lines.append(r.stdout.strip()[:3000])
        else:
            r = self._run("ss -tunap 2>/dev/null || netstat -tunap 2>/dev/null")
            output = r.stdout.strip()
            if output:
                # Limit output
                for line in output.splitlines()[:40]:
                    lines.append(f"  {line}")
            else:
                lines.append("  Unable to list (needs root?)")
        return "\n".join(lines)

    @safe
    def cmd_listening(self, args):
        """Listening ports. Usage: /net.listening"""
        lines = ["=== 👂 Listening Ports ===\n"]
        if sys.platform == "win32":
            r = self._run(
                "Get-NetTCPConnection -State Listen | "
                "Select-Object LocalAddress,LocalPort,OwningProcess | "
                "Sort-Object LocalPort | Format-Table -AutoSize"
            )
            lines.append(r.stdout.strip()[:3000])
        else:
            r = self._run("ss -tlnp 2>/dev/null || netstat -tlnp 2>/dev/null")
            lines.append(r.stdout.strip()[:3000])
        return "\n".join(lines)

    def _count_connections(self) -> dict:
        result = {"total": 0, "listening": 0}
        try:
            if sys.platform == "win32":
                r = self._run("(Get-NetTCPConnection).Count")
                try: result["total"] = int(r.stdout.strip())
                except Exception: pass
                r = self._run("(Get-NetTCPConnection -State Listen).Count")
                try: result["listening"] = int(r.stdout.strip())
                except Exception: pass
            else:
                r = self._run("ss -tun 2>/dev/null | wc -l")
                try: result["total"] = max(0, int(r.stdout.strip()) - 1)
                except Exception: pass
                r = self._run("ss -tln 2>/dev/null | wc -l")
                try: result["listening"] = max(0, int(r.stdout.strip()) - 1)
                except Exception: pass
        except Exception:
            pass
        return result

    # === PORTS ===

    @safe
    def cmd_ports(self, args):
        """Scan common ports on a host. Usage: /net.ports <host>"""
        if not args.strip():
            return "Usage: /net.ports <host>\nExample: /net.ports 192.168.1.1"
        host = args.strip()
        common_ports = {
            20: "FTP-data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
            53: "DNS", 80: "HTTP", 110: "POP3", 135: "RPC", 139: "NetBIOS",
            143: "IMAP", 443: "HTTPS", 445: "SMB", 3306: "MySQL", 3389: "RDP",
            5432: "PostgreSQL", 5900: "VNC", 6379: "Redis", 8080: "HTTP-alt",
            8443: "HTTPS-alt", 27017: "MongoDB",
        }

        lines = [f"=== 🎯 Port scan: {host} ===\n"]
        open_ports = []
        for port, name in common_ports.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex((host, port))
                s.close()
                if result == 0:
                    open_ports.append((port, name))
                    lines.append(f"  🟢 {port:5d}/tcp  OPEN   ({name})")
            except Exception:
                pass

        if not open_ports:
            lines.append("  No common ports open, or host unreachable")
        else:
            lines.append(f"\n  Found {len(open_ports)} open port(s)")
        return "\n".join(lines)

    @safe
    def cmd_scan(self, args):
        """Scan local subnet. Usage: /net.scan [subnet]"""
        subnet = args.strip() if args.strip() else self._get_local_subnet()
        if not subnet:
            return "Could not detect local subnet. Usage: /net.scan 192.168.1.0/24"

        lines = [f"=== 🔍 Subnet scan: {subnet} ===\n"]

        # Try nmap first (fastest)
        import shutil
        if shutil.which("nmap"):
            print("Running nmap quick scan...")
            r = self._run(f"nmap -sn -T4 {subnet} 2>&1", timeout=60)
            if r.stdout.strip():
                for line in r.stdout.splitlines():
                    if "Nmap scan report" in line or "Host is up" in line:
                        lines.append(f"  {line.strip()}")
            return "\n".join(lines)

        # Fallback: simple ping sweep
        lines.append("  (nmap not installed - using ping sweep)")
        base = subnet.rsplit(".", 1)[0] if "." in subnet else subnet
        hosts_up = []
        for i in range(1, 20):
            target = f"{base}.{i}"
            if self._ping(target, timeout=0.5):
                hosts_up.append(target)
                lines.append(f"  🟢 {target}")
        if not hosts_up:
            lines.append("  No hosts responding")
        return "\n".join(lines)

    def _get_local_subnet(self) -> str:
        for iface in self._get_interfaces():
            ip = iface.get("ip", "")
            if ip and ip != "127.0.0.1" and not ip.startswith("169.254"):
                parts = ip.split(".")
                if len(parts) == 4:
                    return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        return ""

    def _ping(self, host: str, timeout: float = 1.0) -> bool:
        flag = "-n" if sys.platform == "win32" else "-c"
        wait = "-w" if sys.platform == "win32" else "-W"
        try:
            r = subprocess.run(
                ["ping", flag, "1", wait, str(int(timeout * 1000 if sys.platform == "win32" else timeout)), host],
                capture_output=True, timeout=timeout + 1,
            )
            return r.returncode == 0
        except Exception:
            return False

    # === DNS / GATEWAY ===

    @safe
    def cmd_dns(self, args):
        """DNS analysis. Usage: /net.dns [hostname]"""
        lines = ["=== 🔎 DNS ===\n"]
        servers = self._get_dns_servers()
        lines.append("Resolvers:")
        for s in servers:
            lines.append(f"  • {s}")

        if args.strip():
            host = args.strip()
            lines.append(f"\nResolving '{host}'...")
            try:
                start = time.time()
                ips = socket.getaddrinfo(host, None)
                elapsed = (time.time() - start) * 1000
                unique_ips = {i[4][0] for i in ips}
                lines.append(f"  Time: {elapsed:.1f} ms")
                for ip in unique_ips:
                    lines.append(f"  → {ip}")
            except Exception as e:
                lines.append(f"  Error: {e}")
        return "\n".join(lines)

    def _get_dns_servers(self) -> list:
        servers = []
        try:
            if sys.platform == "win32":
                r = self._run(
                    "Get-DnsClientServerAddress -AddressFamily IPv4 | "
                    "Select-Object -ExpandProperty ServerAddresses"
                )
                for line in r.stdout.splitlines():
                    line = line.strip()
                    if line and re.match(r"\d+\.\d+\.\d+\.\d+", line):
                        servers.append(line)
            else:
                if Path("/etc/resolv.conf").exists():
                    for line in Path("/etc/resolv.conf").read_text().splitlines():
                        if line.startswith("nameserver"):
                            parts = line.split()
                            if len(parts) >= 2:
                                servers.append(parts[1])
        except Exception:
            pass
        return list(dict.fromkeys(servers))  # dedupe

    @safe
    def cmd_gateway(self, args):
        """Default gateway info. Usage: /net.gateway"""
        lines = ["=== 🚪 Gateway ===\n"]
        gw = self._get_gateway()
        if gw.get("gateway"):
            lines.append(f"  Address:  {gw['gateway']}")
            if gw.get("latency"):
                lines.append(f"  Latency:  {gw['latency']:.1f} ms")
            # ARP info
            if sys.platform == "win32":
                r = self._run(f"Get-NetNeighbor -IPAddress {gw['gateway']} -ErrorAction SilentlyContinue | Format-List")
                if r.stdout.strip():
                    lines.append(f"\n{r.stdout.strip()}")
            else:
                r = self._run(f"ip neigh show {gw['gateway']} 2>/dev/null || arp -n {gw['gateway']} 2>/dev/null")
                if r.stdout.strip():
                    lines.append(f"\n  {r.stdout.strip()}")
        else:
            lines.append("  No gateway detected")
        return "\n".join(lines)

    def _get_gateway(self) -> dict:
        result = {}
        try:
            if sys.platform == "win32":
                r = self._run(
                    "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
                    "Sort-Object -Property RouteMetric | Select-Object -First 1).NextHop"
                )
                gw = r.stdout.strip()
                if gw:
                    result["gateway"] = gw
            else:
                r = self._run("ip route show default 2>/dev/null | head -1")
                if r.stdout.strip():
                    m = re.search(r"default via (\S+)", r.stdout)
                    if m:
                        result["gateway"] = m.group(1)
                else:
                    r = self._run("route -n 2>/dev/null | awk '/^0.0.0.0/ {print $2; exit}'")
                    if r.stdout.strip():
                        result["gateway"] = r.stdout.strip()

            # Measure latency
            if result.get("gateway"):
                start = time.time()
                if self._ping(result["gateway"], timeout=1.0):
                    result["latency"] = (time.time() - start) * 1000
        except Exception:
            pass
        return result

    # === PUBLIC IP ===

    @safe
    def cmd_public_ip(self, args):
        """Public IP and geo info. Usage: /net.public_ip"""
        info = self._get_public_ip(detailed=True)
        if not info.get("ip"):
            return "Could not determine public IP"
        lines = ["=== 🌍 Public IP ===\n"]
        lines.append(f"  IP:       {info['ip']}")
        for k in ["hostname", "city", "region", "country", "isp", "org", "timezone"]:
            if info.get(k):
                lines.append(f"  {k.capitalize():9s} {info[k]}")
        return "\n".join(lines)

    def _get_public_ip(self, detailed: bool = False) -> dict:
        try:
            import httpx
            with httpx.Client(timeout=5.0) as c:
                if detailed:
                    r = c.get("https://ipapi.co/json/")
                    if r.status_code == 200:
                        return r.json()
                r = c.get("https://ifconfig.me")
                if r.status_code == 200:
                    return {"ip": r.text.strip()}
        except Exception:
            pass
        return {}

    # === SPEED ===

    @safe
    def cmd_speed(self, args):
        """Quick speed test. Usage: /net.speed"""
        lines = ["=== ⚡ Speed Test ===\n"]

        import shutil
        if shutil.which("speedtest-cli"):
            print("Running speedtest-cli...")
            r = self._run("speedtest-cli --simple 2>&1", timeout=60)
            lines.append(r.stdout.strip())
            return "\n".join(lines)

        # Fallback: measure ping + simple download
        try:
            import httpx
            print("Measuring latency to cloudflare.com...")
            start = time.time()
            with httpx.Client(timeout=5.0) as c:
                c.get("https://1.1.1.1/")
            ping_ms = (time.time() - start) * 1000
            lines.append(f"  Ping (1.1.1.1):    {ping_ms:.0f} ms")

            print("Downloading 1MB test file...")
            start = time.time()
            with httpx.Client(timeout=30.0) as c:
                r = c.get("https://speed.cloudflare.com/__down?bytes=1048576")
                if r.status_code == 200:
                    elapsed = time.time() - start
                    mbps = (1.0 / elapsed) * 8
                    lines.append(f"  Download speed:    {mbps:.1f} Mbps (1 MB sample)")
            lines.append("\n  Install speedtest-cli for accurate results")
        except Exception as e:
            lines.append(f"  Error: {e}")
        return "\n".join(lines)

    # === THREATS ===

    @safe
    def cmd_threats(self, args):
        """Scan for network threats. Usage: /net.threats"""
        lines = ["=== ⚠️  Threat Assessment ===\n"]
        issues = []

        # Check 1: Suspicious listening ports (unexpected services)
        suspicious = self._check_suspicious_ports()
        if suspicious:
            lines.append("🔴 Suspicious listening ports:")
            for item in suspicious:
                lines.append(f"   • {item}")
                issues.append(("high", item))

        # Check 2: Public services exposed
        exposed = self._check_public_exposure()
        if exposed:
            lines.append("\n🟡 Services bound to 0.0.0.0 (public):")
            for item in exposed[:10]:
                lines.append(f"   • {item}")
                issues.append(("medium", item))

        # Check 3: DNS hygiene (using public/known servers?)
        dns = self._get_dns_servers()
        safe_dns = {"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9"}
        unknown_dns = [d for d in dns if d not in safe_dns and not d.startswith("192.168.")
                       and not d.startswith("10.") and not d.startswith("172.")]
        if unknown_dns:
            lines.append(f"\n🟡 Unknown DNS servers: {', '.join(unknown_dns)}")
            issues.append(("low", "Non-standard DNS"))

        # Check 4: Gateway reachability
        gw = self._get_gateway()
        if not gw.get("gateway"):
            lines.append("\n🔴 No default gateway detected")
            issues.append(("high", "No gateway"))
        elif gw.get("latency", 0) > 100:
            lines.append(f"\n🟡 High gateway latency: {gw['latency']:.0f} ms")
            issues.append(("low", "High latency"))

        # Check 5: Active connections count
        conns = self._count_connections()
        if conns.get("total", 0) > 100:
            lines.append(f"\n🟡 High number of connections: {conns['total']}")
            issues.append(("low", "Many connections"))

        # Summary
        if not issues:
            lines.append("✓ No obvious threats detected")
        else:
            high = sum(1 for s, _ in issues if s == "high")
            med = sum(1 for s, _ in issues if s == "medium")
            low = sum(1 for s, _ in issues if s == "low")
            lines.append(f"\n--- Summary ---")
            lines.append(f"  High:   {high}")
            lines.append(f"  Medium: {med}")
            lines.append(f"  Low:    {low}")

            # AI recommendations
            if self.ai:
                lines.append("\n--- AI Recommendations ---")
                prompt = (f"Network security scan found:\n"
                          + "\n".join(f"- [{s}] {d}" for s, d in issues)
                          + "\n\nProvide 3-4 specific, actionable fixes. Be concise.")
                try:
                    rec = self.ask_ai(prompt, system="You are a network security expert.")
                    lines.append(rec[:1500])
                except Exception:
                    pass

        return "\n".join(lines)

    def _check_suspicious_ports(self) -> list:
        """Flag well-known backdoor/malware ports if they're listening."""
        suspicious_ports = {
            1337: "Common backdoor",
            31337: "Elite/backdoor",
            4444: "Metasploit default",
            5554: "Sasser worm",
            6667: "IRC (often botnets)",
            12345: "NetBus backdoor",
            27374: "SubSeven backdoor",
            65000: "Devil backdoor",
        }
        found = []
        if sys.platform == "win32":
            r = self._run("Get-NetTCPConnection -State Listen | Select-Object -ExpandProperty LocalPort")
            ports = [int(p.strip()) for p in r.stdout.splitlines() if p.strip().isdigit()]
        else:
            r = self._run("ss -tln 2>/dev/null | awk 'NR>1 {print $4}' | rev | cut -d: -f1 | rev")
            ports = [int(p.strip()) for p in r.stdout.splitlines() if p.strip().isdigit()]

        for p in ports:
            if p in suspicious_ports:
                found.append(f"Port {p}: {suspicious_ports[p]}")
        return found

    def _check_public_exposure(self) -> list:
        """Find services listening on 0.0.0.0 (publicly exposed)."""
        exposed = []
        if sys.platform == "win32":
            r = self._run(
                "Get-NetTCPConnection -State Listen -LocalAddress 0.0.0.0 | "
                "Select-Object LocalPort,OwningProcess | ConvertTo-Csv -NoTypeInformation"
            )
            for line in r.stdout.splitlines()[1:]:  # skip header
                parts = line.strip().strip('"').split('","')
                if len(parts) >= 1:
                    exposed.append(f"Port {parts[0]}")
        else:
            r = self._run("ss -tlnp 2>/dev/null | grep '0.0.0.0' | awk '{print $4, $6}' | head -20")
            for line in r.stdout.splitlines():
                if line.strip():
                    exposed.append(line.strip())
        return exposed

    # === SCORE ===

    @safe
    def cmd_score(self, args):
        """Overall network effectiveness score. Usage: /net.score"""
        lines = ["=== 📊 Network Effectiveness Score ===\n"]

        score = 100
        factors = []

        # Gateway latency
        gw = self._get_gateway()
        latency = gw.get("latency", 0)
        if latency == 0:
            score -= 10
            factors.append(("?", "Could not measure gateway"))
        elif latency < 5:
            factors.append(("+10", f"Excellent gateway latency: {latency:.1f}ms"))
        elif latency < 20:
            factors.append(("+5",  f"Good gateway latency: {latency:.1f}ms"))
        elif latency < 50:
            score -= 5
            factors.append(("-5",  f"Acceptable latency: {latency:.1f}ms"))
        else:
            score -= 15
            factors.append(("-15", f"High latency: {latency:.1f}ms"))

        # Interface count
        active = [i for i in self._get_interfaces() if i.get("status") == "up"]
        if not active:
            score -= 40
            factors.append(("-40", "No active interfaces"))
        else:
            factors.append(("+0", f"{len(active)} active interface(s)"))

        # DNS health
        dns = self._get_dns_servers()
        if not dns:
            score -= 15
            factors.append(("-15", "No DNS servers"))
        elif len(dns) < 2:
            score -= 5
            factors.append(("-5", f"Only {len(dns)} DNS server (redundancy low)"))
        else:
            factors.append(("+0", f"{len(dns)} DNS servers configured"))

        # Public connectivity
        pub = self._get_public_ip()
        if not pub.get("ip"):
            score -= 20
            factors.append(("-20", "No public internet"))
        else:
            factors.append(("+0", f"Internet OK (IP: {pub['ip']})"))

        # Threats
        suspicious = self._check_suspicious_ports()
        if suspicious:
            penalty = 10 * len(suspicious)
            score -= penalty
            factors.append((f"-{penalty}", f"{len(suspicious)} suspicious port(s) open"))

        # Bound everything
        score = max(0, min(100, score))

        grade = ("A+" if score >= 95 else "A" if score >= 85 else "B" if score >= 75
                 else "C" if score >= 65 else "D" if score >= 50 else "F")

        lines.append(f"  Score: {score}/100  (Grade: {grade})\n")
        lines.append("  Factors:")
        for delta, reason in factors:
            lines.append(f"    {delta:5s}  {reason}")
        return "\n".join(lines)

    # === REPORT / WATCH ===

    @safe
    def cmd_report(self, args):
        """Generate full network report. Usage: /net.report"""
        sections = [
            ("Overview", self.cmd_overview("")),
            ("Score", self.cmd_score("")),
            ("Threats", self.cmd_threats("")),
            ("Interfaces", self.cmd_interfaces("")),
            ("DNS", self.cmd_dns("")),
            ("Gateway", self.cmd_gateway("")),
        ]
        out = [
            "=" * 55,
            "  🌐 FULL NETWORK REPORT",
            f"  {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 55,
        ]
        for title, content in sections:
            out.append(f"\n{'─' * 55}")
            out.append(f"  {title}")
            out.append(f"{'─' * 55}")
            out.append(content)

        report = "\n".join(out)
        fp = self._dir / f"report_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        fp.write_text(report, encoding="utf-8")
        return report + f"\n\n📄 Saved: {fp}"

    @safe
    def cmd_watch(self, args):
        """Monitor connections (5-second snapshot). Usage: /net.watch"""
        print("📊 Collecting 5-second sample...")
        before = self._count_connections()
        time.sleep(5)
        after = self._count_connections()
        lines = ["=== 👀 5-Second Snapshot ===\n"]
        lines.append(f"  Connections:  {before['total']} → {after['total']}  ({after['total'] - before['total']:+d})")
        lines.append(f"  Listening:    {before['listening']} → {after['listening']}  ({after['listening'] - before['listening']:+d})")
        return "\n".join(lines)
    @safe
    def cmd_explain(self, arg=""):  # v3.11: auto-injected cmd_explain
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            # Fallback if _shared.explain isn't importable
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{getattr(self, 'name', '?')}] {getattr(self, 'description', '')}"]
            lines.append("")
            lines.append("Commands:")
            for c in cmds:
                lines.append(f"  /{getattr(self, 'name', '?')} {c}")
            return "\n".join(lines)

```

## `modules/nettools/__init__.py`

```python
"""NetTools Module — Networking utilities (ping, traceroute, DNS, whois).

Complements /net (netscan) with active tools for reachability, name
resolution, and route analysis. Pure stdlib where possible, with optional
native tool wrappers.

Commands (16):
  /nt ping <host> [count]       ICMP ping
  /nt trace <host>              traceroute / tracert
  /nt dns <name> [type]         DNS lookup (A, AAAA, MX, TXT, NS, CNAME)
  /nt reverse <ip>              Reverse DNS (PTR)
  /nt whois <domain-or-ip>      WHOIS query
  /nt tcp-test <host> <port>    TCP connection probe
  /nt http-ping <url>           Timed HTTP GET
  /nt myip                      Public IP via multiple services
  /nt geoip <ip>                IP geolocation (free service)
  /nt mtu <host>                Find MTU to a host
  /nt latency <host> [count]    Latency stats (min/avg/max/stddev)
  /nt bandwidth                 Local link bandwidth estimate
  /nt ports-common              Common port reference
  /nt ssl-info <host>[:port]    TLS/SSL certificate info
  /nt headers <url>             HTTP headers only
  /nt host-info <host>          Aggregate info on a single host
"""

import json
import math
import os
import re
import socket
import ssl
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


COMMON_PORTS = {
    20: "FTP data", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP",
    53: "DNS", 67: "DHCP server", 68: "DHCP client", 69: "TFTP",
    80: "HTTP", 110: "POP3", 119: "NNTP", 123: "NTP", 143: "IMAP",
    161: "SNMP", 162: "SNMP trap", 389: "LDAP", 443: "HTTPS",
    445: "SMB", 465: "SMTPS", 514: "Syslog", 587: "SMTP (submission)",
    636: "LDAPS", 873: "rsync", 993: "IMAPS", 995: "POP3S",
    1080: "SOCKS", 1194: "OpenVPN", 1433: "MSSQL", 1521: "Oracle",
    1723: "PPTP", 3128: "Squid", 3306: "MySQL", 3389: "RDP",
    5000: "UPnP/Flask", 5432: "PostgreSQL", 5900: "VNC", 6379: "Redis",
    6667: "IRC", 8000: "HTTP alt", 8080: "HTTP proxy", 8443: "HTTPS alt",
    8888: "HTTP alt", 9090: "Prometheus", 9200: "Elasticsearch",
    11211: "Memcached", 25565: "Minecraft", 27017: "MongoDB",
}


class NetToolsModule(Module):
    name = "nt"
    version = "1.0.0"
    description = "Active networking utilities: ping, dns, whois, tcp, ssl"
    author = "termaid"

    def on_load(self):
        cmds = ["ping", "trace", "dns", "reverse", "whois", "tcp-test",
                "http-ping", "myip", "geoip", "mtu", "latency", "bandwidth",
                "ports-common", "ssl-info", "headers", "host-info", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "nt"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _run(self, argv, timeout=30):
        try:
            return subprocess.run(argv, capture_output=True, text=True,
                                  timeout=timeout, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return subprocess.CompletedProcess(argv, 127, "", "not found")
        except Exception as e:
            return subprocess.CompletedProcess(argv, 1, "", str(e))

    def _which(self, tool):
        exts = (".exe", ".cmd", "") if sys.platform == "win32" else ("",)
        for p in os.environ.get("PATH", "").split(os.pathsep):
            for ext in exts:
                f = Path(p) / f"{tool}{ext}"
                if f.exists(): return str(f)
        return None

    # ---------- commands ----------

    @safe
    def cmd_ping(self, arg=""):
        parts = (arg or "").split()
        if not parts: return "[nt] Usage: /nt ping <host> [count]"
        host = parts[0]
        count = parts[1] if len(parts) > 1 else "4"
        flag = "-n" if sys.platform == "win32" else "-c"
        r = self._run(["ping", flag, count, host], timeout=int(count) * 2 + 5)
        return f"[nt] ping {host}:\n{r.stdout or r.stderr}"

    @safe
    def cmd_trace(self, arg=""):
        host = (arg or "").strip()
        if not host: return "[nt] Usage: /nt trace <host>"
        tool = "tracert" if sys.platform == "win32" else "traceroute"
        if not self._which(tool):
            return f"[nt] {tool} not installed."
        r = self._run([tool, host], timeout=60)
        return f"[nt] {tool} {host}:\n{r.stdout or r.stderr}"

    @safe
    def cmd_dns(self, arg=""):
        parts = (arg or "").split()
        if not parts: return "[nt] Usage: /nt dns <name> [A|AAAA|MX|TXT|NS|CNAME]"
        name = parts[0]
        qtype = parts[1].upper() if len(parts) > 1 else "A"
        # Prefer dig/nslookup for richer output
        if self._which("dig"):
            r = self._run(["dig", "+short", name, qtype], timeout=10)
            return f"[nt] dig {name} {qtype}:\n{r.stdout or '(no answer)'}"
        if self._which("nslookup"):
            r = self._run(["nslookup", f"-type={qtype}", name], timeout=10)
            return f"[nt] nslookup {name} {qtype}:\n{r.stdout}"
        # Fallback: stdlib socket for A/AAAA only
        try:
            if qtype == "A":
                ips = socket.gethostbyname_ex(name)[2]
                return f"[nt] A {name}:\n" + "\n".join(f"  {ip}" for ip in ips)
            return f"[nt] Install dig or nslookup for {qtype} queries."
        except Exception as e:
            return f"[nt] Lookup failed: {e}"

    @safe
    def cmd_reverse(self, arg=""):
        ip = (arg or "").strip()
        if not ip: return "[nt] Usage: /nt reverse <ip>"
        try:
            name, aliases, _ = socket.gethostbyaddr(ip)
            lines = [f"[nt] Reverse DNS for {ip}:", f"  {name}"]
            for a in aliases:
                lines.append(f"  {a} (alias)")
            return "\n".join(lines)
        except Exception as e:
            return f"[nt] PTR lookup failed: {e}"

    @safe
    def cmd_whois(self, arg=""):
        target = (arg or "").strip()
        if not target: return "[nt] Usage: /nt whois <domain-or-ip>"
        if self._which("whois"):
            r = self._run(["whois", target], timeout=30)
            # Trim excessive legalese; show first ~60 lines
            lines = (r.stdout or "").splitlines()
            return f"[nt] whois {target}:\n" + "\n".join(lines[:80])
        return ("[nt] whois not installed.\n"
                "     Install: apt install whois  /  brew install whois  /  pkg install whois\n"
                "     Or query via web: https://lookup.icann.org/")

    @safe
    def cmd_tcp_test(self, arg=""):
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[nt] Usage: /nt tcp-test <host> <port>"
        host = parts[0]
        try: port = int(parts[1])
        except Exception: return "[nt] Invalid port."
        start = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=5) as s:
                elapsed = (time.perf_counter() - start) * 1000
                return (f"[nt] ✓ {host}:{port} reachable  ({elapsed:.1f} ms)\n"
                        f"     Service: {COMMON_PORTS.get(port, 'unknown')}")
        except socket.timeout:
            return f"[nt] ✗ {host}:{port} timeout (5s)"
        except Exception as e:
            return f"[nt] ✗ {host}:{port} failed: {e}"

    @safe
    def cmd_http_ping(self, arg=""):
        url = (arg or "").strip()
        if not url: return "[nt] Usage: /nt http-ping <url>"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        samples = []
        for i in range(5):
            try:
                start = time.perf_counter()
                with urllib.request.urlopen(url, timeout=10) as resp:
                    resp.read(1024)
                samples.append((time.perf_counter() - start) * 1000)
            except Exception as e:
                samples.append(None)
        valid = [s for s in samples if s is not None]
        if not valid:
            return f"[nt] All requests failed for {url}"
        lines = [f"[nt] HTTP ping {url}:"]
        for i, s in enumerate(samples, 1):
            lines.append(f"  [{i}] " + (f"{s:.1f} ms" if s else "FAILED"))
        lines.append(f"\n  min={min(valid):.1f}  avg={statistics.mean(valid):.1f}  "
                     f"max={max(valid):.1f} ms")
        return "\n".join(lines)

    @safe
    def cmd_myip(self, arg=""):
        services = [
            "https://api.ipify.org",
            "https://ifconfig.me/ip",
            "https://icanhazip.com",
            "https://checkip.amazonaws.com",
        ]
        results = []
        for svc in services:
            try:
                with urllib.request.urlopen(svc, timeout=5) as resp:
                    ip = resp.read().decode().strip()
                    results.append((svc, ip))
            except Exception as e:
                results.append((svc, f"error: {e}"))
        lines = ["[nt] Public IP (queried multiple services):"]
        for svc, ip in results:
            lines.append(f"  {svc:<40s} {ip}")
        return "\n".join(lines)

    @safe
    def cmd_geoip(self, arg=""):
        ip = (arg or "").strip()
        if not ip: return "[nt] Usage: /nt geoip <ip>"
        # Use ip-api.com free tier (no key, rate-limited)
        try:
            with urllib.request.urlopen(f"http://ip-api.com/json/{ip}", timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except Exception as e:
            return f"[nt] Lookup failed: {e}"
        if data.get("status") != "success":
            return f"[nt] Error: {data.get('message','unknown')}"
        lines = [f"[nt] GeoIP for {ip}:"]
        for k in ("country", "regionName", "city", "zip", "lat", "lon",
                  "timezone", "isp", "org", "as"):
            if data.get(k):
                lines.append(f"  {k:<12s} {data[k]}")
        return "\n".join(lines)

    @safe
    def cmd_mtu(self, arg=""):
        host = (arg or "").strip()
        if not host: return "[nt] Usage: /nt mtu <host>"
        # Binary search using don't-fragment pings
        lo, hi = 1000, 1500
        best = None
        print(f"[nt] Probing MTU to {host} (binary search)...")
        for _ in range(8):
            size = (lo + hi) // 2
            if sys.platform == "win32":
                argv = ["ping", "-n", "1", "-l", str(size), "-f", host]
            else:
                # -M do = set don't-fragment
                argv = ["ping", "-c", "1", "-M", "do", "-s", str(size), host]
            r = self._run(argv, timeout=5)
            if r.returncode == 0 and "too long" not in (r.stdout or "").lower():
                best = size
                lo = size + 1
            else:
                hi = size - 1
            if lo > hi: break
        if best:
            # Actual MTU = payload + 28 (IP + ICMP headers)
            return f"[nt] Max successful payload: {best} bytes  =>  MTU ≈ {best + 28} bytes"
        return "[nt] Could not determine MTU."

    @safe
    def cmd_latency(self, arg=""):
        parts = (arg or "").split()
        if not parts: return "[nt] Usage: /nt latency <host> [count]"
        host = parts[0]
        try: count = int(parts[1]) if len(parts) > 1 else 10
        except Exception: count = 10
        samples = []
        for _ in range(count):
            flag = "-n" if sys.platform == "win32" else "-c"
            r = self._run(["ping", flag, "1", host], timeout=5)
            m = re.search(r"time[=<]?\s*([\d.]+)\s*ms", r.stdout or "")
            if m:
                try: samples.append(float(m.group(1)))
                except Exception: pass
            time.sleep(0.2)
        if not samples:
            return f"[nt] No replies from {host}"
        lines = [f"[nt] Latency stats for {host} ({len(samples)}/{count} replies):"]
        lines.append(f"  min:    {min(samples):.2f} ms")
        lines.append(f"  avg:    {statistics.mean(samples):.2f} ms")
        lines.append(f"  max:    {max(samples):.2f} ms")
        if len(samples) > 1:
            lines.append(f"  stddev: {statistics.stdev(samples):.2f} ms")
        return "\n".join(lines)

    @safe
    def cmd_bandwidth(self, arg=""):
        """Rough estimate via downloading a test file."""
        print("[nt] Running bandwidth test (downloads ~10 MB)...")
        url = "http://speedtest.ftp.otenet.gr/files/test10Mb.db"
        try:
            start = time.perf_counter()
            total = 0
            with urllib.request.urlopen(url, timeout=30) as resp:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk: break
                    total += len(chunk)
            elapsed = time.perf_counter() - start
            mbps = (total * 8) / (elapsed * 1000 * 1000)
            return (f"[nt] Downloaded {total/(1024*1024):.1f} MB in {elapsed:.2f}s\n"
                    f"     Estimated bandwidth: {mbps:.1f} Mbps")
        except Exception as e:
            return f"[nt] Bandwidth test failed: {e}"

    @safe
    def cmd_ports_common(self, arg=""):
        lines = [f"[nt] {len(COMMON_PORTS)} common port(s) reference:"]
        for port, svc in sorted(COMMON_PORTS.items()):
            lines.append(f"  {port:>5d}   {svc}")
        return "\n".join(lines)

    @safe
    def cmd_ssl_info(self, arg=""):
        target = (arg or "").strip()
        if not target: return "[nt] Usage: /nt ssl-info <host>[:port]"
        if ":" in target:
            host, port = target.rsplit(":", 1)
            try: port = int(port)
            except Exception: return "[nt] Invalid port"
        else:
            host, port = target, 443
        ctx = ssl.create_default_context()
        try:
            with socket.create_connection((host, port), timeout=10) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
        except Exception as e:
            return f"[nt] TLS handshake failed: {e}"
        lines = [f"[nt] TLS info for {host}:{port}:"]
        lines.append(f"  Protocol: {version}")
        lines.append(f"  Cipher:   {cipher[0]}  ({cipher[1]} bits)")
        subj = dict(x[0] for x in cert.get("subject", []))
        issuer = dict(x[0] for x in cert.get("issuer", []))
        lines.append(f"  Subject:  {subj.get('commonName','')}")
        lines.append(f"  Issuer:   {issuer.get('commonName','')} / {issuer.get('organizationName','')}")
        lines.append(f"  Valid:    {cert.get('notBefore','')}  to  {cert.get('notAfter','')}")
        sans = cert.get("subjectAltName", [])
        if sans:
            lines.append(f"  SANs:     {', '.join(s[1] for s in sans[:10])}")
            if len(sans) > 10:
                lines.append(f"            ... {len(sans)-10} more")
        return "\n".join(lines)

    @safe
    def cmd_headers(self, arg=""):
        url = (arg or "").strip()
        if not url: return "[nt] Usage: /nt headers <url>"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                lines = [f"[nt] HEAD {url}:",
                         f"  Status: {resp.status} {resp.reason}"]
                for k, v in resp.headers.items():
                    lines.append(f"  {k}: {v}")
                return "\n".join(lines)
        except urllib.error.HTTPError as e:
            lines = [f"[nt] HEAD {url}:", f"  Status: {e.code} {e.reason}"]
            for k, v in (e.headers.items() if e.headers else []):
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        except Exception as e:
            return f"[nt] Failed: {e}"

    @safe
    def cmd_host_info(self, arg=""):
        host = (arg or "").strip()
        if not host: return "[nt] Usage: /nt host-info <host>"
        lines = [f"[nt] Aggregate info for {host}:"]
        # DNS A
        try:
            ips = socket.gethostbyname_ex(host)[2]
            lines.append(f"  A records: {', '.join(ips)}")
        except Exception as e:
            lines.append(f"  A lookup:  failed ({e})")
            return "\n".join(lines)
        # Reverse
        try:
            rev = socket.gethostbyaddr(ips[0])[0]
            lines.append(f"  PTR:       {rev}")
        except Exception: pass
        # Reachability ping
        flag = "-n" if sys.platform == "win32" else "-c"
        r = self._run(["ping", flag, "2", host], timeout=10)
        if r.returncode == 0:
            lines.append(f"  Ping:      reachable")
        else:
            lines.append(f"  Ping:      no reply")
        # Common port probe
        open_ports = []
        for port in (22, 80, 443, 25, 21):
            try:
                with socket.create_connection((host, port), timeout=2):
                    open_ports.append(port)
            except Exception: pass
        if open_ports:
            lines.append(f"  Open:      " + ", ".join(f"{p}({COMMON_PORTS.get(p,'?')})"
                                                      for p in open_ports))
        else:
            lines.append(f"  Open:      none detected (22/80/443/25/21)")
        return "\n".join(lines)
    @safe
    def cmd_explain(self, arg=""):  # v3.11: auto-injected cmd_explain
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            # Fallback if _shared.explain isn't importable
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{getattr(self, 'name', '?')}] {getattr(self, 'description', '')}"]
            lines.append("")
            lines.append("Commands:")
            for c in cmds:
                lines.append(f"  /{getattr(self, 'name', '?')} {c}")
            return "\n".join(lines)

```

## `modules/netdeep/__init__.py`

```python
"""Network Deep Module — Beyond /nt, /net, and /netscan.

WiFi adapter capabilities, regulatory domain, channel scanning,
Ethernet auto-negotiation, MTU path discovery, Bluetooth stack inspection,
WireGuard helpers.

Complements existing /nt (active probing) and /net (scanning).

Commands (15):
  /nd status              All network interfaces + state
  /nd wifi-info           WiFi adapter capabilities + driver
  /nd wifi-scan           Scan visible networks (current band)
  /nd wifi-current        Currently associated network details
  /nd wifi-channels       Channel usage / congestion in current area
  /nd reg-domain          Regulatory domain + allowed channels
  /nd ethernet-info       Ethernet adapter capabilities + negotiated speed
  /nd ethernet-negotiate  Force speed/duplex (walkthrough)
  /nd mtu-discover <host> Path MTU discovery
  /nd bluetooth           Bluetooth adapters + connected devices
  /nd dns-cache           Local DNS resolver cache
  /nd routes              Routing table with annotations
  /nd firewall            Local firewall status
  /nd wireguard           WireGuard config + status
  /nd vpn-status          Active VPN / tunnel interfaces
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class NetDeepModule(Module):
    name = "nd"
    version = "1.0.0"
    description = "Deep network inspection: WiFi, Ethernet, Bluetooth, VPN"
    author = "termaid"

    def on_load(self):
        cmds = ["status", "wifi-info", "wifi-scan", "wifi-current",
                "wifi-channels", "reg-domain", "ethernet-info",
                "ethernet-negotiate", "mtu-discover", "bluetooth",
                "dns-cache", "routes", "firewall", "wireguard", "vpn-status", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "nd"
        self._dir.mkdir(parents=True, exist_ok=True)

    def _run(self, cmd, timeout=15, shell=False):
        try:
            if sys.platform == "win32" and isinstance(cmd, str):
                return subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                      capture_output=True, text=True, timeout=timeout,
                                      encoding="utf-8", errors="replace")
            return subprocess.run(cmd, shell=shell or isinstance(cmd, str),
                                  capture_output=True, text=True, timeout=timeout,
                                  encoding="utf-8", errors="replace")
        except Exception as e:
            return subprocess.CompletedProcess(cmd, 1, "", str(e))

    def _which(self, t): return shutil.which(t)

    @safe
    def cmd_status(self, arg=""):
        if sys.platform == "win32":
            r = self._run(
                "Get-NetAdapter | Select-Object Name,Status,LinkSpeed,MediaType,InterfaceDescription | "
                "Format-Table -AutoSize | Out-String -Width 200", timeout=10)
            return f"[nd] Network adapters:\n{r.stdout or r.stderr}"
        lines = ["[nd] Network interfaces:"]
        if self._which("ip"):
            r = self._run(["ip", "-brief", "address"], timeout=5)
            lines.append(r.stdout)
            r = self._run(["ip", "-brief", "link"], timeout=5)
            lines.append("\nLink state:\n" + r.stdout)
        else:
            r = self._run(["ifconfig", "-a"], timeout=5)
            lines.append(r.stdout[:3000])
        return "\n".join(lines)

    @safe
    def cmd_wifi_info(self, arg=""):
        if sys.platform == "win32":
            r = self._run("netsh wlan show drivers", timeout=10)
            return f"[nd] WiFi adapter info:\n{r.stdout or r.stderr}"
        if self._which("iw"):
            r = self._run(["iw", "list"], timeout=5)
            out = r.stdout[:4000] if r.stdout else r.stderr
            return f"[nd] WiFi adapter capabilities (iw list):\n{out}"
        if self._which("iwconfig"):
            r = self._run(["iwconfig"], timeout=5)
            return f"[nd] WiFi info (iwconfig — old):\n{r.stdout or r.stderr}"
        return "[nd] No WiFi tools found. Install: sudo apt install iw wireless-tools"

    @safe
    def cmd_wifi_scan(self, arg=""):
        if sys.platform == "win32":
            r = self._run("netsh wlan show networks mode=bssid", timeout=15)
            return f"[nd] Visible WiFi networks:\n{r.stdout[:6000] or r.stderr}"
        # Linux: prefer nmcli > iwlist > iw
        if self._which("nmcli"):
            r = self._run(["nmcli", "-c", "no", "-f",
                           "SSID,BSSID,CHAN,RATE,SIGNAL,SECURITY", "device", "wifi", "list"],
                          timeout=15)
            return f"[nd] Visible WiFi networks:\n{r.stdout[:6000] or r.stderr}"
        if self._which("iwlist"):
            # Need an interface
            r = self._run("iwconfig 2>/dev/null | grep 'IEEE 802.11' | awk '{print $1}'",
                          timeout=5, shell=True)
            iface = (r.stdout or "").strip().split("\n")[0]
            if not iface: return "[nd] No WiFi interface found."
            r = self._run(["sudo", "-n", "iwlist", iface, "scan"], timeout=15)
            return f"[nd] Scan ({iface}):\n{r.stdout[:6000] or r.stderr}"
        return "[nd] No WiFi scanning tool. Install nmcli or wireless-tools."

    @safe
    def cmd_wifi_current(self, arg=""):
        if sys.platform == "win32":
            r = self._run("netsh wlan show interfaces", timeout=10)
            return f"[nd] Current WiFi association:\n{r.stdout or r.stderr}"
        if self._which("nmcli"):
            r = self._run(["nmcli", "-f", "ACTIVE,SSID,BSSID,CHAN,RATE,SIGNAL,BARS,SECURITY",
                           "device", "wifi"], timeout=10)
            # Filter to active
            lines = (r.stdout or "").splitlines()
            return "[nd] Currently connected WiFi:\n" + "\n".join([l for l in lines if "yes" in l.lower()][:1] or lines[:2])
        if self._which("iwconfig"):
            r = self._run(["iwconfig"], timeout=5)
            return f"[nd] iwconfig output:\n{r.stdout or r.stderr}"
        return "[nd] No WiFi tool available."

    @safe
    def cmd_wifi_channels(self, arg=""):
        if sys.platform == "win32":
            return ("[nd] Windows channel usage:\n"
                    "  netsh wlan show networks mode=bssid    (channel field)\n"
                    "  GUI: Acrylic WiFi Home, NetSpot — proper heatmaps + congestion.")
        if not self._which("nmcli"):
            return ("[nd] Install nmcli (NetworkManager) for channel data.\n"
                    "  Or: sudo iwlist scan | grep -E 'Frequency|Channel'")
        r = self._run(["nmcli", "-c", "no", "-f", "CHAN,SIGNAL,SSID", "device", "wifi", "list"],
                      timeout=15)
        if r.returncode != 0:
            return f"[nd] {r.stderr}"
        from collections import Counter
        channels = Counter()
        for line in (r.stdout or "").splitlines()[1:]:
            parts = line.split()
            if parts and parts[0].isdigit():
                channels[int(parts[0])] += 1
        if not channels:
            return "[nd] No networks found to compute channel usage."
        lines = ["[nd] Channel usage (current visible networks):"]
        for ch, n in sorted(channels.items()):
            bar = "█" * n
            lines.append(f"  Ch {ch:>3d}: {bar} ({n})")
        lines.append("")
        lines.append("  2.4 GHz: only channels 1, 6, 11 are non-overlapping. Pick whichever is least used.")
        lines.append("  5 GHz: many non-overlapping channels. Less crowded usually.")
        lines.append("  6 GHz (WiFi 6E): cleanest, but needs WiFi 6E client + AP.")
        return "\n".join(lines)

    @safe
    def cmd_reg_domain(self, arg=""):
        if sys.platform == "win32":
            return ("[nd] Regulatory domain on Windows:\n"
                    "  Get-NetAdapterAdvancedProperty -Name *wifi*    (look for 'Country Region')\n"
                    "  Or device manager -> NIC -> Advanced -> Country Region")
        if not self._which("iw"):
            return "[nd] Install iw: sudo apt install iw"
        r = self._run(["iw", "reg", "get"], timeout=5)
        lines = [f"[nd] Wireless regulatory domain:\n{r.stdout}"]
        lines.append("\n  Set domain (requires root):")
        lines.append("    sudo iw reg set US        # United States")
        lines.append("    sudo iw reg set DE        # Germany")
        lines.append("    sudo iw reg set 00        # World (most restrictive)")
        lines.append("")
        lines.append("  Persistent: edit /etc/default/crda (Debian/Ubuntu) or")
        lines.append("  /etc/conf.d/wireless-regdom (Arch)")
        return "\n".join(lines)

    @safe
    def cmd_ethernet_info(self, arg=""):
        if sys.platform == "win32":
            r = self._run(
                "Get-NetAdapter | Where-Object {$_.MediaType -eq '802.3'} | "
                "Format-List Name,Status,LinkSpeed,MediaType,FullDuplex,MtuSize", timeout=10)
            return f"[nd] Ethernet adapters:\n{r.stdout or r.stderr}"
        if not self._which("ethtool"):
            return "[nd] Install ethtool: sudo apt install ethtool"
        # Find ethernet interfaces
        r = self._run("ip -brief link | grep -E 'eth|enp|eno' | awk '{print $1}'",
                      timeout=5, shell=True)
        ifaces = (r.stdout or "").strip().split("\n")
        if not ifaces or not ifaces[0]:
            return "[nd] No Ethernet interfaces found."
        lines = ["[nd] Ethernet adapters:"]
        for iface in ifaces:
            iface = iface.strip()
            if not iface: continue
            lines.append(f"\n  --- {iface} ---")
            r = self._run(["sudo", "-n", "ethtool", iface], timeout=5)
            if r.returncode == 0:
                lines.append(r.stdout)
            else:
                r = self._run(["ethtool", iface], timeout=5)
                lines.append(r.stdout or r.stderr)
        return "\n".join(lines)

    @safe
    def cmd_ethernet_negotiate(self, arg=""):
        if sys.platform == "win32":
            return """[nd] Force Ethernet speed/duplex on Windows:

  Method 1: Device Manager
    Right-click NIC -> Properties -> Advanced -> 'Speed & Duplex'
    Pick: Auto (default), 1.0 Gbps Full Duplex, etc.

  Method 2: PowerShell
    Set-NetAdapterAdvancedProperty -Name 'Ethernet' -DisplayName 'Speed & Duplex' -DisplayValue '1.0 Gbps Full Duplex'

  ALMOST ALWAYS leave on Auto. Forcing is needed only for:
    - Diagnosing flapping links
    - Older switch that mis-negotiates
    - Specific QoS / VLAN requirements"""
        return """[nd] Force Ethernet speed/duplex on Linux:

  ━━━ TEMPORARY (current session) ━━━

    sudo ethtool -s eth0 speed 1000 duplex full autoneg off
    sudo ethtool -s eth0 autoneg on              # back to auto

  ━━━ PERSISTENT ━━━

  Debian/Ubuntu (/etc/network/interfaces):
    iface eth0 inet dhcp
      pre-up ethtool -s eth0 speed 1000 duplex full autoneg off

  systemd-networkd (/etc/systemd/network/eth0.link):
    [Match]
    OriginalName=eth0
    [Link]
    BitsPerSecond=1G
    Duplex=full

  NetworkManager:
    nmcli connection modify 'Wired' 802-3-ethernet.speed 1000
    nmcli connection modify 'Wired' 802-3-ethernet.duplex full
    nmcli connection modify 'Wired' 802-3-ethernet.auto-negotiate no

  ALMOST ALWAYS leave on auto. Forcing only for diagnosis or
  ancient infrastructure."""

    @safe
    def cmd_mtu_discover(self, arg=""):
        host = (arg or "").strip()
        if not host: return "[nd] Usage: /nd mtu-discover <host>"
        if sys.platform == "win32":
            # Use ping with DF flag
            return (f"[nd] Windows path MTU discovery to {host}:\n"
                    f"  ping -f -l 1472 {host}   # try 1472, decrease if 'Packet needs to be fragmented'\n"
                    f"  ping -f -l 1464 {host}\n"
                    f"  ...\n"
                    f"  Find largest size that doesn't fragment. Add 28 (IP+ICMP headers) for MTU.")
        lines = [f"[nd] Path MTU discovery to {host} (binary search):"]
        lo, hi = 1200, 1500
        best = None
        while lo <= hi:
            size = (lo + hi) // 2
            r = self._run(["ping", "-c", "1", "-M", "do", "-s", str(size), host], timeout=5)
            if r.returncode == 0 and "too long" not in (r.stdout or "").lower():
                best = size
                lo = size + 1
            else:
                hi = size - 1
        if best is not None:
            lines.append(f"  Largest non-fragmenting payload: {best} bytes")
            lines.append(f"  Inferred path MTU:               {best + 28} bytes (payload + 20 IP + 8 ICMP)")
            return "\n".join(lines)
        return f"[nd] Could not determine MTU (host may be unreachable)."

    @safe
    def cmd_bluetooth(self, arg=""):
        if sys.platform == "win32":
            r = self._run(
                "Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName,Status,InstanceId | "
                "Format-Table -AutoSize | Out-String -Width 200", timeout=10)
            return f"[nd] Bluetooth devices:\n{r.stdout or r.stderr}"
        if self._which("bluetoothctl"):
            r = self._run(["bluetoothctl", "list"], timeout=5)
            adapters = r.stdout
            r2 = self._run(["bluetoothctl", "devices"], timeout=5)
            devices = r2.stdout
            r3 = self._run(["bluetoothctl", "show"], timeout=5)
            return (f"[nd] Bluetooth adapters:\n{adapters}\n"
                    f"Paired/known devices:\n{devices}\n"
                    f"Default adapter:\n{r3.stdout[:1000]}")
        if self._which("hciconfig"):
            r = self._run(["hciconfig", "-a"], timeout=5)
            return f"[nd] Bluetooth (hciconfig — old):\n{r.stdout or r.stderr}"
        return "[nd] No Bluetooth tools. Install: sudo apt install bluez"

    @safe
    def cmd_dns_cache(self, arg=""):
        if sys.platform == "win32":
            r = self._run("Get-DnsClientCache | Select-Object Entry,RecordName,RecordType,Data | "
                          "Format-Table -AutoSize | Out-String -Width 200", timeout=10)
            return f"[nd] Windows DNS resolver cache:\n{r.stdout[:5000] or r.stderr}\n\n  Clear: ipconfig /flushdns"
        # Linux: systemd-resolved
        if self._which("resolvectl"):
            r = self._run(["resolvectl", "statistics"], timeout=5)
            lines = [f"[nd] systemd-resolved stats:\n{r.stdout}"]
            r = self._run(["resolvectl", "query", "--cache-only", "test"], timeout=5)
            # Just demonstrate it exists
            lines.append("\n  Show cached for a name:")
            lines.append("    resolvectl query example.com")
            lines.append("  Clear cache:")
            lines.append("    sudo resolvectl flush-caches")
            return "\n".join(lines)
        # nscd
        if self._which("nscd"):
            r = self._run(["nscd", "-g"], timeout=5)
            return f"[nd] nscd stats:\n{r.stdout[:3000]}"
        return ("[nd] No system DNS cache active.\n"
                "  Resolver: see /etc/resolv.conf\n"
                "  Most Linux systems don't cache DNS by default (uses libc).")

    @safe
    def cmd_routes(self, arg=""):
        if sys.platform == "win32":
            r = self._run("Get-NetRoute | Where-Object {$_.AddressFamily -eq 'IPv4'} | "
                          "Sort-Object DestinationPrefix | Format-Table -AutoSize | Out-String -Width 200", timeout=10)
            return f"[nd] IPv4 routing table:\n{r.stdout[:4000] or r.stderr}"
        if self._which("ip"):
            r = self._run(["ip", "route", "show"], timeout=5)
            lines = [f"[nd] IPv4 routes:\n{r.stdout}"]
            r6 = self._run(["ip", "-6", "route", "show"], timeout=5)
            if r6.stdout.strip():
                lines.append(f"\nIPv6 routes:\n{r6.stdout[:2000]}")
            # Annotation
            lines.append("\n  Reading routes:")
            lines.append("    default via <gw> dev <iface>  = your default gateway")
            lines.append("    <subnet>/<bits> dev <iface>   = on-link (LAN)")
            lines.append("    <ip> via <gw>                 = static route")
            return "\n".join(lines)
        if self._which("route"):
            r = self._run(["route", "-n"], timeout=5)
            return f"[nd] Routes:\n{r.stdout}"
        return "[nd] No route tool available."

    @safe
    def cmd_firewall(self, arg=""):
        if sys.platform == "win32":
            r = self._run("Get-NetFirewallProfile | Select Name,Enabled,DefaultInboundAction,DefaultOutboundAction | Format-List", timeout=10)
            return f"[nd] Windows Firewall:\n{r.stdout or r.stderr}"
        lines = ["[nd] Linux firewall status:"]
        if self._which("ufw"):
            r = self._run(["sudo", "-n", "ufw", "status"], timeout=5)
            lines.append(f"  ufw:       {r.stdout.strip() or r.stderr.strip()}")
        if self._which("firewall-cmd"):
            r = self._run(["firewall-cmd", "--state"], timeout=5)
            lines.append(f"  firewalld: {r.stdout.strip() or r.stderr.strip()}")
        if self._which("nft"):
            r = self._run(["sudo", "-n", "nft", "list", "ruleset"], timeout=5)
            if r.returncode == 0 and r.stdout.strip():
                lines.append(f"\n  nftables rules:\n{r.stdout[:3000]}")
        if self._which("iptables"):
            r = self._run(["sudo", "-n", "iptables", "-L", "-n", "-v"], timeout=10)
            if r.returncode == 0:
                lines.append(f"\n  iptables -L (excerpt):\n{r.stdout[:3000]}")
        return "\n".join(lines)

    @safe
    def cmd_wireguard(self, arg=""):
        if sys.platform == "win32":
            r = self._run("Get-NetIPInterface | Where-Object {$_.InterfaceAlias -like '*wireguard*' -or $_.InterfaceAlias -like '*wg*'}", timeout=10)
            return (f"[nd] WireGuard on Windows:\n{r.stdout}\n\n"
                    f"  Manage via the WireGuard app (https://www.wireguard.com/install/)\n"
                    f"  Configs live at: C:\\Program Files\\WireGuard\\Data\\Configurations\\\n"
                    f"  CLI: wg.exe show / wg.exe show all")
        if not self._which("wg"):
            return ("[nd] WireGuard tools not installed.\n"
                    "  Install: sudo apt install wireguard wireguard-tools")
        r = self._run(["sudo", "-n", "wg", "show"], timeout=5)
        if r.returncode != 0:
            r = self._run(["wg", "show"], timeout=5)
        return (f"[nd] WireGuard interfaces:\n{r.stdout or '(none active)'}\n\n"
                f"  Configs: /etc/wireguard/*.conf\n"
                f"  Start:   sudo wg-quick up <iface>\n"
                f"  Stop:    sudo wg-quick down <iface>\n"
                f"  Persistent: sudo systemctl enable wg-quick@<iface>")

    @safe
    def cmd_vpn_status(self, arg=""):
        lines = [f"[nd] VPN / tunnel interface check:"]
        if sys.platform == "win32":
            r = self._run("Get-VpnConnection | Select Name,ServerAddress,ConnectionStatus,AuthenticationMethod | Format-Table -AutoSize | Out-String -Width 200", timeout=10)
            lines.append("  Windows VPN connections:\n" + (r.stdout or "(none configured)"))
            # Tap/TUN interfaces
            r2 = self._run("Get-NetAdapter | Where-Object {$_.InterfaceDescription -like '*TAP*' -or $_.InterfaceDescription -like '*WireGuard*' -or $_.InterfaceDescription -like '*Tailscale*'} | Format-Table Name,Status,InterfaceDescription -AutoSize | Out-String -Width 200", timeout=10)
            if r2.stdout.strip():
                lines.append(f"\n  Tunnel adapters:\n{r2.stdout}")
            return "\n".join(lines)
        # Linux
        if self._which("ip"):
            r = self._run(["ip", "-brief", "link", "show", "type", "tun"], timeout=5)
            if r.stdout.strip():
                lines.append(f"  TUN interfaces:\n{r.stdout}")
            r = self._run(["ip", "-brief", "link", "show", "type", "wireguard"], timeout=5)
            if r.stdout.strip():
                lines.append(f"\n  WireGuard interfaces:\n{r.stdout}")
        # Tailscale
        if self._which("tailscale"):
            r = self._run(["tailscale", "status"], timeout=5)
            lines.append(f"\n  Tailscale:\n{r.stdout[:1500] or '(not running)'}")
        # OpenVPN
        r = self._run("pgrep -fa openvpn", timeout=5, shell=True)
        if r.stdout.strip():
            lines.append(f"\n  OpenVPN processes:\n{r.stdout}")
        return "\n".join(lines)
    @safe
    def cmd_explain(self, arg=""):  # v3.11: auto-injected cmd_explain
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            # Fallback if _shared.explain isn't importable
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{getattr(self, 'name', '?')}] {getattr(self, 'description', '')}"]
            lines.append("")
            lines.append("Commands:")
            for c in cmds:
                lines.append(f"  /{getattr(self, 'name', '?')} {c}")
            return "\n".join(lines)

```
