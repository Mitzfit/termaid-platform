"""PyEnv Module — Python interpreters, virtualenvs, packages, and tooling.

Works with the standard library's venv module directly (no dependency on the
external `pyenv` version-manager tool being installed) — creates/inspects
venvs and lists packages via `pip list` inside them.

Commands (~10):
  /pyenv version                Current Python version (running this backend)
  /pyenv list-venvs <root>        Find venv folders under a directory
  /pyenv create-venv <path>         Create a new virtualenv at path
  /pyenv packages [venv-path]         pip list (default: this backend's own venv)
  /pyenv which                          Path to the current Python interpreter
  /pyenv explain                          How this module works
"""

import subprocess
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _venv_python(venv_path: Path) -> Path:
    if sys.platform == "win32":
        return venv_path / "Scripts" / "python.exe"
    return venv_path / "bin" / "python"


class PyEnvModule(Module):
    name = "pyenv"
    version = "1.0.0"
    description = "Python interpreters, virtualenvs, packages, and tooling"
    author = "termaid"

    def on_load(self):
        for cmd in ["version", "list-venvs", "create-venv", "packages", "which", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    @safe
    def cmd_version(self, arg=""):
        """Current Python version (running this backend)"""
        return f"[pyenv] {sys.version}"

    @safe
    def cmd_list_venvs(self, arg=""):
        """Find venv folders under a directory: /pyenv list-venvs <root>"""
        root = Path((arg or ".").strip()).expanduser()
        if not root.is_dir():
            return f"[pyenv] Not a directory: {root}"
        found = []
        for p in root.rglob("pyvenv.cfg"):
            found.append(str(p.parent))
            if len(found) >= 50:
                break
        if not found:
            return f"[pyenv] No venvs found under {root}"
        return f"[pyenv] {len(found)} venv(s):\n" + "\n".join(f"  {f}" for f in found)

    @safe
    def cmd_create_venv(self, arg=""):
        """Create a new virtualenv at path"""
        path = (arg or "").strip()
        if not path:
            return "[pyenv] Usage: /pyenv create-venv <path>"
        p = Path(path).expanduser()
        if p.exists():
            return f"[pyenv] Already exists: {p}"
        try:
            r = subprocess.run([sys.executable, "-m", "venv", str(p)],
                              capture_output=True, text=True, timeout=60)
        except Exception as e:
            return f"[pyenv] Failed: {e}"
        if r.returncode != 0:
            return f"[pyenv] Failed: {r.stderr.strip()}"
        return f"[pyenv] Created venv at {p}"

    @safe
    def cmd_packages(self, arg=""):
        """pip list (default: this backend's own venv)"""
        venv_path = (arg or "").strip()
        python_exe = _venv_python(Path(venv_path)) if venv_path else Path(sys.executable)
        if venv_path and not python_exe.exists():
            return f"[pyenv] No Python found in venv: {venv_path}"
        try:
            r = subprocess.run([str(python_exe), "-m", "pip", "list"],
                              capture_output=True, text=True, timeout=30)
        except Exception as e:
            return f"[pyenv] Failed: {e}"
        return r.stdout.strip() or r.stderr.strip()

    @safe
    def cmd_which(self, arg=""):
        """Path to the current Python interpreter"""
        return f"[pyenv] {sys.executable}"

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
