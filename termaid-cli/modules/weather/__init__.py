"""Weather Module — Weather and forecast via wttr.in (no API key needed).

wttr.in serves plain-text weather reports, so this module just formats HTTP
requests against it. Set a default location once with /weather set-location.

Commands (~9):
  /weather current [place]        Current conditions
  /weather forecast [place]       3-day forecast (short)
  /weather hourly [place]         Hourly breakdown for today
  /weather moon                   Moon phase
  /weather set-location <place>   Remember a default location
  /weather units <c|f>            Set metric (c) or imperial (f) default
  /weather compare <a> <b>        Current conditions side by side
  /weather explain                How this module works
"""

import os
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class WeatherModule(Module):
    name = "weather"
    version = "1.0.0"
    description = "Weather and forecast via wttr.in (no API key needed)"
    author = "termaid"

    def on_load(self):
        cmds = ["current", "forecast", "hourly", "moon",
                "set-location", "units", "compare", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "weather"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._dir / "config.json"
        self._config = self._load_config()

    def _load_config(self) -> dict:
        import json
        if self._config_file.exists():
            try:
                return json.loads(self._config_file.read_text())
            except Exception:
                pass
        return {"location": "", "units": "m"}  # m=metric, u=imperial

    def _save_config(self) -> None:
        import json
        self._config_file.write_text(json.dumps(self._config, indent=2))

    def _fetch(self, place: str, fmt_path: str = "") -> str:
        try:
            import httpx
        except ImportError:
            return "[weather] httpx not installed — cannot reach wttr.in"
        place = (place or self._config.get("location") or "").strip()
        units_flag = f"?{self._config.get('units', 'm')}"
        url = f"https://wttr.in/{place}{fmt_path}{units_flag}"
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.get(url, headers={"User-Agent": "curl/8"})
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            return f"[weather] Request failed: {e}"

    @safe
    def cmd_current(self, arg=""):
        """Current conditions"""
        return self._fetch(arg, "?format=%l:+%C+%t+(feels+%f),+wind+%w,+humidity+%h")

    @safe
    def cmd_forecast(self, arg=""):
        """3-day forecast (short)"""
        return self._fetch(arg, "?0")

    @safe
    def cmd_hourly(self, arg=""):
        """Hourly breakdown for today"""
        return self._fetch(arg, "?F")

    @safe
    def cmd_moon(self, arg=""):
        """Moon phase"""
        return self._fetch("Moon", "")

    @safe
    def cmd_set_location(self, arg=""):
        """Remember a default location"""
        place = (arg or "").strip()
        if not place:
            cur = self._config.get("location") or "(none set)"
            return f"[weather] Usage: /weather set-location <place>\n  Current default: {cur}"
        self._config["location"] = place
        self._save_config()
        return f"[weather] Default location set to '{place}'"

    @safe
    def cmd_units(self, arg=""):
        """Set metric (c) or imperial (f) default"""
        u = (arg or "").strip().lower()
        if u not in ("c", "f", "m", "u"):
            return "[weather] Usage: /weather units <c|f>  (metric or imperial)"
        self._config["units"] = "m" if u in ("c", "m") else "u"
        self._save_config()
        return f"[weather] Units set to {'metric' if self._config['units'] == 'm' else 'imperial'}"

    @safe
    def cmd_compare(self, arg=""):
        """Current conditions side by side: /weather compare <place-a> <place-b>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[weather] Usage: /weather compare <place-a> <place-b>"
        a, b = parts
        fmt = "?format=%l:+%C+%t"
        return f"{self._fetch(a, fmt)}\n{self._fetch(b, fmt)}"

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
