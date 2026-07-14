"""VM Module — Virtual machine detection AND management across backends.

Two distinct jobs:
  1. Detect whether *this* machine is itself running inside a hypervisor
     (heuristic, read-only — BIOS/DMI string fingerprinting).
  2. Manage *guest* VMs on backends actually installed here — Hyper-V
     (PowerShell cmdlets), VirtualBox (`VBoxManage`), and VMware Workstation
     (`vmrun`, list-only — it addresses VMs by .vmx path, not name, so full
     lifecycle control is out of scope here). All backend calls use
     list-form subprocess args, never a shell string — same discipline as
     every other subprocess-calling module in this codebase.

Start/stop only ever act on a VM that already exists — this module never
creates, deletes, or reconfigures a VM's hardware. That keeps it a SYSTEM-
tier "control what's already there" tool, not a DANGEROUS-tier
provisioning one.

Commands (~8):
  /vm detect                  Check for known hypervisor fingerprints (is THIS host a VM?)
  /vm backends                  Which VM backends are available on this host
  /vm list                        List guest VMs across every detected backend
  /vm status <name>                  Detailed info for one VM
  /vm start <name>                     Start an existing VM
  /vm stop <name> [force]                Stop a running VM (graceful by default)
  /vm snapshots <name>                     List snapshots for a VM (read-only)
  /vm explain                                How this module works
"""

import shutil
import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_HYPERVISOR_SIGNATURES = {
    "vmware": ["vmware", "vmw"],
    "virtualbox": ["virtualbox", "vbox"],
    "hyper-v": ["hyper-v", "microsoft corporation virtual machine", "hvm"],
    "qemu/kvm": ["qemu", "kvm"],
    "xen": ["xen"],
}


