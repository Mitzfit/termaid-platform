"""SelfMod Module — View, edit, and roll back TermAId's own module source. DANGEROUS tier.

Built with real write access, as explicitly requested — this is not a
read-only or narrowly-scoped variant. Scoped to files under `modules/`
specifically (the extension/plugin directory): it never touches
`backend/policy.py`, `backend/main.py`, or the core `termaid/` engine, so
it can't rewrite the security-tier system that gates this module itself.
That's a scope boundary, not a safety theater gesture — the operator
already has full filesystem access to every file in this repo regardless
of what this module does; the boundary just keeps "self-modification"
meaning "edit an extension module" rather than "edit the access-control
engine deciding whether this module should even be reachable."

Every write is backed up automatically first (see /backup for the general
version of this pattern) and syntax-validated with `compile()` before
being committed to disk — not because the operator's judgment needs a
safety net, but because a module left in a broken state fails every other
module's import scan too (`/manifest`, `/qa`, `/smart` all read the
modules/ directory directly).

Commands (~6):
  /selfmod list                              List module files (name + size)
  /selfmod view <module>                       Show a module's current source
  /selfmod diff <module> <new-content-path>      Unified diff vs. a proposed replacement
  /selfmod edit <module> <new-content-path> confirm  Apply the replacement (auto-backs-up, syntax-checks)
  /selfmod backups <module>                            List backups for a module
  /selfmod rollback <module> confirm                     Restore the most recent backup
  /selfmod explain                                          How this module works
"""

