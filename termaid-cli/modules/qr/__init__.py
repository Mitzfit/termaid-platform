"""QR Module — QR code generation for terminal and PNG export.

Uses the optional `qrcode` package (pip install qrcode[pil]) when available
for real QR generation; without it, commands return a clear install hint
rather than a broken/fake QR code.

Commands (~7):
  /qr generate <text>          Render a QR code as terminal ASCII art
  /qr save <path> <text>       Save a QR code as a PNG file
  /qr wifi <ssid> <password> [WPA|WEP|nopass]   WiFi-join QR payload
  /qr contact <name> <phone> [email]            vCard QR payload
  /qr url <url>                 QR code for a URL (validates scheme)
  /qr batch <path> <lines>       One PNG per line, numbered, into a folder
  /qr explain                   How this module works
"""

from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


def _qrcode_lib():
    try:
        import qrcode
        return qrcode
    except ImportError:
        return None


def _ascii_qr(text: str) -> str:
    qrcode = _qrcode_lib()
    if qrcode is None:
        return ("[qr] The 'qrcode' package isn't installed.\n"
                "     Install it with: pip install qrcode\n"
                f"     (payload was: {text})")
    qr = qrcode.QRCode(border=1)
    qr.add_data(text)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    lines = []
    for row in matrix:
        lines.append("".join("##" if cell else "  " for cell in row))
    return "\n".join(lines)


class QRModule(Module):
    name = "qr"
    version = "1.0.0"
    description = "QR code generation for terminal and PNG export"
    author = "termaid"

    def on_load(self):
        for cmd in ["generate", "save", "wifi", "contact", "url", "batch", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_generate(self, arg=""):
        """Render a QR code as terminal ASCII art"""
        text = arg or ""
        if not text:
            return "[qr] Usage: /qr generate <text>"
        return _ascii_qr(text)

    @safe
    def cmd_save(self, arg=""):
        """Save a QR code as a PNG file: /qr save <path> <text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[qr] Usage: /qr save <path.png> <text>"
        path, text = parts
        qrcode = _qrcode_lib()
        if qrcode is None:
            return "[qr] The 'qrcode' package isn't installed. pip install qrcode[pil]"
        try:
            img = qrcode.make(text)
            out = Path(path).expanduser()
            img.save(out)
            return f"[qr] Saved to {out}"
        except Exception as e:
            return f"[qr] Save failed: {e}"

    @safe
    def cmd_wifi(self, arg=""):
        """WiFi-join QR payload: /qr wifi <ssid> <password> [WPA|WEP|nopass]"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[qr] Usage: /qr wifi <ssid> <password> [WPA|WEP|nopass]"
        ssid, password = parts[0], parts[1]
        security = parts[2].upper() if len(parts) > 2 else "WPA"
        payload = f"WIFI:T:{security};S:{ssid};P:{password};;"
        return _ascii_qr(payload)

    @safe
    def cmd_contact(self, arg=""):
        """vCard QR payload: /qr contact <name> <phone> [email]"""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[qr] Usage: /qr contact <name> <phone> [email]"
        name, phone = parts[0], parts[1]
        email = parts[2] if len(parts) > 2 else ""
        vcard = f"BEGIN:VCARD\nVERSION:3.0\nN:{name}\nTEL:{phone}\n"
        if email:
            vcard += f"EMAIL:{email}\n"
        vcard += "END:VCARD"
        return _ascii_qr(vcard)

    @safe
    def cmd_url(self, arg=""):
        """QR code for a URL (validates scheme)"""
        url = (arg or "").strip()
        if not url:
            return "[qr] Usage: /qr url <url>"
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        return _ascii_qr(url)

    @safe
    def cmd_batch(self, arg=""):
        """One PNG per line, numbered, into a folder: /qr batch <dir> <multi-line text>"""
        parts = (arg or "").split(None, 1)
        if len(parts) != 2:
            return "[qr] Usage: /qr batch <output-dir> <newline-separated entries>"
        qrcode = _qrcode_lib()
        if qrcode is None:
            return "[qr] The 'qrcode' package isn't installed. pip install qrcode[pil]"
        out_dir, text = parts
        out_path = Path(out_dir).expanduser()
        out_path.mkdir(parents=True, exist_ok=True)
        lines = [l for l in text.splitlines() if l.strip()]
        if not lines:
            return "[qr] No entries to encode."
        for i, line in enumerate(lines, 1):
            qrcode.make(line).save(out_path / f"qr-{i:03d}.png")
        return f"[qr] Saved {len(lines)} QR code(s) to {out_path}"

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
