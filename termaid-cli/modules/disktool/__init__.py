"""DiskTool Module — Disk/partition management. DANGEROUS tier.

Listing disks and partitions is read-only. `format` is the single most
destructive command in this entire codebase — it erases everything on a
partition, irreversibly, in seconds. It requires an explicit acknowledgement
string beyond the usual "confirm", the same escalated pattern used for
/fastboot's flash/unlock, because a partition letter or index typo here has
no undo.

Commands (~3):
  /disktool list-disks                    List physical disks
  /disktool list-partitions <disk>          List partitions on a disk
  /disktool format <partition> I-UNDERSTAND-THIS-ERASES-ALL-DATA
                                               Format a partition (irreversible)
  /disktool explain                             How this module works
"""

import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_FORMAT_ACK = "I-UNDERSTAND-THIS-ERASES-ALL-DATA"


class DiskToolModule(Module):
    name = "disktool"
    version = "1.0.0"
    description = "Disk/partition management (format is irreversible — extra ack required)"
    author = "termaid"

    def on_load(self):
        for cmd in ["list-disks", "list-partitions", "format", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_list_disks(self, arg=""):
        """List physical disks"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     "Get-Disk | Select-Object Number,FriendlyName,Size,PartitionStyle,OperationalStatus | "
                     "Format-Table -AutoSize"],
                    capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(["lsblk", "-d", "-o", "NAME,SIZE,MODEL,TYPE"], capture_output=True,
                                    text=True, timeout=10)
        except Exception as e:
            return f"[disktool] Failed: {e}"
        return f"[disktool] {(r.stdout or r.stderr).strip()}"

    @safe
    def cmd_list_partitions(self, arg=""):
        """List partitions on a disk: /disktool list-partitions <disk>"""
        disk = (arg or "").strip()
        if not disk:
            return "[disktool] Usage: /disktool list-partitions <disk> (disk number on Windows, device on Linux)"
        if sys.platform == "win32" and not disk.isdigit():
            # Get-Partition -DiskNumber only ever takes a plain integer — embedding it bare into a
            # PowerShell -Command string with no validation was a real injection vector. Reject
            # anything that isn't purely digits before it ever reaches the shell.
            return f"[disktool] Disk number must be a plain integer, got '{disk}'."
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Get-Partition -DiskNumber {disk} -ErrorAction SilentlyContinue | "
                     "Select-Object PartitionNumber,DriveLetter,Size,Type | Format-Table -AutoSize"],
                    capture_output=True, text=True, timeout=15, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(["lsblk", disk, "-o", "NAME,SIZE,FSTYPE,MOUNTPOINT"],
                                    capture_output=True, text=True, timeout=10)
        except Exception as e:
            return f"[disktool] Failed: {e}"
        return f"[disktool] {(r.stdout or r.stderr).strip()}"

    @safe
    def cmd_format(self, arg=""):
        """Format a partition — irreversible (extra ack required):
        /disktool format <partition> I-UNDERSTAND-THIS-ERASES-ALL-DATA"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1] != _FORMAT_ACK:
            return (f"[disktool] This ERASES ALL DATA on the partition, irreversibly. "
                    f"Re-run as: /disktool format <partition> {_FORMAT_ACK}")
        partition = parts[0]
        drive_letter = partition.rstrip(":")
        if sys.platform == "win32" and not (len(drive_letter) == 1 and drive_letter.isalpha()):
            # Format-Volume -DriveLetter takes exactly one letter — same reasoning as list-partitions
            # above: validate the narrow shape a bare (unquoted) interpolation actually needs, rather
            # than trusting it, since this one is also the single most destructive command here.
            return f"[disktool] Drive letter must be a single letter (e.g. 'D' or 'D:'), got '{partition}'."
        try:
            if sys.platform == "win32":
                r = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"Format-Volume -DriveLetter {drive_letter} -FileSystem NTFS -Confirm:$false -Force"],
                    capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(["mkfs.ext4", "-F", partition], capture_output=True,
                                    text=True, timeout=120)
        except subprocess.TimeoutExpired:
            return "[disktool] Format timed out after 120s."
        except Exception as e:
            return f"[disktool] Failed: {e}"
        return f"[disktool] {(r.stdout or r.stderr).strip() or f'Formatted {partition}'}"

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
