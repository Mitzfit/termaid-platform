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
                return (f"[nt] OK {host}:{port} reachable  ({elapsed:.1f} ms)\n"
                        f"     Service: {COMMON_PORTS.get(port, 'unknown')}")
        except socket.timeout:
            return f"[nt] FAIL {host}:{port} timeout (5s)"
        except Exception as e:
            return f"[nt] FAIL {host}:{port} failed: {e}"

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
            return f"[nt] Max successful payload: {best} bytes  =>  MTU ~ {best + 28} bytes"
        return "[nt] Could not determine MTU."

    @safe
    def cmd_latency(self, arg=""):
        parts = (arg or "").split()
        if not parts: return "[nt] Usage: /nt latency <host> [count]"
        host = parts[0]
        try: count = int(parts[1]) if len(parts) > 1 else 10
        except Exception: count = 10
        # Cap regardless of what was requested: each iteration blocks this request for
        # up to ~5.2s (ping timeout + inter-sample delay), and this runs on the same
        # single-threaded event loop every other request shares — an uncapped count is
        # an attacker/typo-controlled hang, not just a slow response.
        count = max(1, min(count, 30))
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
