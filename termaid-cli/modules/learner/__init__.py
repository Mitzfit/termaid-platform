"""Learner Module — Comprehensive system, hardware, and user profiling.

Builds a rich profile of:
- Hardware (CPU, GPU, RAM, disks, motherboard, peripherals)
- Software (OS, installed apps, running services)
- User patterns (command frequency, preferences, work hours)
- Network fingerprint
- Performance baselines

Stores to SQLite profile DB with proper schema.
AI uses this context to give personalized suggestions.
"""

import json
import os
import platform
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class LearnerModule(Module):
    name = "profile"
    version = "1.0.0"
    description = "Learn user, system, and hardware for personalized AI suggestions"
    author = "termaid"

    def on_load(self):
        for cmd in ["scan", "hardware", "software", "profile", "context",
                    "record", "insights", "forget", "export", "suggest",
                    "watch", "baseline", "status", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "learner"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._db = self._dir / "profile.db"
        self._init_db()

    def _init_db(self):
        """Create relational schema with proper foreign keys."""
        conn = sqlite3.connect(str(self._db))
        conn.executescript("""
            -- Core profile table (one row per system)
            CREATE TABLE IF NOT EXISTS system_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hostname TEXT UNIQUE NOT NULL,
                os_system TEXT,
                os_release TEXT,
                os_version TEXT,
                machine_arch TEXT,
                processor TEXT,
                python_version TEXT,
                first_seen REAL NOT NULL,
                last_updated REAL NOT NULL,
                total_scans INTEGER DEFAULT 0
            );

            -- Hardware components (CPU, GPU, etc.) with FK to system
            CREATE TABLE IF NOT EXISTS hardware (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                component_type TEXT NOT NULL,    -- cpu, gpu, memory, disk, network
                name TEXT,
                manufacturer TEXT,
                model TEXT,
                specs TEXT,                      -- JSON blob with details
                detected_at REAL NOT NULL,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- Installed software with FK to system
            CREATE TABLE IF NOT EXISTS software (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                version TEXT,
                install_path TEXT,
                kind TEXT,                        -- package, app, service, language_tool
                source TEXT,                      -- how detected (winget, apt, pip, etc.)
                first_seen REAL NOT NULL,
                last_seen REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE,
                UNIQUE(system_id, name, kind)
            );

            -- User interactions and commands
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                activity_type TEXT NOT NULL,      -- command, query, edit, error
                content TEXT,
                context TEXT,                     -- JSON for additional info
                timestamp REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- Performance baselines for comparison
            CREATE TABLE IF NOT EXISTS performance_baseline (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                metric TEXT NOT NULL,             -- boot_time, cpu_idle, ram_free, disk_read
                value REAL,
                unit TEXT,
                recorded_at REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- User preferences learned from behavior
            CREATE TABLE IF NOT EXISTS user_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT,
                confidence REAL DEFAULT 0.5,     -- 0.0 to 1.0
                times_seen INTEGER DEFAULT 1,
                last_seen REAL NOT NULL,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE,
                UNIQUE(system_id, key)
            );

            -- Relationships: how entities relate to each other
            -- "software X runs on hardware Y" or "user uses command Z often"
            CREATE TABLE IF NOT EXISTS entity_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_table TEXT NOT NULL,
                source_id INTEGER NOT NULL,
                target_table TEXT NOT NULL,
                target_id INTEGER NOT NULL,
                relationship_type TEXT NOT NULL,   -- uses, depends_on, runs_on, prefers
                strength REAL DEFAULT 1.0,         -- 0.0 to 1.0, how strong the relationship
                metadata TEXT,                     -- JSON
                created_at REAL NOT NULL,
                UNIQUE(source_table, source_id, target_table, target_id, relationship_type)
            );

            -- Insights generated by AI about the user
            CREATE TABLE IF NOT EXISTS insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system_id INTEGER NOT NULL,
                category TEXT,                    -- usage_pattern, recommendation, warning
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 5,     -- 1-10
                created_at REAL NOT NULL,
                acted_on INTEGER DEFAULT 0,
                FOREIGN KEY (system_id) REFERENCES system_profile(id) ON DELETE CASCADE
            );

            -- Useful indexes
            CREATE INDEX IF NOT EXISTS idx_hardware_system ON hardware(system_id);
            CREATE INDEX IF NOT EXISTS idx_software_system ON software(system_id);
            CREATE INDEX IF NOT EXISTS idx_activity_system ON user_activity(system_id);
            CREATE INDEX IF NOT EXISTS idx_activity_time ON user_activity(timestamp);
            CREATE INDEX IF NOT EXISTS idx_relationships_source ON entity_relationships(source_table, source_id);
            CREATE INDEX IF NOT EXISTS idx_relationships_target ON entity_relationships(target_table, target_id);
            CREATE INDEX IF NOT EXISTS idx_preferences_system ON user_preferences(system_id);
        """)
        conn.commit()
        conn.close()

    def _get_or_create_system(self) -> int:
        """Get current system ID, creating the row if missing."""
        hostname = platform.node() or "unknown"
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT id FROM system_profile WHERE hostname = ?", (hostname,))
        row = c.fetchone()
        now = time.time()
        if row:
            c.execute(
                "UPDATE system_profile SET last_updated = ?, total_scans = total_scans + 1 WHERE id = ?",
                (now, row["id"])
            )
            system_id = row["id"]
        else:
            c.execute(
                """INSERT INTO system_profile
                   (hostname, os_system, os_release, os_version, machine_arch,
                    processor, python_version, first_seen, last_updated, total_scans)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
                (hostname, platform.system(), platform.release(), platform.version()[:200],
                 platform.machine(), platform.processor(), platform.python_version(),
                 now, now)
            )
            system_id = c.lastrowid
        conn.commit()
        conn.close()
        return system_id

    def _run(self, cmd: str, timeout: int = 15):
        try:
            if sys.platform == "win32":
                r = subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                                   capture_output=True, text=True, timeout=timeout,
                                   encoding="utf-8", errors="replace")
            else:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                   timeout=timeout, encoding="utf-8", errors="replace")
            return r
        except Exception:
            return subprocess.CompletedProcess(cmd, 1, "", "")

    # === SCAN ===

    @safe
    def cmd_scan(self, args):
        """Full learning scan. Usage: /learn.scan"""
        print("Scanning hardware, software, and system...")
        system_id = self._get_or_create_system()
        hw_count = self._scan_hardware(system_id)
        sw_count = self._scan_software(system_id)

        return (
            f"=== Learning Scan Complete ===\n\n"
            f"  System ID:    {system_id}\n"
            f"  Hostname:     {platform.node()}\n"
            f"  Hardware:     {hw_count} components detected\n"
            f"  Software:     {sw_count} items cataloged\n"
            f"  Database:     {self._db}\n\n"
            f"  Next: /learn.insights for AI analysis\n"
            f"  Next: /learn.suggest <topic> for personalized advice"
        )

    # === HARDWARE ===

    def _scan_hardware(self, system_id: int) -> int:
        """Detect hardware and store."""
        items = []
        now = time.time()

        # CPU
        cpu = {
            "name": platform.processor() or "Unknown",
            "cores_logical": os.cpu_count() or 0,
            "arch": platform.machine(),
        }
        # Get more CPU detail
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_Processor | "
                "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed,Manufacturer | "
                "ConvertTo-Json"
            )
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    if isinstance(data, list):
                        data = data[0]
                    cpu.update({
                        "name": data.get("Name", cpu["name"]),
                        "cores": data.get("NumberOfCores"),
                        "threads": data.get("NumberOfLogicalProcessors"),
                        "max_mhz": data.get("MaxClockSpeed"),
                        "manufacturer": data.get("Manufacturer"),
                    })
                except Exception:
                    pass
        elif sys.platform.startswith("linux"):
            r = self._run("cat /proc/cpuinfo 2>/dev/null | grep -m1 'model name' | cut -d: -f2")
            if r.stdout.strip():
                cpu["name"] = r.stdout.strip()
        items.append(("cpu", cpu.get("name"), cpu.get("manufacturer", ""), "", cpu))

        # Memory
        ram = {}
        if sys.platform == "win32":
            r = self._run(
                "(Get-WmiObject Win32_ComputerSystem).TotalPhysicalMemory"
            )
            try:
                ram["total_bytes"] = int(r.stdout.strip())
                ram["total_gb"] = round(ram["total_bytes"] / (1024**3), 1)
            except Exception:
                pass
        else:
            r = self._run("cat /proc/meminfo 2>/dev/null | head -3")
            for line in r.stdout.splitlines():
                if "MemTotal" in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        try:
                            kb = int(parts[1])
                            ram["total_gb"] = round(kb / (1024**2), 1)
                            ram["total_bytes"] = kb * 1024
                        except Exception:
                            pass
        items.append(("memory", f"{ram.get('total_gb', '?')} GB RAM", "", "", ram))

        # GPU
        gpu_info = {}
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_VideoController | "
                "Select-Object Name,AdapterRAM,DriverVersion | ConvertTo-Json"
            )
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    if isinstance(data, list):
                        data = data[0] if data else {}
                    if data:
                        gpu_info = {
                            "name": data.get("Name"),
                            "driver": data.get("DriverVersion"),
                        }
                        if data.get("AdapterRAM"):
                            gpu_info["vram_mb"] = data["AdapterRAM"] // (1024*1024)
                except Exception:
                    pass
        else:
            r = self._run("lspci 2>/dev/null | grep -i 'vga\\|3d' | head -1")
            if r.stdout.strip():
                gpu_info["name"] = r.stdout.split(":", 2)[-1].strip()
        if gpu_info:
            items.append(("gpu", gpu_info.get("name", "Unknown"), "", "", gpu_info))

        # Disks
        if sys.platform == "win32":
            r = self._run(
                "Get-WmiObject Win32_DiskDrive | "
                "Select-Object Model,Size,MediaType | ConvertTo-Json"
            )
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for d in data:
                        size_gb = round((d.get("Size") or 0) / (1024**3), 1)
                        items.append(("disk", d.get("Model", "?"), "", "",
                                     {"size_gb": size_gb, "type": d.get("MediaType")}))
                except Exception:
                    pass
        else:
            r = self._run("lsblk -dJ -o NAME,SIZE,TYPE,MODEL 2>/dev/null")
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout).get("blockdevices", [])
                    for d in data:
                        if d.get("type") == "disk":
                            items.append(("disk", d.get("model") or d.get("name", "?"), "", "",
                                         {"size": d.get("size"), "type": "disk"}))
                except Exception:
                    pass

        # Save to DB
        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        # Mark all existing as inactive (will be reactivated if found)
        c.execute("UPDATE hardware SET is_active = 0 WHERE system_id = ?", (system_id,))
        for ctype, name, manufacturer, model, specs in items:
            c.execute(
                """INSERT INTO hardware
                   (system_id, component_type, name, manufacturer, model, specs, detected_at, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                (system_id, ctype, name, manufacturer, model, json.dumps(specs), now)
            )
        conn.commit()
        conn.close()
        return len(items)

    @safe
    def cmd_hardware(self, args):
        """Show detected hardware. Usage: /learn.hardware"""
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("""
            SELECT * FROM hardware
            WHERE system_id = ? AND is_active = 1
            ORDER BY component_type, name
        """, (system_id,))
        rows = c.fetchall()
        conn.close()

        if not rows:
            return "No hardware scanned yet. Run: /learn.scan"

        lines = ["=== Detected Hardware ===\n"]
        by_type = {}
        for row in rows:
            by_type.setdefault(row["component_type"], []).append(row)
        for ctype, items in by_type.items():
            lines.append(f"\n  {ctype.upper()}:")
            for item in items:
                lines.append(f"    - {item['name']}")
                if item["manufacturer"]:
                    lines.append(f"        Mfr: {item['manufacturer']}")
                try:
                    specs = json.loads(item["specs"] or "{}")
                    for k, v in specs.items():
                        if v:
                            lines.append(f"        {k}: {v}")
                except Exception:
                    pass
        return "\n".join(lines)

    # === SOFTWARE ===

    def _scan_software(self, system_id: int) -> int:
        """Detect installed software and store."""
        items = []
        now = time.time()

        # Python packages
        r = self._run(f"{sys.executable} -m pip list --format=json", timeout=30)
        if r.stdout.strip():
            try:
                packages = json.loads(r.stdout)
                for pkg in packages:
                    items.append((pkg.get("name", ""), pkg.get("version", ""),
                                  "", "python_package", "pip"))
            except Exception:
                pass

        # Node packages (global)
        import shutil as sh
        if sh.which("npm"):
            r = self._run("npm list -g --depth=0 --json 2>/dev/null", timeout=15)
            if r.stdout.strip():
                try:
                    data = json.loads(r.stdout)
                    for name, info in (data.get("dependencies") or {}).items():
                        items.append((name, info.get("version", ""),
                                      "", "node_package", "npm"))
                except Exception:
                    pass

        # OS packages
        if sys.platform == "win32":
            r = self._run("winget list --accept-source-agreements 2>&1 | Select-String -Pattern '^\\w' | Select-Object -First 100", timeout=30)
            for line in r.stdout.splitlines()[2:]:
                parts = line.split()
                if len(parts) >= 2:
                    items.append((parts[0], parts[-2] if len(parts) >= 3 else "",
                                  "", "app", "winget"))
        elif sh.which("apt"):
            r = self._run("dpkg-query -W -f='${Package}|${Version}\\n' 2>/dev/null | head -200", timeout=10)
            for line in r.stdout.splitlines():
                if "|" in line:
                    name, ver = line.split("|", 1)
                    items.append((name, ver, "", "package", "apt"))
        elif sh.which("pacman"):
            r = self._run("pacman -Q 2>/dev/null | head -200", timeout=10)
            for line in r.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    items.append((parts[0], parts[1], "", "package", "pacman"))
        elif sh.which("brew"):
            r = self._run("brew list --versions 2>/dev/null | head -100", timeout=15)
            for line in r.stdout.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) >= 1:
                    items.append((parts[0], parts[1] if len(parts) > 1 else "",
                                  "", "package", "brew"))

        # Save to DB
        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        for name, version, install_path, kind, source in items:
            c.execute("""
                INSERT INTO software (system_id, name, version, install_path, kind, source, first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(system_id, name, kind) DO UPDATE SET
                    version = excluded.version,
                    last_seen = excluded.last_seen
            """, (system_id, name, version, install_path, kind, source, now, now))
        conn.commit()
        conn.close()
        return len(items)

    @safe
    def cmd_software(self, args):
        """Show installed software. Usage: /learn.software [filter]"""
        filter_kind = args.strip().lower() if args.strip() else ""
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        if filter_kind:
            c.execute("""SELECT kind, COUNT(*) as n FROM software
                         WHERE system_id = ? AND kind LIKE ?
                         GROUP BY kind""", (system_id, f"%{filter_kind}%"))
        else:
            c.execute("SELECT kind, COUNT(*) as n FROM software WHERE system_id = ? GROUP BY kind",
                      (system_id,))
        summary = c.fetchall()

        if filter_kind:
            c.execute("""SELECT name, version FROM software
                         WHERE system_id = ? AND kind LIKE ?
                         ORDER BY name LIMIT 50""", (system_id, f"%{filter_kind}%"))
            items = c.fetchall()
        else:
            c.execute("""SELECT name, version, kind FROM software
                         WHERE system_id = ?
                         ORDER BY kind, name LIMIT 50""", (system_id,))
            items = c.fetchall()
        conn.close()

        lines = ["=== Software ===\n"]
        for row in summary:
            lines.append(f"  {row['kind']:20s} {row['n']:5d}")
        lines.append("")
        lines.append("Sample items:")
        for row in items:
            if filter_kind:
                lines.append(f"  - {row['name']:30s} {row['version']}")
            else:
                lines.append(f"  [{row['kind']}] {row['name']} {row['version']}")
        return "\n".join(lines)

    # === PROFILE / CONTEXT ===

    @safe
    def cmd_profile(self, args):
        """Show user/system profile. Usage: /learn.profile"""
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        c.execute("SELECT * FROM system_profile WHERE id = ?", (system_id,))
        sys_row = c.fetchone()
        c.execute("SELECT COUNT(*) as n FROM hardware WHERE system_id = ? AND is_active = 1", (system_id,))
        hw_count = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM software WHERE system_id = ?", (system_id,))
        sw_count = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM user_activity WHERE system_id = ?", (system_id,))
        act_count = c.fetchone()["n"]
        c.execute("SELECT COUNT(*) as n FROM user_preferences WHERE system_id = ?", (system_id,))
        pref_count = c.fetchone()["n"]
        conn.close()

        if not sys_row:
            return "No profile yet. Run: /learn.scan"

        lines = ["=== System Profile ==="]
        lines.append(f"\n  Host:            {sys_row['hostname']}")
        lines.append(f"  OS:              {sys_row['os_system']} {sys_row['os_release']}")
        lines.append(f"  Architecture:    {sys_row['machine_arch']}")
        lines.append(f"  Python:          {sys_row['python_version']}")
        lines.append(f"  First seen:      {time.ctime(sys_row['first_seen'])}")
        lines.append(f"  Last updated:    {time.ctime(sys_row['last_updated'])}")
        lines.append(f"  Total scans:     {sys_row['total_scans']}")
        lines.append(f"\n  Catalog:")
        lines.append(f"    Hardware:      {hw_count}")
        lines.append(f"    Software:      {sw_count}")
        lines.append(f"    Activities:    {act_count}")
        lines.append(f"    Preferences:   {pref_count}")
        return "\n".join(lines)

    @safe
    def cmd_context(self, args):
        """Get full AI context string. Usage: /learn.context"""
        system_id = self._get_or_create_system()
        return self._build_context(system_id)

    def _build_context(self, system_id: int) -> str:
        """Build a compact context string for the AI."""
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        parts = []
        c.execute("SELECT * FROM system_profile WHERE id = ?", (system_id,))
        sys_row = c.fetchone()
        if sys_row:
            parts.append(f"System: {sys_row['os_system']} {sys_row['os_release']} on {sys_row['machine_arch']}")

        # Top hardware
        c.execute("""SELECT component_type, name, specs FROM hardware
                     WHERE system_id = ? AND is_active = 1""", (system_id,))
        for row in c.fetchall():
            parts.append(f"  {row['component_type']}: {row['name']}")

        # Software summary
        c.execute("""SELECT kind, COUNT(*) as n FROM software
                     WHERE system_id = ? GROUP BY kind""", (system_id,))
        for row in c.fetchall():
            parts.append(f"  {row['kind']}: {row['n']} installed")

        # Preferences
        c.execute("""SELECT key, value FROM user_preferences
                     WHERE system_id = ? ORDER BY confidence DESC LIMIT 10""", (system_id,))
        prefs = c.fetchall()
        if prefs:
            parts.append("User preferences:")
            for row in prefs:
                parts.append(f"  {row['key']}: {row['value']}")

        conn.close()
        return "\n".join(parts)

    # === RECORD / INSIGHTS ===

    @safe
    def cmd_record(self, args):
        """Record user activity. Usage: /learn.record <type> <content>"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /learn.record <type> <content>\nExample: /learn.record command 'git status'"
        activity_type, content = parts[0], parts[1]
        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.execute(
            """INSERT INTO user_activity (system_id, activity_type, content, timestamp)
               VALUES (?, ?, ?, ?)""",
            (system_id, activity_type, content, time.time())
        )
        conn.commit()
        conn.close()
        return f"Recorded {activity_type}: {content[:80]}"

    @safe
    def cmd_insights(self, args):
        """AI insights about the user/system. Usage: /learn.insights"""
        system_id = self._get_or_create_system()
        context = self._build_context(system_id)

        # Activity stats
        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        c.execute("""SELECT activity_type, COUNT(*) as n FROM user_activity
                     WHERE system_id = ? GROUP BY activity_type
                     ORDER BY n DESC LIMIT 10""", (system_id,))
        activity = c.fetchall()
        conn.close()

        prompt = f"""Based on this system profile, generate 5 specific insights and recommendations.

{context}

Activity summary:
{chr(10).join(f'  {a[0]}: {a[1]} times' for a in activity) if activity else '  (no activity recorded yet)'}

For each insight:
- What pattern or situation you identified
- Why it matters
- Concrete action

Be specific to THIS system. No generic advice."""

        print("Generating AI insights...")
        result = self.ask_ai(prompt, system="You are a personal computing expert analyzing a user's system.")

        # Store insights
        conn = sqlite3.connect(str(self._db))
        conn.execute(
            """INSERT INTO insights (system_id, category, content, created_at)
               VALUES (?, 'general', ?, ?)""",
            (system_id, result, time.time())
        )
        conn.commit()
        conn.close()

        return f"=== AI Insights ===\n\n{result}"

    @safe
    def cmd_suggest(self, args):
        """Personalized AI suggestions. Usage: /learn.suggest <topic>"""
        if not args.strip():
            return ("Usage: /learn.suggest <topic>\n"
                    "Examples:\n"
                    "  /learn.suggest cleanup\n"
                    "  /learn.suggest performance\n"
                    "  /learn.suggest security\n"
                    "  /learn.suggest workflow")
        system_id = self._get_or_create_system()
        context = self._build_context(system_id)

        prompt = f"""Given this user's system and preferences:

{context}

Provide specific suggestions for: {args.strip()}

Tailor advice to THIS exact system. Be direct, specific, and actionable."""

        print(f"Generating suggestions for '{args.strip()}'...")
        return self.ask_ai(prompt, system="You are a personalized tech advisor.")

    # === BASELINE / WATCH ===

    def _capture_metrics(self) -> list:
        """One instant (bounded, sub-2s) sample of CPU idle% and free RAM. Shared by
        /learn.baseline and /learn.watch so neither pretends to monitor over a window
        it doesn't actually observe."""
        metrics = []

        if sys.platform == "win32":
            r = self._run(
                "(Get-Counter '\\Processor(_Total)\\% Idle Time' "
                "-SampleInterval 1 -MaxSamples 1).CounterSamples.CookedValue"
            )
            try:
                metrics.append(("cpu_idle_pct", float(r.stdout.strip()), "%"))
            except Exception:
                pass
        else:
            r = self._run("vmstat 1 2 | tail -1 | awk '{print $15}'")
            try:
                metrics.append(("cpu_idle_pct", float(r.stdout.strip()), "%"))
            except Exception:
                pass

        if sys.platform == "win32":
            r = self._run(
                "[math]::Round((Get-WmiObject Win32_OperatingSystem).FreePhysicalMemory/1MB, 2)"
            )
            try:
                metrics.append(("ram_free_gb", float(r.stdout.strip()), "GB"))
            except Exception:
                pass
        else:
            r = self._run("free -g 2>/dev/null | awk 'NR==2 {print $4}'")
            try:
                metrics.append(("ram_free_gb", float(r.stdout.strip()), "GB"))
            except Exception:
                pass

        return metrics

    def _record_metrics(self, metrics: list) -> None:
        system_id = self._get_or_create_system()
        now = time.time()
        conn = sqlite3.connect(str(self._db))
        for name, val, unit in metrics:
            conn.execute(
                """INSERT INTO performance_baseline (system_id, metric, value, unit, recorded_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (system_id, name, val, unit, now)
            )
        conn.commit()
        conn.close()

    @safe
    def cmd_baseline(self, args):
        """Record performance baseline. Usage: /learn.baseline"""
        metrics = self._capture_metrics()
        self._record_metrics(metrics)
        lines = ["=== Baseline Recorded ===\n"]
        for name, val, unit in metrics:
            lines.append(f"  {name:20s} {val:8.2f} {unit}")
        return "\n".join(lines)

    @safe
    def cmd_watch(self, args):
        """Record an instant performance sample. Usage: /learn.watch

        Previously did a blocking time.sleep(5) that froze the whole backend's
        single-threaded event loop for every connected user on every call, while
        not actually sampling anything during that wait — a strictly worse version
        of /learn.baseline. Now just takes the same instant, bounded sample
        /learn.baseline does; run this a few times over a real interval yourself
        (there's no background worker to do timed sampling from inside a
        request/response handler) if you want a trend.
        """
        metrics = self._capture_metrics()
        self._record_metrics(metrics)
        return "Sample recorded. See /learn.insights for analysis, or /learn.baseline for the raw numbers."

    # === EXPORT / FORGET / STATUS ===

    @safe
    def cmd_export(self, args):
        """Export profile. Usage: /learn.export [file]"""
        filename = args.strip() or f"profile_{int(time.time())}.json"
        filepath = Path(filename).expanduser()
        if not filepath.is_absolute():
            filepath = self._dir / filename

        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        export_data = {}
        for table in ["system_profile", "hardware", "software", "user_preferences", "insights"]:
            if table == "system_profile":
                c.execute(f"SELECT * FROM {table} WHERE id = ?", (system_id,))
            else:
                c.execute(f"SELECT * FROM {table} WHERE system_id = ?", (system_id,))
            export_data[table] = [dict(row) for row in c.fetchall()]
        conn.close()

        filepath.write_text(json.dumps(export_data, indent=2, default=str))
        return f"Exported {sum(len(v) for v in export_data.values())} records to {filepath}"

    @safe
    def cmd_forget(self, args):
        """Delete learned data. Usage: /learn.forget [what]"""
        what = args.strip().lower() or "confirm"
        if what == "confirm":
            return ("This will delete all learned data.\n"
                    "Run: /learn.forget all  (to confirm)\n"
                    "Or:  /learn.forget activity  (activity log only)\n"
                    "Or:  /learn.forget insights (insights only)")

        system_id = self._get_or_create_system()
        conn = sqlite3.connect(str(self._db))
        if what == "all":
            for table in ["hardware", "software", "user_activity", "performance_baseline",
                          "user_preferences", "entity_relationships", "insights"]:
                if table == "entity_relationships":
                    conn.execute(f"DELETE FROM {table}")
                else:
                    conn.execute(f"DELETE FROM {table} WHERE system_id = ?", (system_id,))
            conn.commit()
            conn.close()
            return "All learned data deleted for this system"
        elif what in ("activity", "user_activity"):
            conn.execute("DELETE FROM user_activity WHERE system_id = ?", (system_id,))
            conn.commit()
            conn.close()
            return "Activity log cleared"
        elif what == "insights":
            conn.execute("DELETE FROM insights WHERE system_id = ?", (system_id,))
            conn.commit()
            conn.close()
            return "Insights cleared"
        else:
            conn.close()
            return f"Unknown target: {what}"

    @safe
    def cmd_status(self, args):
        """Show learner status. Usage: /learn.status"""
        if not self._db.exists():
            return "Database not yet initialized. Run: /learn.scan"

        conn = sqlite3.connect(str(self._db))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM system_profile")
        systems = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM hardware")
        hw = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM software")
        sw = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM user_activity")
        act = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM insights")
        ins = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM entity_relationships")
        rel = c.fetchone()[0]
        conn.close()

        lines = ["=== Learner Status ===\n"]
        lines.append(f"  Database:        {self._db}")
        lines.append(f"  Size:            {self._db.stat().st_size:,} bytes")
        lines.append(f"\n  Systems tracked:   {systems}")
        lines.append(f"  Hardware items:    {hw}")
        lines.append(f"  Software items:    {sw}")
        lines.append(f"  Activities:        {act}")
        lines.append(f"  Insights:          {ins}")
        lines.append(f"  Relationships:     {rel}")
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
