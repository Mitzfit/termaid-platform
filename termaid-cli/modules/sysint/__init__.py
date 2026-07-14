"""SysInt Module — System file integrity check + repair. DANGEROUS tier.

Windows: wraps `sfc /scannow` (checks + repairs protected system files in
one pass) and DISM for image-level repair. Linux: verifies installed
packages against their package manager's checksums (`debsums`/`rpm -Va`).
Checking is read-only observation of existing state; `repair` can replace
system files from the component store/cache, which is why it confirms —
on a system with a damaged component store this can occasionally make
things worse before better, and it's not instant.

Commands (~2):
  /sysint check           Check system file integrity (read-only)
  /sysint repair confirm     Repair damaged system files
  /sysint explain               How this module works
"""

import shutil
import subprocess
import sys
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class SysIntModule(Module):
    name = "sysint"
    version = "1.0.0"
    description = "System file integrity check + repair"
    author = "termaid"

    def on_load(self):
        for cmd in ["check", "repair", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_check(self, arg=""):
        """Check system file integrity (read-only)"""
        try:
            if sys.platform == "win32":
                r = subprocess.run(["dism", "/online", "/cleanup-image", "/scanhealth"],
                                    capture_output=True, text=True, timeout=300)
            elif shutil.which("debsums"):
                r = subprocess.run(["debsums", "-c"], capture_output=True, text=True, timeout=120)
            elif shutil.which("rpm"):
                r = subprocess.run(["rpm", "-Va"], capture_output=True, text=True, timeout=120)
            else:
                return "[sysint] No package integrity tool found (debsums/rpm) on this system."
        except subprocess.TimeoutExpired:
            return "[sysint] Check timed out — this can genuinely take a while on Windows; try again."
        except Exception as e:
            return f"[sysint] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[sysint] {out[:6000] or 'No issues found.'}"

    @safe
    def cmd_repair(self, arg=""):
        """Repair damaged system files (confirms): /sysint repair confirm"""
        if (arg or "").strip().lower() != "confirm":
            return "[sysint] This can take several minutes and replaces system files. Re-run as: /sysint repair confirm"
        try:
            if sys.platform == "win32":
                r = subprocess.run(["sfc", "/scannow"], capture_output=True, text=True, timeout=600)
            else:
                return "[sysint] Automated repair isn't available for this platform in this module — reinstall affected packages with your package manager instead."
        except subprocess.TimeoutExpired:
            return "[sysint] Repair timed out after 600s — it may still be running; check again shortly."
        except Exception as e:
            return f"[sysint] Failed: {e}"
        out = (r.stdout or r.stderr).strip()
        return f"[sysint] {out[:6000] or 'Repair finished.'}"

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
