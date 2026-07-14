"""Learn Module — Knowledge base, cross-session memory, and resource discovery.

An extensible local knowledge system. You add entries (facts, commands, links,
lessons learned). /learn ranks and surfaces relevant entries when you search
or ask for context. Designed to complement (not replace) TermAId's /learner.

Also includes curated free resource catalogs for: investing, security, game dev,
AI/ML, systems programming, mobile dev, Linux sysadmin.

Commands (24):
  /learn add <text>             Quick-add a knowledge entry
  /learn add-cmd <cmd> <notes>  Add a command with notes
  /learn add-link <url> <note>  Add a URL with description
  /learn add-lesson <text>      Add a lesson learned (flagged for review)
  /learn list [tag]             List entries (optionally filtered)
  /learn show <id>              Detailed view of one entry
  /learn search <pattern>       Full-text search
  /learn tag <id> <tag>         Add tag
  /learn untag <id> <tag>       Remove tag
  /learn tags                   All tags with counts
  /learn resources <topic>      Free learning resources for topic
  /learn topics                 Topics available in resources
  /learn related <text>         Find related entries by keywords
  /learn review                 Surface items for spaced review
  /learn review-done <id>       Mark a review item done
  /learn stats                  Knowledge base statistics
  /learn export [path]          Export entire KB to markdown
  /learn import <path>          Import markdown/text
  /learn delete <id>            Delete an entry (confirm)
  /learn backup                 Create timestamped backup
  /learn journal <text>         Learning journal entry
  /learn journal-list           Show journal
  /learn cheatsheet <topic>     Generate cheatsheet from KB entries
  /learn cross-session          Recent entries across all sessions (for context)
"""

import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


