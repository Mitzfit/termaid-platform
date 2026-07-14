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
            bar = "#" * n
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

  --- TEMPORARY (current session) ---

    sudo ethtool -s eth0 speed 1000 duplex full autoneg off
    sudo ethtool -s eth0 autoneg on              # back to auto

  --- PERSISTENT ---

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
