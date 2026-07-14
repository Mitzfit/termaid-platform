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
                    "score", "public_ip", "report", "watch", "listening", "explain"]:
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
        lines = ["=" * 55, "  NETWORK OVERVIEW", "=" * 55]

        # Interfaces summary
        lines.append("\n--- Interfaces ---")
        interfaces = self._get_interfaces()
        active = [i for i in interfaces if i.get("status") == "up"]
        lines.append(f"  Total:   {len(interfaces)}")
        lines.append(f"  Active:  {len(active)}")
        for iface in active[:5]:
            lines.append(f"  - {iface.get('name', '?'):15s} {iface.get('ip', '?'):15s}")

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
        lines = ["=== Interfaces ===\n"]
        for iface in self._get_interfaces():
            status_icon = "up" if iface.get("status") == "up" else "down"
            lines.append(f"  [{status_icon}] {iface.get('name', '?')}")
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
        lines = ["=== Active Connections ===\n"]
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
        lines = ["=== Listening Ports ===\n"]
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

        lines = [f"=== Port scan: {host} ===\n"]
        open_ports = []
        for port, name in common_ports.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.5)
                result = s.connect_ex((host, port))
                s.close()
                if result == 0:
                    open_ports.append((port, name))
                    lines.append(f"  {port:5d}/tcp  OPEN   ({name})")
            except Exception:
                pass

        if not open_ports:
            lines.append("  No common ports open, or host unreachable")
        else:
            lines.append(f"\n  Found {len(open_ports)} open port(s)")
        return "\n".join(lines)

    _SUBNET_RE = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$")

    @safe
    def cmd_scan(self, args):
        """Scan local subnet. Usage: /net.scan [subnet]"""
        subnet = args.strip() if args.strip() else self._get_local_subnet()
        if not subnet:
            return "Could not detect local subnet. Usage: /net.scan 192.168.1.0/24"
        if not self._SUBNET_RE.match(subnet):
            return f"[net.scan] Invalid subnet '{subnet}'. Expected IPv4 or CIDR, e.g. 192.168.1.0/24"

        lines = [f"=== Subnet scan: {subnet} ===\n"]

        # Try nmap first (fastest)
        import shutil
        if shutil.which("nmap"):
            print("Running nmap quick scan...")
            r = self._run(["nmap", "-sn", "-T4", subnet], timeout=60)
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
                lines.append(f"  UP  {target}")
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
        lines = ["=== DNS ===\n"]
        servers = self._get_dns_servers()
        lines.append("Resolvers:")
        for s in servers:
            lines.append(f"  - {s}")

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
                    lines.append(f"  -> {ip}")
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
        lines = ["=== Gateway ===\n"]
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
        lines = ["=== Public IP ===\n"]
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
        lines = ["=== Speed Test ===\n"]

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
        lines = ["=== Threat Assessment ===\n"]
        issues = []

        # Check 1: Suspicious listening ports (unexpected services)
        suspicious = self._check_suspicious_ports()
        if suspicious:
            lines.append("Suspicious listening ports:")
            for item in suspicious:
                lines.append(f"   - {item}")
                issues.append(("high", item))

        # Check 2: Public services exposed
        exposed = self._check_public_exposure()
        if exposed:
            lines.append("\nServices bound to 0.0.0.0 (public):")
            for item in exposed[:10]:
                lines.append(f"   - {item}")
                issues.append(("medium", item))

        # Check 3: DNS hygiene (using public/known servers?)
        dns = self._get_dns_servers()
        safe_dns = {"1.1.1.1", "1.0.0.1", "8.8.8.8", "8.8.4.4", "9.9.9.9"}
        unknown_dns = [d for d in dns if d not in safe_dns and not d.startswith("192.168.")
                       and not d.startswith("10.") and not d.startswith("172.")]
        if unknown_dns:
            lines.append(f"\nUnknown DNS servers: {', '.join(unknown_dns)}")
            issues.append(("low", "Non-standard DNS"))

        # Check 4: Gateway reachability
        gw = self._get_gateway()
        if not gw.get("gateway"):
            lines.append("\nNo default gateway detected")
            issues.append(("high", "No gateway"))
        elif gw.get("latency", 0) > 100:
            lines.append(f"\nHigh gateway latency: {gw['latency']:.0f} ms")
            issues.append(("low", "High latency"))

        # Check 5: Active connections count
        conns = self._count_connections()
        if conns.get("total", 0) > 100:
            lines.append(f"\nHigh number of connections: {conns['total']}")
            issues.append(("low", "Many connections"))

        # Summary
        if not issues:
            lines.append("No obvious threats detected")
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
        lines = ["=== Network Effectiveness Score ===\n"]

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
            "  FULL NETWORK REPORT",
            f"  {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "=" * 55,
        ]
        for title, content in sections:
            out.append(f"\n{'-' * 55}")
            out.append(f"  {title}")
            out.append(f"{'-' * 55}")
            out.append(content)

        report = "\n".join(out)
        fp = self._dir / f"report_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        fp.write_text(report, encoding="utf-8")
        return report + f"\n\nSaved: {fp}"

    @safe
    def cmd_watch(self, args):
        """Connection delta over a real interval, without blocking the server.

        Usage: /net.watch          (takes the 'before' snapshot)
               /net.watch finish   (call this after waiting yourself, shows the delta)

        Used to be a single call with a blocking time.sleep(5) inside it — that
        froze the whole backend's single-threaded event loop for every connected
        user for 5 seconds on every single call, not just the requester. Splitting
        it into two non-blocking calls moves the waiting into your own time
        instead of the shared server's.
        """
        if (args or "").strip().lower() == "finish":
            if not getattr(self, "_watch_before", None):
                return "[net] No /net.watch sample in progress. Run /net.watch first."
            before, started = self._watch_before, self._watch_started
            after = self._count_connections()
            elapsed = time.time() - started
            self._watch_before = None
            lines = [f"=== Snapshot delta ({elapsed:.1f}s) ===\n"]
            lines.append(f"  Connections:  {before['total']} -> {after['total']}  ({after['total'] - before['total']:+d})")
            lines.append(f"  Listening:    {before['listening']} -> {after['listening']}  ({after['listening'] - before['listening']:+d})")
            return "\n".join(lines)

        self._watch_before = self._count_connections()
        self._watch_started = time.time()
        return "[net] Baseline captured. Wait as long as you like, then run: /net.watch finish"
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
