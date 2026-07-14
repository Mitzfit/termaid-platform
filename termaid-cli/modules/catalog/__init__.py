"""Catalog Module — Discover modules and commands.

With 50+ modules and 800+ commands, finding what you need matters.
This module enumerates everything, fuzz-searches, and categorizes.

Commands (10):
  /catalog modules           All modules with descriptions
  /catalog commands          All commands (long)
  /catalog search <query>    Fuzzy search across module + command names + descriptions
  /catalog stats             Module / command counts
  /catalog by-platform <p>   Filter to commands likely to work on platform (win/linux/mac)
  /catalog by-category <c>   Group commands by category
  /catalog categories        List defined categories
  /catalog cheatsheet        One-page command reference
  /catalog module <name>     Detail for one module
  /catalog freshly-added     Recently added modules (by mtime)
"""

import importlib
import json
import os
import re
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except Exception:
    def safe(fn): return fn


# Manually-curated categories (module -> tags)
CATEGORIES = {
    "ai":         ["ai", "llm"],
    "auth":       ["auth"],
    "autoconfig": ["config"],
    "bench":      ["perf"],
    "bootmgr":    ["boot"],
    "clip":       ["productivity"],
    "cortex":     ["ai", "memory"],
    "crypto":     ["security"],
    "dbkeys":     ["dev"],
    "debug":      ["mobile", "dev"],
    "devdetect":  ["dev"],
    "devicescan": ["mobile", "hardware"],
    "diskspace":  ["disk"],
    "disktool":   ["disk", "hardware"],
    "dualboot":   ["boot", "os"],
    "env":        ["dev", "config"],
    "errors":     ["meta"],
    "fastboot":   ["mobile"],
    "filetools":  ["fs"],
    "firmware":   ["mobile"],
    "fsscan":     ["fs"],
    "fwown":      ["firmware", "hardware"],
    "git":        ["dev"],
    "hardware":   ["hardware"],
    "health":     ["meta"],
    "imagegen":   ["ai"],
    "learn":      ["meta", "knowledge"],
    "learner":    ["ai", "memory"],
    "manifest":   ["meta"],
    "markets":    ["finance"],
    "multiboot":  ["mobile"],
    "netscan":    ["network", "security"],
    "nettools":   ["network"],
    "netdeep":    ["network"],
    "notes":      ["productivity"],
    "paper":      ["finance"],
    "perftune":   ["perf"],
    "privesc":    ["security"],
    "proj":       ["dev"],
    "pyenv":      ["dev", "python"],
    "recovery":   ["disk", "os"],
    "rootguide":  ["mobile"],
    "router":     ["ai", "config"],
    "sandbox":    ["meta"],
    "sec":        ["security"],
    "selfmod":    ["meta"],
    "selftest":   ["meta"],
    "serve":      ["network", "dev"],
    "sysint":     ["security", "perf"],
    "sysmonitor": ["perf"],
    "uefi":       ["firmware", "boot"],
    "usbdeep":    ["hardware"],
    "vm":         ["dev"],
    "wsl":        ["os", "dev"],
}

# Platform compatibility hints
WINDOWS_ONLY = {"bootmgr": ["winbm_info", "winbm_entries", "winbm_default", "winbm_fix"],
                "wsl": ["all"],
                "fastboot": ["windows_only"]}
LINUX_ONLY = {"perftune": ["cpu_governor", "cpu_governor_set"],
              "bootmgr": ["grub_info", "grub_entries", "sdboot_info"]}