# Curated resource catalogs — compiled into module so works offline
RESOURCES = {
    "investing": {
        "description": "Personal finance and investing fundamentals",
        "books": [
            ("The Intelligent Investor", "Benjamin Graham", "Foundational value investing"),
            ("A Random Walk Down Wall Street", "Burton Malkiel", "Case for index investing"),
            ("The Bogleheads Guide to Investing", "Larimore et al", "Practical passive investing"),
            ("The Psychology of Money", "Morgan Housel", "Behavioral side of money"),
            ("Common Sense on Mutual Funds", "John Bogle", "From the founder of Vanguard"),
            ("Market Wizards", "Jack Schwager", "Interviews with top traders"),
        ],
        "websites": [
            ("bogleheads.org", "Free wiki + forum, genuinely useful"),
            ("investopedia.com", "Reference for terms"),
            ("portfoliovisualizer.com", "Backtest portfolios for free"),
            ("morningstar.com", "Fund research"),
            ("fred.stlouisfed.org", "Macro economic data"),
            ("sec.gov/edgar", "Actual company filings (10-K, 10-Q)"),
        ],
        "youtube": [
            ("Ben Felix", "Evidence-based investing, no hype"),
            ("The Plain Bagel", "Accessible explanations"),
            ("Aswath Damodaran", "NYU professor, free valuation courses"),
            ("Patrick Boyle", "Markets with wit, ex-hedge-fund"),
        ],
        "courses": [
            ("Yale: Financial Markets (Shiller)", "https://www.coursera.org/learn/financial-markets-global"),
            ("MIT 15.401 Finance Theory I", "https://ocw.mit.edu"),
            ("Khan Academy Finance & Capital Markets", "https://www.khanacademy.org"),
        ],
    },
    "security": {
        "description": "Cybersecurity — offensive knowledge for defense, and general hardening",
        "books": [
            ("The Web Application Hacker's Handbook", "Stuttard & Pinto", "Classic on web app sec"),
            ("The Tangled Web", "Michal Zalewski", "How browsers actually work"),
            ("Practical Malware Analysis", "Sikorski & Honig", "Reverse-engineering malware"),
            ("Serious Cryptography", "Jean-Philippe Aumasson", "Modern crypto, readable"),
            ("The Art of Deception", "Kevin Mitnick", "Social engineering"),
            ("Red Team Field Manual", "Ben Clark", "Quick reference"),
        ],
        "websites": [
            ("owasp.org", "The de facto standard for web app security"),
            ("portswigger.net/web-security", "Free Burp web security academy"),
            ("hackthebox.com", "Legal hacking labs"),
            ("tryhackme.com", "Beginner-friendly labs"),
            ("exploit-db.com", "Historical exploits database"),
            ("nvd.nist.gov", "NIST CVE database"),
            ("attack.mitre.org", "ATT&CK framework — attacker TTPs"),
        ],
        "youtube": [
            ("LiveOverflow", "Hacking challenges + theory"),
            ("John Hammond", "Real CTF walkthroughs"),
            ("IppSec", "HackTheBox walkthroughs"),
            ("David Bombal", "Networking + security basics"),
        ],
        "courses": [
            ("TryHackMe Learning Paths", "tryhackme.com"),
            ("Cybrary", "Free tier has decent intro content"),
            ("OverTheWire Wargames", "overthewire.org/wargames/"),
            ("PicoCTF", "picoctf.org — great for beginners"),
        ],
    },
    "gamedev": {
        "description": "Game development, especially Unreal Engine",
        "books": [
            ("Game Programming Patterns", "Robert Nystrom", "Free online: gameprogrammingpatterns.com"),
            ("The Art of Game Design", "Jesse Schell", "Design philosophy"),
            ("Game Engine Architecture", "Jason Gregory", "How engines work under the hood"),
            ("Real-Time Rendering", "Akenine-Möller et al", "Graphics bible"),
        ],
        "websites": [
            ("docs.unrealengine.com", "Official UE docs"),
            ("gafferongames.com", "Networking in games"),
            ("iquilezles.org", "Graphics/shader wizardry"),
            ("tomdominer.com", "Practical UE tutorials"),
            ("80.lv", "Environment art + Unreal"),
        ],
        "youtube": [
            ("Mathew Wadstein", "UE documentation in video form"),
            ("Gorka Games", "Blueprint tutorials"),
            ("Alex Forsythe", "Smart UE systems"),
            ("Ryan Laley", "AI in UE5"),
            ("The Cherno", "C++ + game engine internals"),
        ],
        "courses": [
            ("Unreal Engine Online Learning", "dev.epicgames.com/community/learning"),
            ("MIT 6.837 Computer Graphics", "ocw.mit.edu"),
            ("Handmade Hero", "handmadehero.org — from-scratch C engine"),
        ],
    },
    "ai-ml": {
        "description": "AI/ML fundamentals and LLM-specific topics",
        "books": [
            ("Deep Learning", "Goodfellow, Bengio, Courville", "Free at deeplearningbook.org"),
            ("Hands-On ML", "Aurélien Géron", "Practical with scikit-learn and TF"),
            ("The Hundred-Page ML Book", "Andriy Burkov", "Fast overview"),
            ("Reinforcement Learning: An Introduction", "Sutton & Barto", "Free online: incompleteideas.net"),
        ],
        "websites": [
            ("arxiv.org", "Papers — follow arxiv-sanity.com to filter"),
            ("paperswithcode.com", "Papers + code"),
            ("huggingface.co", "Models, datasets, docs"),
            ("lilianweng.github.io", "Clear explainers from OpenAI research"),
            ("distill.pub", "Visual ML research"),
            ("fast.ai", "Practical deep learning"),
        ],
        "youtube": [
            ("3Blue1Brown", "Neural networks intuition"),
            ("Andrej Karpathy", "From-scratch LLM lessons"),
            ("Two Minute Papers", "Recent results, short"),
            ("Yannic Kilcher", "Paper walkthroughs"),
        ],
        "courses": [
            ("Andrew Ng ML Specialization (Coursera)", "Classic foundation"),
            ("Stanford CS229 / CS231n / CS224n", "Free on YouTube"),
            ("fast.ai Practical Deep Learning", "fast.ai"),
            ("HuggingFace NLP course", "huggingface.co/learn"),
        ],
    },
    "linux": {
        "description": "Linux system administration and power use",
        "books": [
            ("The Linux Command Line", "William Shotts", "Free at linuxcommand.org"),
            ("UNIX and Linux System Administration Handbook", "Nemeth et al", "Reference"),
            ("How Linux Works", "Brian Ward", "Under-the-hood"),
            ("The Art of Unix Programming", "Eric Raymond", "Philosophy"),
        ],
        "websites": [
            ("man7.org/linux/man-pages", "Online man pages"),
            ("tldr.sh", "Practical examples for every command"),
            ("cheat.sh", "curl cheat.sh/<command>"),
            ("wiki.archlinux.org", "The best Linux documentation, period"),
            ("kernelnewbies.org", "Kernel development"),
        ],
        "youtube": [
            ("DistroTube", "Terminal-focused Linux"),
            ("Luke Smith", "Minimalist Linux setup"),
            ("The Linux Cast", "General Linux topics"),
        ],
        "courses": [
            ("Linux Foundation LFS101 (free)", "Intro to Linux"),
            ("edX Linux courses", "edx.org"),
            ("OverTheWire Bandit", "SSH + shell wargame"),
        ],
    },
    "mobile": {
        "description": "Mobile development and rooting/modding",
        "websites": [
            ("developer.android.com", "Android official docs"),
            ("xda-developers.com", "Modding + ROMs"),
            ("source.android.com", "AOSP documentation"),
            ("topjohnwu.github.io/Magisk", "Magisk (systemless root) docs"),
            ("kernelsu.org", "KernelSU alternative to Magisk"),
            ("lineageos.org/devices", "Supported devices list"),
        ],
        "youtube": [
            ("Mishaal Rahman", "Deep Android news/analysis"),
            ("Max Weinbach", "Modding + custom ROMs"),
            ("HowToMen", "Practical Android tutorials"),
        ],
        "tools": [
            ("ADB Platform Tools", "developer.android.com/tools/releases/platform-tools"),
            ("Magisk", "github.com/topjohnwu/Magisk"),
            ("TWRP recovery", "twrp.me"),
            ("Termux", "termux.dev"),
        ],
    },
    "systems": {
        "description": "Systems programming and low-level CS",
        "books": [
            ("Computer Systems: A Programmer's Perspective", "Bryant & O'Hallaron", "CSAPP, classic"),
            ("Operating Systems: Three Easy Pieces", "Arpaci-Dusseau", "Free at pages.cs.wisc.edu/~remzi/OSTEP"),
            ("The C Programming Language", "K&R", "Short and essential"),
            ("Crafting Interpreters", "Robert Nystrom", "Free at craftinginterpreters.com"),
        ],
        "websites": [
            ("cppreference.com", "C++ reference"),
            ("rust-lang.org/learn", "Rust official learning"),
            ("doc.rust-lang.org/book", "The Rust Book (free)"),
            ("go.dev/tour", "A Tour of Go"),
        ],
        "courses": [
            ("Harvard CS50", "cs50.harvard.edu"),
            ("MIT 6.S081 Operating Systems", "pdos.csail.mit.edu/6.S081"),
            ("Nand2Tetris", "nand2tetris.org — build a computer from NAND"),
        ],
    },
}


