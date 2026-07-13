"""
policy.py — Module safety policy.

The core of "what can we do about it running as a local tool?".

Your CLI assumes a trusted operator on their own machine. A network service
does not get that assumption. We solve it with two deployment modes:

  • DEPLOYMENT_MODE = "local"   → the app runs on the user's own device
                                  (e.g. inside the Tauri desktop/mobile bundle,
                                  talking to a localhost sidecar). Everything is
                                  allowed except an explicit, tiny deny-list of
                                  irreversibly destructive operations.

  • DEPLOYMENT_MODE = "server"  → the app is exposed to remote / multiple users.
                                  ONLY the curated SAFE allow-list loads. System,
                                  device, firmware, and network-attack modules are
                                  never even imported.

Categories below are derived from your 120 modules. Adjust freely; the policy
engine just consumes these sets.
"""

from __future__ import annotations

# Pure compute or own-data-only. Safe to expose to anyone, anywhere.
SAFE_MODULES: frozenset[str] = frozenset({
    "calc", "text", "regex", "diff", "qr", "password",
    "notes", "translate", "weather", "markets", "paper", "research",
    "learn", "lessons", "persona", "style", "banner", "header", "welcome",
    "errors", "clip", "find", "catalog", "manifest", "rules", "memory",
    "quick", "aliases", "calc", "regex",
})

# Need an AI provider but otherwise side-effect-free. Safe with a key configured.
AI_MODULES: frozenset[str] = frozenset({
    "assistant", "brain", "cognition", "cortex", "smart", "aitools",
    "aiconfig", "imagegen", "learner", "improve", "qa", "agent", "chain",
})

# Touch the host: shell out, scan, modify files, manage processes/VMs/repos.
# Allowed in LOCAL mode, blocked in SERVER mode.
SYSTEM_MODULES: frozenset[str] = frozenset({
    "git", "repo", "docker", "vm", "wsl", "pyenv", "env", "schedule",
    "backup", "sync", "cleanup", "filetools", "find", "diskspace",
    "sysmonitor", "hardware", "devdetect", "doctor", "bench", "perftune",
    "log", "debug", "session", "workspace", "proj", "serve", "sandbox",
    "netscan", "nettools", "netdeep", "fsscan", "dbkeys", "sql", "apikeys",
    "keyring", "dashboard", "bots", "notify", "router", "config", "autoconfig",
    "selftest", "verify", "improve", "extras", "tools", "tmx", "termux",
})

# Irreversible / privilege-escalating / firmware-level. NEVER auto-exposed.
# Blocked in BOTH modes unless an operator explicitly opts in per-module.
DANGEROUS_MODULES: frozenset[str] = frozenset({
    "privesc", "sudo", "perms", "admin", "fwown", "firmware", "uefi",
    "bootmgr", "dualboot", "multiboot", "recovery", "rootguide", "device",
    "devicescan", "adb", "fastboot", "usbdeep", "disktool", "syscmd",
    "sysint", "selfmod", "security", "sec", "hardlines", "firstrun",
    "boot", "crypto",  # crypto can sign/encrypt destructively; opt-in only
})


def allowed_modules(
    discovered: list[str],
    mode: str,
    extra_allow: set[str] | None = None,
    extra_deny: set[str] | None = None,
) -> tuple[set[str], dict[str, str]]:
    """Decide which modules may load.

    Returns (allowed_set, blocked_with_reason).
    """
    extra_allow = extra_allow or set()
    extra_deny = extra_deny or set()

    allowed: set[str] = set()
    blocked: dict[str, str] = {}

    for name in discovered:
        if name in extra_deny:
            blocked[name] = "operator deny-list"
            continue
        if name in extra_allow:
            allowed.add(name)
            continue

        if mode == "server":
            # Default-deny. Dangerous is checked FIRST so a module that is ever
            # double-classified can never leak through the safe path.
            if name in DANGEROUS_MODULES:
                blocked[name] = "dangerous (blocked in server mode)"
            elif name in SAFE_MODULES or name in AI_MODULES:
                allowed.add(name)
            elif name in SYSTEM_MODULES:
                blocked[name] = "system access (blocked in server mode)"
            else:
                blocked[name] = "not in server allow-list"
        else:  # local mode → default-allow, except the irreversible deny set
            if name in DANGEROUS_MODULES:
                blocked[name] = "dangerous (opt-in required even locally)"
            else:
                allowed.add(name)

    return allowed, blocked