def _ps(script: str, timeout: int = 15):
    """Run a PowerShell command, list-form, no shell string interpolation of caller input."""
    return subprocess.run(["powershell", "-NoProfile", "-Command", script],
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")


class VmModule(Module):
    name = "vm"
    version = "1.1.0"
    description = "Virtual machine detection AND guest management across backends"
    author = "termaid"

    def on_load(self):
        for cmd in ["detect", "backends", "list", "status", "start", "stop", "snapshots", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    # ------------------------------------------------------------------ #
    # host-is-a-VM detection (unchanged behavior from v1)
    def _raw_signals(self) -> str:
        text = ""
        try:
            if sys.platform == "win32":
                r = _ps("(Get-CimInstance Win32_ComputerSystem).Manufacturer + ' ' + "
                        "(Get-CimInstance Win32_ComputerSystem).Model + ' ' + "
                        "(Get-CimInstance Win32_BIOS).Version", timeout=8)
                text = r.stdout.strip()
            else:
                for p in ("/sys/class/dmi/id/product_name", "/sys/class/dmi/id/sys_vendor",
                          "/sys/class/dmi/id/bios_vendor"):
                    fp = Path(p)
                    if fp.exists():
                        text += " " + fp.read_text(errors="replace").strip()
        except Exception:
            pass
        return text

    @safe
    def cmd_detect(self, arg=""):
        """Check for known hypervisor fingerprints (is THIS host a VM?)"""
        raw = self._raw_signals()
        low = raw.lower()
        matches = [name for name, sigs in _HYPERVISOR_SIGNATURES.items() if any(s in low for s in sigs)]
        lines = [f"[vm] Signal string: {raw or '(none captured)'}"]
        if matches:
            lines.append(f"[vm] This host is likely running inside: {', '.join(matches)}")
        else:
            lines.append("[vm] No known hypervisor fingerprint found — likely bare metal "
                        "(or an unrecognized/well-hidden hypervisor).")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # backend availability
    def _hyperv_available(self) -> bool:
        if sys.platform != "win32":
            return False
        try:
            r = _ps("Get-Command Get-VM -ErrorAction SilentlyContinue | Out-Null; "
                    "if ($?) { 'yes' } else { 'no' }", timeout=8)
            return "yes" in r.stdout
        except Exception:
            return False

    def _vbox_available(self) -> bool:
        return shutil.which("VBoxManage") is not None

    def _vmware_available(self) -> bool:
        return shutil.which("vmrun") is not None

    @safe
    def cmd_backends(self, arg=""):
        """Which VM backends are available on this host"""
        lines = ["[vm] Backends:"]
        lines.append(f"  {'OK' if self._hyperv_available() else '--'}    Hyper-V     "
                    f"{'(Windows Pro/Enterprise only, and the Hyper-V feature must be enabled)' if not self._hyperv_available() else ''}")
        lines.append(f"  {'OK' if self._vbox_available() else '--'}    VirtualBox  {shutil.which('VBoxManage') or ''}")
        lines.append(f"  {'OK' if self._vmware_available() else '--'}    VMware      "
                    f"{shutil.which('vmrun') or '(list-only support — vmrun addresses VMs by .vmx path)'}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Hyper-V backend
    def _hyperv_list(self):
        r = _ps("Get-VM | Select-Object Name,State,CPUUsage,MemoryAssigned | ConvertTo-Json -Compress")
        return r.stdout.strip() if r.returncode == 0 else ""

    def _hyperv_status(self, name: str):
        r = _ps(f"Get-VM -Name '{self._ps_escape(name)}' -ErrorAction SilentlyContinue | "
                "Select-Object Name,State,CPUUsage,MemoryAssigned,Uptime | Format-List")
        return r.stdout.strip()

    def _ps_escape(self, s: str) -> str:
        """Escape a value for embedding in a single-quoted PowerShell string literal
        (doubling ' is the only escape single-quoted strings recognize)."""
        return s.replace("'", "''")

    # ------------------------------------------------------------------ #
    # VirtualBox backend
    def _vbox_list(self):
        r = subprocess.run(["VBoxManage", "list", "vms"], capture_output=True, text=True, timeout=10)
        running = subprocess.run(["VBoxManage", "list", "runningvms"], capture_output=True, text=True, timeout=10)
        running_names = set()
        for line in (running.stdout or "").splitlines():
            if line.startswith('"'):
                running_names.add(line.split('"')[1])
        lines = []
        for line in (r.stdout or "").splitlines():
            if line.startswith('"'):
                vm_name = line.split('"')[1]
                state = "running" if vm_name in running_names else "stopped"
                lines.append(f"  {vm_name:30s} {state}  (VirtualBox)")
        return lines

    # ------------------------------------------------------------------ #
    @safe
    def cmd_list(self, arg=""):
        """List guest VMs across every detected backend"""
        lines = ["[vm] Guest VMs:"]
        found_any = False

        if self._hyperv_available():
            try:
                import json as _json
                raw = self._hyperv_list()
                data = _json.loads(raw) if raw else []
                if isinstance(data, dict):
                    data = [data]
                for vm in data:
                    found_any = True
                    mem_mb = (vm.get("MemoryAssigned") or 0) / (1024 * 1024)
                    lines.append(f"  {vm.get('Name', '?'):30s} {vm.get('State', '?'):10s} "
                                f"{mem_mb:.0f}MB  (Hyper-V)")
            except Exception:
                pass

        if self._vbox_available():
            vbox_lines = self._vbox_list()
            if vbox_lines:
                found_any = True
                lines.extend(vbox_lines)

        if self._vmware_available():
            try:
                r = subprocess.run(["vmrun", "list"], capture_output=True, text=True, timeout=10)
                vmx_paths = [l.strip() for l in r.stdout.splitlines() if l.strip().lower().endswith(".vmx")]
                for path in vmx_paths:
                    found_any = True
                    lines.append(f"  {path:50s} running  (VMware, use full .vmx path to control)")
            except Exception:
                pass

        if not found_any:
            return "[vm] No VMs found (or no VM backend is installed — see /vm backends)."
        return "\n".join(lines)

    @safe
    def cmd_status(self, arg=""):
        """Detailed info for one VM: /vm status <name>"""
        name = (arg or "").strip()
        if not name:
            return "[vm] Usage: /vm status <name>"

        if self._hyperv_available():
            out = self._hyperv_status(name)
            if out:
                return f"[vm] Hyper-V — {name}:\n{out}"

        if self._vbox_available():
            r = subprocess.run(["VBoxManage", "showvminfo", name, "--machinereadable"],
                                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                keep = [l for l in r.stdout.splitlines()
                        if l.split("=", 1)[0] in ("name", "VMState", "memory", "cpus", "ostype")]
                return f"[vm] VirtualBox — {name}:\n" + "\n".join(f"  {l}" for l in keep)

        return f"[vm] No VM named '{name}' found on any available backend."

    @safe
    def cmd_start(self, arg=""):
        """Start an existing VM: /vm start <name>"""
        name = (arg or "").strip()
        if not name:
            return "[vm] Usage: /vm start <name>"

        if self._hyperv_available():
            r = _ps(f"Start-VM -Name '{self._ps_escape(name)}' -ErrorAction Stop; 'ok'")
            if r.returncode == 0 and "ok" in r.stdout:
                return f"[vm] Started '{name}' (Hyper-V)"

        if self._vbox_available():
            r = subprocess.run(["VBoxManage", "startvm", name, "--type", "headless"],
                                capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                return f"[vm] Started '{name}' (VirtualBox, headless)"
            err = (r.stderr or r.stdout).strip()
        else:
            err = ""

        return f"[vm] Could not start '{name}'. {err or 'Check the name and /vm backends.'}"

    @safe
    def cmd_stop(self, arg=""):
        """Stop a running VM, graceful by default: /vm stop <name> [force]"""
        parts = (arg or "").split()
        if not parts:
            return "[vm] Usage: /vm stop <name> [force]"
        name = parts[0]
        force = len(parts) > 1 and parts[1].lower() == "force"

        if self._hyperv_available():
            script = f"Stop-VM -Name '{self._ps_escape(name)}'" + (" -Force" if force else "") + " -ErrorAction Stop; 'ok'"
            r = _ps(script)
            if r.returncode == 0 and "ok" in r.stdout:
                return f"[vm] Stopped '{name}' (Hyper-V{', forced' if force else ', graceful shutdown'})"

        if self._vbox_available():
            action = "poweroff" if force else "acpipowerbutton"
            r = subprocess.run(["VBoxManage", "controlvm", name, action],
                                capture_output=True, text=True, timeout=20)
            if r.returncode == 0:
                return f"[vm] Stopped '{name}' (VirtualBox{', forced' if force else ', ACPI shutdown signal'})"
            err = (r.stderr or r.stdout).strip()
        else:
            err = ""

        return f"[vm] Could not stop '{name}'. {err or 'Check the name and /vm backends.'}"

    @safe
    def cmd_snapshots(self, arg=""):
        """List snapshots for a VM (read-only): /vm snapshots <name>"""
        name = (arg or "").strip()
        if not name:
            return "[vm] Usage: /vm snapshots <name>"

        if self._hyperv_available():
            r = _ps(f"Get-VMSnapshot -VMName '{self._ps_escape(name)}' -ErrorAction SilentlyContinue | "
                    "Select-Object Name,CreationTime | Format-Table -AutoSize")
            if r.returncode == 0 and r.stdout.strip():
                return f"[vm] Hyper-V snapshots — {name}:\n{r.stdout.strip()}"

        if self._vbox_available():
            r = subprocess.run(["VBoxManage", "snapshot", name, "list"],
                                capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                return f"[vm] VirtualBox snapshots — {name}:\n{r.stdout.strip() or '(none)'}"

        return f"[vm] No snapshot info found for '{name}' (check the name and /vm backends)."

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