class CatalogModule(Module):
    name = "catalog"
    version = "1.0.0"
    description = "Discover modules and commands across TermAId"
    author = "termaid"

    def on_load(self):
        cmds = ["modules", "commands", "search", "stats", "by-platform",
                "by-category", "categories", "cheatsheet", "module", "freshly-added", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "catalog"
        self._dir.mkdir(parents=True, exist_ok=True)
        # Find modules dir
        self._modules_dir = self._find_modules_dir()
        self._cache = None

    def _find_modules_dir(self):
        # Look for it relative to this file
        here = Path(__file__).resolve().parent
        # We're in modules/catalog; modules/ is parent
        return here.parent

    def _scan_modules(self, force=False):
        if self._cache and not force:
            return self._cache
        result = []
        if not self._modules_dir.exists():
            return result
        for entry in sorted(self._modules_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue
            init_py = entry / "__init__.py"
            if not init_py.exists():
                continue
            try:
                text = init_py.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            # Extract docstring
            doc_match = re.match(r'^"""(.*?)"""', text, re.S)
            docstring = doc_match.group(1).strip() if doc_match else ""
            # First line of docstring is summary
            summary = docstring.splitlines()[0].strip() if docstring else ""
            # Extract module name (class attribute)
            name_match = re.search(r'name\s*=\s*"([^"]+)"', text)
            mod_alias = name_match.group(1) if name_match else entry.name
            # Extract version
            ver_match = re.search(r'version\s*=\s*"([^"]+)"', text)
            version = ver_match.group(1) if ver_match else "?"
            # Extract description (class attribute)
            desc_match = re.search(r'description\s*=\s*"([^"]+)"', text)
            description = desc_match.group(1) if desc_match else summary
            # Find all cmd_ methods
            cmds = re.findall(r"def\s+cmd_(\w+)\s*\(", text)
            # Normalize for display (underscore -> hyphen)
            cmd_names = [c.replace("_", "-") for c in cmds]
            # Extract per-command summary from docstring if present
            cmd_descriptions = {}
            for line in docstring.splitlines():
                # match lines like:  /xxx command  description
                m = re.match(r"\s*/(\S+)\s+([\w\-<>\[\]\s]+?)\s{2,}(.+)", line)
                if m:
                    cmd_name = m.group(2).strip().split()[0]
                    cmd_descriptions[cmd_name] = m.group(3).strip()
            result.append({
                "folder": entry.name,
                "name": mod_alias,
                "version": version,
                "description": description,
                "commands": cmd_names,
                "command_count": len(cmd_names),
                "cmd_descriptions": cmd_descriptions,
                "categories": CATEGORIES.get(entry.name, []),
                "mtime": entry.stat().st_mtime,
            })
        self._cache = result
        return result

    # ---------- commands ----------

    @safe
    def cmd_modules(self, arg=""):
        """List all modules with descriptions"""
        mods = self._scan_modules()
        lines = [f"[catalog] {len(mods)} modules:"]
        for m in mods:
            cats = " ".join(f"#{c}" for c in m["categories"]) if m["categories"] else ""
            lines.append(f"\n  /{m['name']:<10s} v{m['version']:<6s} ({m['command_count']:>2d} cmds)  {cats}")
            lines.append(f"      {m['description']}")
        return "\n".join(lines)

    @safe
    def cmd_commands(self, arg=""):
        """List all commands (long)"""
        mods = self._scan_modules()
        total = sum(m["command_count"] for m in mods)
        lines = [f"[catalog] {total} commands across {len(mods)} modules:"]
        for m in mods:
            if not m["commands"]: continue
            lines.append(f"\n  /{m['name']}:")
            for cmd in m["commands"]:
                desc = m["cmd_descriptions"].get(cmd, "")
                if desc:
                    lines.append(f"    /{m['name']} {cmd:<22s}  {desc[:80]}")
                else:
                    lines.append(f"    /{m['name']} {cmd}")
        return "\n".join(lines)

    @safe
    def cmd_search(self, arg=""):
        """Fuzzy search: /catalog search <query>"""
        q = (arg or "").strip().lower()
        if not q:
            return "[catalog] Usage: /catalog search <query>"
        mods = self._scan_modules()
        hits = []
        for m in mods:
            score = 0
            matches = []
            # Module name
            if q in m["name"].lower():
                score += 10
                matches.append("name")
            # Module description
            if q in m["description"].lower():
                score += 5
                matches.append("desc")
            # Categories
            for c in m["categories"]:
                if q in c:
                    score += 3
            # Commands
            cmd_hits = [c for c in m["commands"] if q in c.lower()]
            score += len(cmd_hits) * 4
            # Command descriptions
            for cmd, desc in m["cmd_descriptions"].items():
                if q in desc.lower():
                    score += 2
                    if cmd not in cmd_hits: cmd_hits.append(cmd)
            if score > 0:
                hits.append((score, m, cmd_hits))
        hits.sort(key=lambda x: -x[0])
        if not hits:
            return f"[catalog] No matches for '{q}'"
        lines = [f"[catalog] {len(hits)} match(es) for '{q}':"]
        for score, m, cmd_hits in hits[:15]:
            lines.append(f"\n  /{m['name']:<10s} (score {score})  {m['description']}")
            for c in cmd_hits[:5]:
                desc = m['cmd_descriptions'].get(c, '')
                lines.append(f"      /{m['name']} {c}  {desc[:60]}")
        return "\n".join(lines)

    @safe
    def cmd_stats(self, arg=""):
        """Module / command statistics"""
        mods = self._scan_modules()
        total_cmds = sum(m["command_count"] for m in mods)
        cat_counts = {}
        for m in mods:
            for c in m["categories"]:
                cat_counts[c] = cat_counts.get(c, 0) + 1
        lines = [
            f"[catalog] TermAId statistics:",
            f"  Modules:            {len(mods)}",
            f"  Total commands:     {total_cmds}",
            f"  Avg cmds/module:    {total_cmds / max(len(mods),1):.1f}",
            f"  Largest module:     /{max(mods, key=lambda m: m['command_count'])['name']} "
            f"({max(m['command_count'] for m in mods)} cmds)",
            f"  Smallest module:    /{min(mods, key=lambda m: m['command_count'])['name']} "
            f"({min(m['command_count'] for m in mods)} cmds)",
            "",
            "  Modules by category:",
        ]
        for c, n in sorted(cat_counts.items(), key=lambda x: -x[1]):
            lines.append(f"    #{c:<14s} {n} module(s)")
        return "\n".join(lines)

    @safe
    def cmd_by_platform(self, arg=""):
        """Filter commands by platform"""
        p = (arg or sys.platform).lower()
        platform_label = "Windows" if "win" in p else "macOS" if "darwin" in p else "Linux"
        mods = self._scan_modules()
        win_only = {"wsl", "ai" if False else None}
        linux_only = set()
        lines = [f"[catalog] Modules for {platform_label}:"]
        for m in mods:
            note = ""
            if m["name"] == "wsl" and "win" not in p:
                note = "  (Windows host only — but useful from inside WSL)"
            lines.append(f"  /{m['name']:<10s} {m['description']}{note}")
        lines.append(f"\n  Most commands work cross-platform. Use /catalog module <name> for specifics.")
        return "\n".join(lines)

    @safe
    def cmd_by_category(self, arg=""):
        """Group by category: /catalog by-category <c>"""
        cat = (arg or "").strip().lower().lstrip("#")
        if not cat:
            return "[catalog] Usage: /catalog by-category <name>  (see /catalog categories)"
        mods = self._scan_modules()
        matches = [m for m in mods if cat in m["categories"]]
        if not matches:
            return f"[catalog] No modules in category #{cat}"
        lines = [f"[catalog] {len(matches)} module(s) in category #{cat}:"]
        for m in matches:
            lines.append(f"\n  /{m['name']:<10s} {m['description']}")
            for c in m["commands"][:8]:
                desc = m["cmd_descriptions"].get(c, "")
                lines.append(f"    /{m['name']} {c}  {desc[:60]}")
            if len(m["commands"]) > 8:
                lines.append(f"    ... +{len(m['commands'])-8} more")
        return "\n".join(lines)

    @safe
    def cmd_categories(self, arg=""):
        """List defined categories"""
        mods = self._scan_modules()
        cat_mods = {}
        for m in mods:
            for c in m["categories"]:
                cat_mods.setdefault(c, []).append(m["name"])
        lines = [f"[catalog] {len(cat_mods)} categories:"]
        for c, names in sorted(cat_mods.items()):
            lines.append(f"  #{c:<12s} {len(names):>2d} mods: {', '.join(names)}")
        return "\n".join(lines)

    @safe
    def cmd_cheatsheet(self, arg=""):
        """One-page command reference"""
        mods = self._scan_modules()
        lines = [f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                 f"  TermAId Quick Reference",
                 f"  {len(mods)} modules, {sum(m['command_count'] for m in mods)} commands",
                 f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"]
        # Group by category
        by_cat = {}
        for m in mods:
            cats = m["categories"] or ["other"]
            for c in cats:
                by_cat.setdefault(c, []).append(m)
        # Stable category order
        cat_order = ["meta", "ai", "security", "network", "disk", "firmware", "boot",
                     "hardware", "perf", "mobile", "os", "dev", "fs", "productivity",
                     "finance", "knowledge", "memory", "auth", "config", "python", "other"]
        for cat in cat_order:
            if cat not in by_cat: continue
            lines.append(f"\n  ── #{cat} ──")
            for m in by_cat[cat]:
                lines.append(f"  /{m['name']:<10s} ({m['command_count']:>2d}) — {m['description'][:70]}")
        return "\n".join(lines)

    @safe
    def cmd_module(self, arg=""):
        """Detail for one module: /catalog module <name>"""
        name = (arg or "").strip().lstrip("/")
        if not name: return "[catalog] Usage: /catalog module <name>"
        mods = self._scan_modules()
        m = next((x for x in mods if x["name"] == name or x["folder"] == name), None)
        if not m:
            return f"[catalog] No module named '{name}'"
        lines = [f"[catalog] /{m['name']} (v{m['version']})"]
        lines.append(f"  Folder:      modules/{m['folder']}")
        lines.append(f"  Description: {m['description']}")
        lines.append(f"  Commands:    {m['command_count']}")
        if m["categories"]:
            lines.append(f"  Categories:  {', '.join('#'+c for c in m['categories'])}")
        lines.append(f"\n  Command list:")
        for c in m["commands"]:
            desc = m["cmd_descriptions"].get(c, "")
            lines.append(f"    /{m['name']} {c:<22s}  {desc[:80]}")
        return "\n".join(lines)

    @safe
    def cmd_freshly_added(self, arg=""):
        """Recently added modules (by mtime)"""
        try: n = int(arg.strip()) if arg.strip() else 10
        except Exception: n = 10
        mods = self._scan_modules()
        sorted_mods = sorted(mods, key=lambda m: -m["mtime"])
        lines = [f"[catalog] {min(n, len(sorted_mods))} most recently modified module(s):"]
        for m in sorted_mods[:n]:
            mt = time.strftime("%Y-%m-%d %H:%M", time.localtime(m["mtime"]))
            lines.append(f"  {mt}  /{m['name']:<10s} {m['description'][:60]}")
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