import difflib
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class SelfModModule(Module):
    name = "selfmod"
    version = "1.0.0"
    description = "View, edit, and roll back TermAId's own module source"
    author = "termaid"

    def on_load(self):
        for cmd in ["list", "view", "diff", "edit", "backups", "rollback", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        self._modules_dir = Path(__file__).resolve().parent.parent

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._backup_dir = data_dir / "selfmod_backups"
        self._backup_dir.mkdir(parents=True, exist_ok=True)

    def _target_path(self, module: str) -> Path:
        return self._modules_dir / module / "__init__.py"

    def _safe_module_name(self, module: str) -> bool:
        """Reject anything that isn't a plain module directory name — no path
        separators, no '..'. This is what actually keeps 'scoped to modules/'
        true; without it a module name like '../../backend/policy' would
        escape the intended directory entirely."""
        return module.isidentifier() or (module.replace("_", "").isalnum() and "/" not in module
                                          and "\\" not in module and ".." not in module)

    @safe
    def cmd_list(self, arg=""):
        """List module files (name + size)"""
        entries = []
        for p in sorted(self._modules_dir.iterdir()):
            init_py = p / "__init__.py"
            if p.is_dir() and init_py.is_file():
                entries.append((p.name, init_py.stat().st_size))
        if not entries:
            return "[selfmod] No modules found."
        lines = [f"[selfmod] {len(entries)} module(s):"]
        for name, size in entries:
            lines.append(f"  {name:20s} {size:,} bytes")
        return "\n".join(lines)

    @safe
    def cmd_view(self, arg=""):
        """Show a module's current source: /selfmod view <module>"""
        module = (arg or "").strip()
        if not module or not self._safe_module_name(module):
            return "[selfmod] Usage: /selfmod view <module> (plain module directory name only)"
        path = self._target_path(module)
        if not path.is_file():
            return f"[selfmod] No module named '{module}'"
        return f"[selfmod] {path}:\n\n{path.read_text(encoding='utf-8', errors='replace')}"

    @safe
    def cmd_diff(self, arg=""):
        """Unified diff vs. a proposed replacement: /selfmod diff <module> <new-content-path>"""
        parts = (arg or "").split(maxsplit=1)
        if len(parts) != 2:
            return "[selfmod] Usage: /selfmod diff <module> <new-content-path>"
        module, new_path_s = parts
        if not self._safe_module_name(module):
            return "[selfmod] Module name must be a plain directory name, no path separators."
        current_path = self._target_path(module)
        new_path = Path(new_path_s).expanduser()
        if not new_path.is_file():
            return f"[selfmod] New content file not found: {new_path}"
        current = current_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True) \
            if current_path.is_file() else []
        proposed = new_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        diff = list(difflib.unified_diff(current, proposed,
                                          fromfile=f"{module}/__init__.py (current)",
                                          tofile=f"{new_path.name} (proposed)"))
        if not diff:
            return "[selfmod] No differences."
        return "[selfmod] " + "".join(diff[:400])

    def _backup(self, module: str, path: Path) -> Path:
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup_path = self._backup_dir / f"{module}__{ts}.py"
        backup_path.write_text(path.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        return backup_path

    @safe
    def cmd_edit(self, arg=""):
        """Apply a replacement — auto-backs-up + syntax-checks first (confirms):
        /selfmod edit <module> <new-content-path> confirm"""
        parts = (arg or "").split()
        if len(parts) != 3 or parts[-1].lower() != "confirm":
            return "[selfmod] Usage: /selfmod edit <module> <new-content-path> confirm"
        module, new_path_s = parts[0], parts[1]
        if not self._safe_module_name(module):
            return "[selfmod] Module name must be a plain directory name, no path separators."
        new_path = Path(new_path_s).expanduser()
        if not new_path.is_file():
            return f"[selfmod] New content file not found: {new_path}"
        new_content = new_path.read_text(encoding="utf-8", errors="replace")

        try:
            compile(new_content, f"{module}/__init__.py", "exec")
        except SyntaxError as e:
            return f"[selfmod] Refusing to write — proposed content has a syntax error: {e}"

        target = self._target_path(module)
        backup_path = None
        if target.is_file():
            backup_path = self._backup(module, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(new_content, encoding="utf-8")

        msg = f"[selfmod] Wrote {target} ({len(new_content)} bytes)."
        if backup_path:
            msg += f" Backed up previous version to {backup_path.name}."
        msg += " Restart the backend to load the change (modules load once at startup)."
        return msg

    @safe
    def cmd_backups(self, arg=""):
        """List backups for a module: /selfmod backups <module>"""
        module = (arg or "").strip()
        if not module:
            return "[selfmod] Usage: /selfmod backups <module>"
        matches = sorted(self._backup_dir.glob(f"{module}__*.py"), reverse=True)
        if not matches:
            return f"[selfmod] No backups for '{module}'."
        lines = [f"[selfmod] {len(matches)} backup(s) for '{module}':"]
        for p in matches:
            lines.append(f"  {p.name}  ({p.stat().st_size:,} bytes)")
        return "\n".join(lines)

    @safe
    def cmd_rollback(self, arg=""):
        """Restore the most recent backup (confirms): /selfmod rollback <module> confirm"""
        parts = (arg or "").split()
        if len(parts) != 2 or parts[1].lower() != "confirm":
            return "[selfmod] Usage: /selfmod rollback <module> confirm"
        module = parts[0]
        if not self._safe_module_name(module):
            return "[selfmod] Module name must be a plain directory name, no path separators."
        matches = sorted(self._backup_dir.glob(f"{module}__*.py"), reverse=True)
        if not matches:
            return f"[selfmod] No backups for '{module}' to roll back to."
        latest = matches[0]
        content = latest.read_text(encoding="utf-8", errors="replace")
        try:
            compile(content, f"{module}/__init__.py", "exec")
        except SyntaxError as e:
            return f"[selfmod] Refusing to restore — backup itself has a syntax error: {e}"
        target = self._target_path(module)
        # Back up the current (about-to-be-replaced) state too, so a rollback is itself reversible.
        if target.is_file():
            self._backup(module, target)
        target.write_text(content, encoding="utf-8")
        return f"[selfmod] Restored '{module}' from {latest.name}. Restart the backend to load it."

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
