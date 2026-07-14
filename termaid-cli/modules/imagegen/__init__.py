"""ImageGen Module — Gemini image generation.

Calls the Gemini API's generateContent endpoint with an image-capable model
and responseModalities including IMAGE, decodes the returned base64 image
data, and saves it to disk. Needs GEMINI_API_KEY or GOOGLE_API_KEY (the same
keys the rest of the platform's Gemini provider uses).

Commands (~7):
  /imagegen create <prompt> [path]   Generate an image, save to path (default: ./termaid-image.png)
  /imagegen model [name]               Show or set the image model to use
  /imagegen status                       Is a Gemini key configured?
  /imagegen history                        Recently generated images (this session, paths only)
  /imagegen explain                          How this module works
"""

import base64
import os
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


_DEFAULT_MODEL = "gemini-2.5-flash-image"


def _get_key() -> str | None:
    for k in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        v = os.environ.get(k, "").strip()
        if v:
            return v
    return None


class ImageGenModule(Module):
    name = "imagegen"
    version = "1.0.0"
    description = "Gemini Nano Banana image generation"
    author = "termaid"

    def on_load(self):
        for cmd in ["create", "model", "status", "history", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))
        self._model = _DEFAULT_MODEL
        self._history: list[str] = []

    @safe
    def cmd_create(self, arg=""):
        """Generate an image, save to path: /imagegen create <prompt> [path]"""
        key = _get_key()
        if not key:
            return "[imagegen] No GEMINI_API_KEY/GOOGLE_API_KEY configured."
        parts = (arg or "").rsplit(None, 1)
        if not arg.strip():
            return "[imagegen] Usage: /imagegen create <prompt> [output-path]"
        # Only treat the trailing token as a path if it looks like one (has an
        # extension) — otherwise the whole arg is the prompt.
        if len(parts) == 2 and Path(parts[1]).suffix.lower() in (".png", ".jpg", ".jpeg"):
            prompt, out_path = parts[0], parts[1]
        else:
            prompt, out_path = arg, "termaid-image.png"

        try:
            import httpx
        except ImportError:
            return "[imagegen] httpx not installed."

        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
              f"{self._model}:generateContent")
        headers = {"Content-Type": "application/json", "x-goog-api-key": key}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(url, json=payload, headers=headers)
        except Exception as e:
            return f"[imagegen] Request failed: {e}"
        if resp.status_code != 200:
            return f"[imagegen] API error {resp.status_code}: {resp.text[:300]}"

        data = resp.json()
        image_b64 = None
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    image_b64 = inline["data"]
                    break
            if image_b64:
                break
        if not image_b64:
            return f"[imagegen] No image data in response: {str(data)[:300]}"

        try:
            out = Path(out_path).expanduser()
            out.write_bytes(base64.b64decode(image_b64))
        except Exception as e:
            return f"[imagegen] Could not save image: {e}"
        self._history.append(str(out))
        return f"[imagegen] Saved to {out}"

    @safe
    def cmd_model(self, arg=""):
        """Show or set the image model to use"""
        name = (arg or "").strip()
        if not name:
            return f"[imagegen] Current model: {self._model}"
        self._model = name
        return f"[imagegen] Model set to {name}"

    @safe
    def cmd_status(self, arg=""):
        """Is a Gemini key configured?"""
        return f"[imagegen] API key: {'configured' if _get_key() else 'NOT configured'}  model: {self._model}"

    @safe
    def cmd_history(self, arg=""):
        """Recently generated images (this session, paths only)"""
        if not self._history:
            return "[imagegen] No images generated this session."
        return "[imagegen] Generated this session:\n" + "\n".join(f"  {p}" for p in self._history[-20:])

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
