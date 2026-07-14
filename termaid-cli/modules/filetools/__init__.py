"""FileTools Module — File operations: hash, compress, analyze.

Encryption is intentionally left out: a module with no key-recovery/escrow
story that can encrypt a file is a good way to accidentally lock yourself
out of your own data. Use /crypto (once built, DANGEROUS-tier, opt-in) for
that with proper key management, not this module.

Commands (~9):
  /filetools hash <path> [algo]      File hash (default sha256; also md5, sha1, sha512)
  /filetools size <path>                Human-readable file size
  /filetools compress <path> [out.zip]     Zip a file or directory
  /filetools decompress <path> [outdir]      Extract a zip archive
  /filetools analyze <path>                    Basic file analysis (type guess, line/byte count)
  /filetools explain                             How this module works
"""

import hashlib
import mimetypes
import zipfile
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_HASH_ALGOS = {"md5", "sha1", "sha256", "sha512"}


def _human(n: int) -> str:
    f = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if f < 1024 or unit == "TB":
            return f"{f:.1f}{unit}" if unit != "B" else f"{int(f)}B"
        f /= 1024
    return f"{f:.1f}TB"


class FileToolsModule(Module):
    name = "filetools"
    version = "1.0.0"
    description = "File operations: hash, compress, encrypt, analyze"
    author = "termaid"

    def on_load(self):
        for cmd in ["hash", "size", "compress", "decompress", "analyze", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_hash(self, arg=""):
        """File hash (default sha256): /filetools hash <path> [algo]"""
        parts = (arg or "").split()
        if not parts:
            return "[filetools] Usage: /filetools hash <path> [md5|sha1|sha256|sha512]"
        path = parts[0]
        algo = parts[1].lower() if len(parts) > 1 else "sha256"
        if algo not in _HASH_ALGOS:
            return f"[filetools] Unknown algorithm '{algo}'. Choose from: {', '.join(sorted(_HASH_ALGOS))}"
        p = Path(path).expanduser()
        if not p.is_file():
            return f"[filetools] Not a file: {p}"
        h = hashlib.new(algo)
        try:
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    h.update(chunk)
        except Exception as e:
            return f"[filetools] Read failed: {e}"
        return f"[filetools] {algo}({p.name}) = {h.hexdigest()}"

    @safe
    def cmd_size(self, arg=""):
        """Human-readable file size"""
        path = (arg or "").strip()
        if not path:
            return "[filetools] Usage: /filetools size <path>"
        p = Path(path).expanduser()
        if not p.exists():
            return f"[filetools] Not found: {p}"
        size = p.stat().st_size if p.is_file() else sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return f"[filetools] {p}: {_human(size)} ({size:,} bytes)"

    @safe
    def cmd_compress(self, arg=""):
        """Zip a file or directory: /filetools compress <path> [out.zip]"""
        parts = (arg or "").split()
        if not parts:
            return "[filetools] Usage: /filetools compress <path> [out.zip]"
        src = Path(parts[0]).expanduser()
        if not src.exists():
            return f"[filetools] Not found: {src}"
        out = Path(parts[1]).expanduser() if len(parts) > 1 else src.with_suffix(".zip")
        try:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                if src.is_file():
                    zf.write(src, src.name)
                else:
                    for f in src.rglob("*"):
                        if f.is_file():
                            zf.write(f, f.relative_to(src.parent))
        except Exception as e:
            return f"[filetools] Compress failed: {e}"
        return f"[filetools] Created {out} ({_human(out.stat().st_size)})"

    @safe
    def cmd_decompress(self, arg=""):
        """Extract a zip archive: /filetools decompress <path> [outdir]"""
        parts = (arg or "").split()
        if not parts:
            return "[filetools] Usage: /filetools decompress <path.zip> [outdir]"
        src = Path(parts[0]).expanduser()
        if not src.is_file():
            return f"[filetools] Not found: {src}"
        outdir = Path(parts[1]).expanduser() if len(parts) > 1 else src.with_suffix("")
        try:
            with zipfile.ZipFile(src) as zf:
                zf.extractall(outdir)
                n = len(zf.namelist())
        except Exception as e:
            return f"[filetools] Extract failed: {e}"
        return f"[filetools] Extracted {n} item(s) to {outdir}"

    @safe
    def cmd_analyze(self, arg=""):
        """Basic file analysis (type guess, line/byte count)"""
        path = (arg or "").strip()
        if not path:
            return "[filetools] Usage: /filetools analyze <path>"
        p = Path(path).expanduser()
        if not p.is_file():
            return f"[filetools] Not a file: {p}"
        mime, _ = mimetypes.guess_type(str(p))
        size = p.stat().st_size
        lines = [f"[filetools] {p.name}:",
                f"  Size:      {_human(size)} ({size:,} bytes)",
                f"  Guessed type: {mime or 'unknown'}"]
        if mime and mime.startswith("text"):
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
                lines.append(f"  Lines:     {len(text.splitlines())}")
                lines.append(f"  Words:     {len(text.split())}")
            except Exception:
                pass
        return "\n".join(lines)

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