class LearnModule(Module):
    name = "learn"
    version = "1.0.0"
    description = "Knowledge base, memory, and curated learning resources"
    author = "termaid"

    def on_load(self):
        cmds = ["add", "add-cmd", "add-link", "add-lesson", "list", "show",
                "search", "tag", "untag", "tags", "resources", "topics",
                "related", "review", "review-done", "stats", "export",
                "import", "delete", "backup", "journal", "journal-list",
                "cheatsheet", "cross-session", "explain"]
        for cmd in cmds:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-','_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "learn"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._kb_file = self._dir / "kb.jsonl"
        self._journal_file = self._dir / "journal.jsonl"
        self._session_file = self._dir / "sessions.jsonl"
        # Log this session
        self._log_session()

    def _log_session(self):
        try:
            with self._session_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(), "event": "module_load"}) + "\n")
        except Exception: pass

    def _load_kb(self):
        entries = []
        if self._kb_file.exists():
            try:
                for line in self._kb_file.read_text().splitlines():
                    if line.strip():
                        try: entries.append(json.loads(line))
                        except Exception: continue
            except Exception: pass
        return entries

    def _save_kb(self, entries):
        with self._kb_file.open("w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e, default=str) + "\n")

    def _next_id(self, entries):
        return max((e.get("id", 0) for e in entries), default=0) + 1

    def _append(self, entry):
        entries = self._load_kb()
        entry["id"] = self._next_id(entries)
        entry["ts"] = time.time()
        entry["created"] = time.strftime("%Y-%m-%d %H:%M:%S")
        entries.append(entry)
        self._save_kb(entries)
        return entry["id"]

    # ---------- commands ----------

    @safe
    def cmd_add(self, arg=""):
        text = arg or ""
        if not text.strip():
            return "[learn] Usage: /learn add <text>"
        # Extract inline #tags
        tags = re.findall(r"(?:^|\s)#([a-zA-Z][\w-]{1,30})", text)
        entry = {"kind": "note", "text": text, "tags": [t.lower() for t in tags]}
        eid = self._append(entry)
        return f"[learn] Saved entry #{eid}" + (f" tags: {', '.join('#'+t for t in tags)}" if tags else "")

    @safe
    def cmd_add_cmd(self, arg=""):
        parts = (arg or "").split(None, 1)
        if len(parts) < 2:
            return "[learn] Usage: /learn add-cmd <command> <notes>"
        cmd, notes = parts
        entry = {"kind": "command", "command": cmd, "text": notes, "tags": ["command"]}
        eid = self._append(entry)
        return f"[learn] Saved command entry #{eid}: {cmd}"

    @safe
    def cmd_add_link(self, arg=""):
        parts = (arg or "").split(None, 1)
        if len(parts) < 1 or not parts[0].startswith(("http://", "https://")):
            return "[learn] Usage: /learn add-link <url> [description]"
        url = parts[0]
        desc = parts[1] if len(parts) > 1 else ""
        entry = {"kind": "link", "url": url, "text": desc, "tags": ["link"]}
        eid = self._append(entry)
        return f"[learn] Saved link #{eid}: {url}"

    @safe
    def cmd_add_lesson(self, arg=""):
        text = (arg or "").strip()
        if not text: return "[learn] Usage: /learn add-lesson <what you learned>"
        # Lessons go in spaced-repetition queue
        entry = {
            "kind": "lesson", "text": text, "tags": ["lesson"],
            "review_state": {"interval_days": 1, "ease": 2.5,
                             "next_review": time.time() + 86400},
        }
        eid = self._append(entry)
        return f"[learn] Saved lesson #{eid}. Review in 1 day."

    @safe
    def cmd_list(self, arg=""):
        filt_tag = (arg or "").strip().lstrip("#").lower()
        entries = self._load_kb()
        if filt_tag:
            entries = [e for e in entries if filt_tag in (e.get("tags") or [])]
        if not entries:
            return f"[learn] No entries" + (f" with tag #{filt_tag}" if filt_tag else "")
        lines = [f"[learn] {len(entries)} entr{'y' if len(entries)==1 else 'ies'}" +
                 (f" tagged #{filt_tag}" if filt_tag else "") + ":"]
        for e in entries[-50:]:
            kind = e.get("kind", "?")[:8]
            preview = (e.get("text", "") or e.get("command", "") or e.get("url", ""))[:80].replace("\n", " ")
            tags = "  [" + ", ".join(f"#{t}" for t in e.get("tags", [])) + "]" if e.get("tags") else ""
            lines.append(f"  #{e['id']:<4d} [{kind:<8s}] {preview}{tags}")
        return "\n".join(lines)

    @safe
    def cmd_show(self, arg=""):
        try: eid = int((arg or "").strip())
        except Exception: return "[learn] Usage: /learn show <id>"
        entries = self._load_kb()
        match = next((e for e in entries if e.get("id") == eid), None)
        if not match:
            return f"[learn] No entry #{eid}"
        lines = [f"[learn] Entry #{eid}:"]
        for k, v in match.items():
            if k == "review_state" and isinstance(v, dict):
                nr = v.get("next_review", 0)
                lines.append(f"  review_due: {time.strftime('%Y-%m-%d', time.localtime(nr))}")
                lines.append(f"  interval:   {v.get('interval_days',1)} days")
                lines.append(f"  ease:       {v.get('ease',2.5):.2f}")
            elif isinstance(v, (list, dict)):
                lines.append(f"  {k}: {json.dumps(v)}")
            else:
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)

    @safe
    def cmd_search(self, arg=""):
        q = (arg or "").strip().lower()
        if not q: return "[learn] Usage: /learn search <pattern>"
        entries = self._load_kb()
        matches = []
        for e in entries:
            blob = json.dumps(e).lower()
            if q in blob:
                matches.append(e)
        if not matches:
            return f"[learn] No matches for '{q}'"
        lines = [f"[learn] {len(matches)} match(es):"]
        for e in matches[:30]:
            preview = (e.get("text","") or e.get("command","") or e.get("url",""))[:100]
            lines.append(f"  #{e['id']:<4d} [{e.get('kind','?'):<8s}] {preview}")
        return "\n".join(lines)

    @safe
    def cmd_tag(self, arg=""):
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[learn] Usage: /learn tag <id> <tag>"
        try: eid = int(parts[0])
        except Exception: return "[learn] Invalid id"
        tag = parts[1].lstrip("#").lower()
        entries = self._load_kb()
        for e in entries:
            if e.get("id") == eid:
                e.setdefault("tags", [])
                if tag not in e["tags"]:
                    e["tags"].append(tag)
                self._save_kb(entries)
                return f"[learn] Tagged #{eid} with #{tag}"
        return f"[learn] No entry #{eid}"

    @safe
    def cmd_untag(self, arg=""):
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[learn] Usage: /learn untag <id> <tag>"
        try: eid = int(parts[0])
        except Exception: return "[learn] Invalid id"
        tag = parts[1].lstrip("#").lower()
        entries = self._load_kb()
        for e in entries:
            if e.get("id") == eid:
                if tag in e.get("tags", []):
                    e["tags"].remove(tag)
                self._save_kb(entries)
                return f"[learn] Removed #{tag} from entry #{eid}"
        return f"[learn] No entry #{eid}"

    @safe
    def cmd_tags(self, arg=""):
        entries = self._load_kb()
        counts = Counter()
        for e in entries:
            for t in e.get("tags", []):
                counts[t] += 1
        if not counts:
            return "[learn] No tags yet."
        lines = [f"[learn] {len(counts)} tag(s):"]
        for t, c in sorted(counts.items(), key=lambda x: -x[1]):
            lines.append(f"  #{t:<20s} {c:>4d} entries")
        return "\n".join(lines)

    @safe
    def cmd_resources(self, arg=""):
        topic = (arg or "").strip().lower()
        if not topic:
            return (f"[learn] Available topics: {', '.join(RESOURCES.keys())}\n"
                    f"  Use: /learn resources <topic>")
        if topic not in RESOURCES:
            close = [t for t in RESOURCES if topic in t or t in topic]
            if close:
                topic = close[0]
            else:
                return f"[learn] Unknown topic '{topic}'. Available: {', '.join(RESOURCES)}"
        r = RESOURCES[topic]
        lines = [f"━━━ {topic.upper()} — {r['description']} ━━━"]
        for section, items in r.items():
            if section == "description": continue
            lines.append(f"\n  {section.upper()}:")
            for item in items:
                if isinstance(item, tuple):
                    if len(item) == 3:
                        lines.append(f"    - {item[0]}")
                        lines.append(f"      by {item[1]}. {item[2]}")
                    else:
                        lines.append(f"    - {item[0]} — {item[1]}")
                else:
                    lines.append(f"    - {item}")
        return "\n".join(lines)

    @safe
    def cmd_topics(self, arg=""):
        lines = ["[learn] Curated resource topics:"]
        for t, r in RESOURCES.items():
            lines.append(f"  {t:<12s} {r['description']}")
        return "\n".join(lines)

    @safe
    def cmd_related(self, arg=""):
        q = (arg or "").strip()
        if not q: return "[learn] Usage: /learn related <text or keywords>"
        words = set(re.findall(r"\w{3,}", q.lower()))
        if not words: return "[learn] No usable keywords"
        entries = self._load_kb()
        scored = []
        for e in entries:
            blob = json.dumps(e).lower()
            score = sum(1 for w in words if w in blob)
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            return f"[learn] No related entries for: {q}"
        lines = [f"[learn] {len(scored)} related entr{'y' if len(scored)==1 else 'ies'}:"]
        for score, e in scored[:10]:
            preview = (e.get("text","") or e.get("command","") or e.get("url",""))[:100]
            lines.append(f"  score={score}  #{e['id']}  {preview}")
        return "\n".join(lines)

    @safe
    def cmd_review(self, arg=""):
        entries = self._load_kb()
        now = time.time()
        due = [e for e in entries if e.get("review_state") and
               e["review_state"].get("next_review", 0) <= now]
        if not due:
            next_up = sorted(
                (e for e in entries if e.get("review_state")),
                key=lambda e: e["review_state"].get("next_review", float("inf"))
            )
            if next_up:
                nxt = next_up[0]["review_state"]["next_review"]
                when = time.strftime("%Y-%m-%d", time.localtime(nxt))
                return f"[learn] No items due for review. Next review: {when}"
            return "[learn] No review items. Add with /learn add-lesson <text>"
        lines = [f"[learn] {len(due)} item(s) due for review:"]
        for e in due:
            lines.append(f"\n  #{e['id']}  {e.get('text','')}")
        lines.append("\n  Mark as reviewed with: /learn review-done <id>")
        lines.append("  Each review schedules the next one farther out (spaced repetition).")
        return "\n".join(lines)

    @safe
    def cmd_review_done(self, arg=""):
        try: eid = int((arg or "").strip())
        except Exception: return "[learn] Usage: /learn review-done <id>"
        entries = self._load_kb()
        for e in entries:
            if e.get("id") == eid and e.get("review_state"):
                state = e["review_state"]
                # Simple SM-2-ish: double interval each success
                state["interval_days"] = min(state.get("interval_days", 1) * 2, 180)
                state["next_review"] = time.time() + state["interval_days"] * 86400
                state["last_review"] = time.time()
                self._save_kb(entries)
                return f"[learn] #{eid} reviewed. Next review in {state['interval_days']} days."
        return f"[learn] No review item #{eid}"

    @safe
    def cmd_stats(self, arg=""):
        entries = self._load_kb()
        if not entries:
            return "[learn] Empty knowledge base."
        kinds = Counter(e.get("kind", "?") for e in entries)
        tag_counts = Counter()
        for e in entries:
            for t in e.get("tags", []):
                tag_counts[t] += 1
        oldest = min(entries, key=lambda e: e.get("ts", float("inf")))
        newest = max(entries, key=lambda e: e.get("ts", 0))
        lines = [f"[learn] Knowledge base stats:"]
        lines.append(f"  Total entries:   {len(entries)}")
        lines.append(f"  Unique tags:     {len(tag_counts)}")
        lines.append(f"  Kinds:")
        for k, c in kinds.most_common():
            lines.append(f"    {k:<10s} {c}")
        lines.append(f"  Top tags:        {', '.join(f'#{t}({c})' for t,c in tag_counts.most_common(5))}")
        lines.append(f"  Oldest:          {time.strftime('%Y-%m-%d', time.localtime(oldest.get('ts',0)))}")
        lines.append(f"  Newest:          {time.strftime('%Y-%m-%d', time.localtime(newest.get('ts',0)))}")
        # File sizes
        lines.append(f"  KB file size:    {self._kb_file.stat().st_size} bytes")
        # Sessions
        if self._session_file.exists():
            session_count = len(self._session_file.read_text().splitlines())
            lines.append(f"  Session loads:   {session_count}")
        return "\n".join(lines)

    @safe
    def cmd_export(self, arg=""):
        out = (arg or "").strip() or str(self._dir / f"export-{int(time.time())}.md")
        entries = self._load_kb()
        if not entries:
            return "[learn] Nothing to export."
        parts = [f"# TermAId Knowledge Base Export\n",
                 f"Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n",
                 f"Total entries: {len(entries)}\n",
                 "---\n"]
        grouped = defaultdict(list)
        for e in entries:
            grouped[e.get("kind", "note")].append(e)
        for kind, items in grouped.items():
            parts.append(f"\n## {kind.title()}s ({len(items)})\n")
            for e in items:
                parts.append(f"\n### #{e['id']}\n")
                parts.append(f"*{e.get('created','')}*")
                if e.get("tags"):
                    parts.append(f"  Tags: {', '.join('#'+t for t in e['tags'])}")
                parts.append("")
                if "command" in e:
                    parts.append(f"```\n{e['command']}\n```\n")
                if "url" in e:
                    parts.append(f"<{e['url']}>\n")
                if "text" in e:
                    parts.append(e["text"])
                parts.append("")
        try:
            Path(out).write_text("\n".join(parts), encoding="utf-8")
            return f"[learn] Exported {len(entries)} entries -> {out}"
        except Exception as e:
            return f"[learn] Export failed: {e}"

    @safe
    def cmd_import(self, arg=""):
        path = (arg or "").strip()
        if not path: return "[learn] Usage: /learn import <file>"
        p = Path(path).expanduser()
        if not p.exists(): return f"[learn] Not found: {path}"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return f"[learn] Read failed: {e}"
        # Split on blank lines into entries
        chunks = [c.strip() for c in re.split(r"\n\s*\n", text) if c.strip()]
        for chunk in chunks:
            tags = re.findall(r"(?:^|\s)#([a-zA-Z][\w-]{1,30})", chunk)
            self._append({"kind": "note", "text": chunk,
                          "tags": [t.lower() for t in tags] + ["imported"]})
        return f"[learn] Imported {len(chunks)} entries from {p.name}"

    @safe
    def cmd_delete(self, arg=""):
        """Delete an entry: /learn delete <id> confirm"""
        parts = (arg or "").split()
        if not parts:
            return "[learn] Usage: /learn delete <id> confirm"
        try: eid = int(parts[0])
        except Exception: return "[learn] Usage: /learn delete <id> confirm"
        entries = self._load_kb()
        match = next((e for e in entries if e.get("id") == eid), None)
        if not match: return f"[learn] No entry #{eid}"
        if len(parts) < 2 or parts[1].lower() != "confirm":
            preview = (match.get("text", "") or "")[:60]
            return f"[learn] Delete entry #{eid} ({preview!r})? Re-run as: /learn delete {eid} confirm"
        entries = [e for e in entries if e.get("id") != eid]
        self._save_kb(entries)
        return f"[learn] Deleted #{eid}"

    @safe
    def cmd_backup(self, arg=""):
        backup_path = self._dir / f"kb-backup-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
        if not self._kb_file.exists():
            return "[learn] Nothing to back up."
        try:
            backup_path.write_bytes(self._kb_file.read_bytes())
            return f"[learn] Backup: {backup_path}"
        except Exception as e:
            return f"[learn] Backup failed: {e}"

    @safe
    def cmd_journal(self, arg=""):
        text = (arg or "").strip()
        if not text: return "[learn] Usage: /learn journal <text>"
        try:
            with self._journal_file.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"ts": time.time(),
                                    "date": time.strftime("%Y-%m-%d %H:%M"),
                                    "entry": text}) + "\n")
            return "[learn] Journal entry saved."
        except Exception as e:
            return f"[learn] Journal save failed: {e}"

    @safe
    def cmd_journal_list(self, arg=""):
        if not self._journal_file.exists():
            return "[learn] No journal entries yet."
        entries = []
        for line in self._journal_file.read_text().splitlines():
            try: entries.append(json.loads(line))
            except Exception: continue
        if not entries: return "[learn] No journal entries."
        lines = [f"[learn] Learning journal ({len(entries)} entries):"]
        for e in entries[-15:]:
            lines.append(f"\n  [{e.get('date','?')}]  {e.get('entry','')}")
        return "\n".join(lines)

    @safe
    def cmd_cheatsheet(self, arg=""):
        topic = (arg or "").strip().lower()
        if not topic: return "[learn] Usage: /learn cheatsheet <topic-or-tag>"
        entries = self._load_kb()
        # Match on tag or keywords in text
        matching = []
        for e in entries:
            if topic in (e.get("tags") or []):
                matching.append(e)
            elif topic.lower() in (e.get("text", "") + e.get("command", "")).lower():
                matching.append(e)
        if not matching:
            return f"[learn] No entries for '{topic}'"
        lines = [f"━━━ CHEATSHEET: {topic.upper()} ━━━"]
        commands = [e for e in matching if e.get("kind") == "command"]
        links = [e for e in matching if e.get("kind") == "link"]
        notes = [e for e in matching if e.get("kind") not in ("command", "link")]
        if commands:
            lines.append("\n  COMMANDS:")
            for e in commands:
                lines.append(f"    {e.get('command', '')}")
                if e.get("text"):
                    lines.append(f"      {e['text'][:120]}")
        if links:
            lines.append("\n  LINKS:")
            for e in links:
                lines.append(f"    {e.get('url','')}")
                if e.get("text"):
                    lines.append(f"      {e['text'][:120]}")
        if notes:
            lines.append("\n  NOTES:")
            for e in notes[:10]:
                lines.append(f"    {e.get('text','')[:200]}")
        return "\n".join(lines)

    @safe
    def cmd_cross_session(self, arg=""):
        """Recent entries across all sessions - useful for context recovery."""
        entries = self._load_kb()
        # Show last 20 by time
        entries.sort(key=lambda e: e.get("ts", 0), reverse=True)
        if not entries:
            return "[learn] No entries yet."
        lines = [f"[learn] Recent entries (across all sessions):"]
        for e in entries[:20]:
            date = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("ts", 0)))
            kind = e.get("kind", "?")
            preview = (e.get("text","") or e.get("command","") or e.get("url",""))[:70]
            lines.append(f"  [{date}] #{e['id']} [{kind}]  {preview}")
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
