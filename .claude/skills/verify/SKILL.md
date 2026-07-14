---
name: verify
description: Build/launch/drive recipe for verifying changes to the Termaid backend (FastAPI + reconstructed CLI modules).
---

# Termaid backend verify recipe

Surface: HTTP REST + WebSocket, served by `run_backend.py` (uvicorn, port 8000).

## Launch

```bash
cd C:/Termaid
rm -f termaid_web.db   # fresh DB avoids stale users during repeat testing
"./.venv/Scripts/python.exe" run_backend.py > /tmp/backend.log 2>&1 &
sleep 5
curl -s http://127.0.0.1:8000/api/health   # {"status":"ok","mode":"local","commands":N,"ai":false}
```

`.env` at repo root sets `TERMAID_ROOT=C:\Termaid\termaid-cli` (the reconstructed
CLI package — see root `README`/session history) and `DEPLOYMENT_MODE=local`.

## Gotcha: zombie reloader process

`run_backend.py` runs uvicorn with `reload=True`, which spawns a **reloader
parent + worker child** as separate PIDs. A plain `kill $PID` (bash on
Windows) frequently fails to kill the actual worker holding the port —
you'll edit code, restart, and still see the OLD behavior because the port
is still bound by an orphaned worker from a prior run.

**Always verify before trusting a "restart":**
```bash
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select OwningProcess"
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select ProcessId,CommandLine"
```
If a PID owns port 8000 that isn't the one you just started, kill it
explicitly by PID (`Stop-Process -Id <pid> -Force`), confirm the port is
free, *then* relaunch. Don't trust the "Uvicorn running on ..." log line
alone — it prints even when the bind actually failed.

## Gotcha: bcrypt/passlib version mismatch

`requirements.txt` pins `passlib[bcrypt]==1.7.4`, which is incompatible with
`bcrypt>=4.1` (passlib's backend self-test throws `ValueError: password
cannot be longer than 72 bytes` on **any** register/login, even short
passwords — it's a passlib internal self-test, not your input). If
`/api/auth/register` 500s, check `bcrypt.__version__`; if it's `>=4.1`:
```bash
"./.venv/Scripts/pip.exe" install "bcrypt<4.1"
```
then fully restart (see gotcha above).

## Drive it

```bash
# register + login
curl -s -X POST http://127.0.0.1:8000/api/auth/register -H "Content-Type: application/json" \
  -d '{"username":"verifyuser","password":"testpass123"}'
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=verifyuser&password=testpass123" | "./.venv/Scripts/python.exe" -c "import json,sys; print(json.load(sys.stdin)['access_token'])")

# REST exec
curl -s -X POST http://127.0.0.1:8000/api/exec -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"command":"calc.hex 255"}'
```

WebSocket terminal (`/ws/terminal?token=...`) is the protocol the real
frontend uses — prefer it over REST `/api/exec` when verifying UI-facing
behavior. `websockets` (16.x) is already in the venv; a minimal async
client: connect, read the `banner` message, then send
`{"type":"exec","payload":"<cmd>"}` / `{"type":"chat","payload":"..."}` and
read one JSON message back per exec, two for chat (`chat_delta` then
`chat_done`).

Windows console note: reconfigure stdout to UTF-8
(`sys.stdout.reconfigure(encoding="utf-8")`) before printing any command
output — several modules (e.g. `memory.list`) emit raw ANSI color codes and
Unicode bullets (`●`) that crash on the default cp1252 console.

## Server-mode policy check (do this whenever policy.py or a module's
## category changes)

```bash
sed -i 's/DEPLOYMENT_MODE=local/DEPLOYMENT_MODE=server/' .env
# restart (see gotcha above), then:
curl -s http://127.0.0.1:8000/api/blocked -H "Authorization: Bearer $TOKEN"
# confirm SYSTEM-tier modules (netscan, nettools, netdeep, git, docker, ...)
# show up blocked with a reason, and that SAFE/AI-tier commands still work.
# Then restore: sed -i 's/DEPLOYMENT_MODE=server/DEPLOYMENT_MODE=local/' .env
```
Verified 2026-07-13: server mode correctly blocks netdeep/netscan/nettools
(291 vs 339 commands) while calc/brain (SAFE/AI tier) still work.

## Comprehensive module sweep

`scratchpad/full_check.py` (rebuild if missing) registers a user, then execs
one representative command per loaded module in a single pass, plus a rate-
limit probe (default 60/min — note it counts from the START of the session,
so 29 prior execs + N loop execs will trip at N=60-29) and auth-edge-case
checks (no token, garbage token → both 401). Re-run this after any batch of
new modules, not just a health-check.

## Known pre-existing findings (status as of last full sweep)

- `memory.list` (and similar) embed raw ANSI escape sequences + Unicode
  bullets in output meant for a plain-text web JSON API — a browser
  terminal renders these as garbled characters, not colors. Inherited from
  the original module source; not fixed as of this writing.
- `backend/main.py` `exec_command`: empty/whitespace/bare-`/` commands used
  to 500 (`IndexError` from `.split(maxsplit=1)[0]` on an empty list) —
  **fixed** by guarding with `parts[0] if parts else ""`.
- `learner.explain` and `netscan.explain`: both modules define a
  `cmd_explain` method (present in every module) but their `on_load()`
  registration loop — copied verbatim from the original kit source — never
  included `"explain"` in the list, so the command existed in code but was
  unreachable. **Fixed** by adding `"explain"` to both loops. Caught by
  comparing catalog.py's static cmd_-method count (339) against the live
  `/api/commands` count (was 337) — worth re-running that comparison after
  adding any new module copied from original kit source, since the same
  auto-injected-explain inconsistency could exist elsewhere in the
  not-yet-reconstructed modules.

### 2026-07-14 hardening pass

- **Blocking `input()` in 11 confirm prompts** (`memory`, `lessons` x2,
  `aliases`, `clip`, `quick`, `rules`, `docker`, `git`, `notes`, `learn`):
  `/api/exec` and `/ws/terminal` call `engine.execute()` synchronously on
  FastAPI's single-threaded event loop — a real `input()` call (stdin is a
  TTY when `run_backend.py` runs in an interactive console, which is the
  user's actual usage pattern) would block **every connected user**, not
  just the requester. **Fixed**: replaced all y/N `input()` prompts with a
  non-blocking "re-run with a literal `confirm` argument" pattern (e.g.
  `/docker remove <name> confirm`). Verify with `grep -rn "input(" modules/`
  → should be zero hits.
- **`backend/policy.py` double-classification** (`find` in both
  `SAFE_MODULES` and `SYSTEM_MODULES`; `improve` in both `AI_MODULES` and
  `SYSTEM_MODULES`): `allowed_modules()` checks SAFE/AI before SYSTEM in
  server mode, so a module double-listed in SAFE-or-AI *and* SYSTEM gets
  silently **allowed** in server mode despite the SYSTEM listing intending
  to block it. `find` does unrestricted filesystem enumeration; `improve`
  reads arbitrary file contents (up to 50KB) and sends them to an AI
  provider — both are genuine info-disclosure risks if exposed to server-mode
  remote users. **Fixed**: removed both from their SAFE/AI listing, kept
  SYSTEM-only. Verify: `DEPLOYMENT_MODE=server`, hit `/api/blocked`, confirm
  `find` and `improve` show `"system access (blocked in server mode)"`, and
  that `/api/exec` actually rejects them (not just the report).
- **Command injection in `netscan.scan`**: `cmd_scan`'s `subnet` argument
  (raw user input) was interpolated into an f-string (`f"nmap -sn -T4
  {subnet} 2>&1"`) passed to `_run()`, which on Windows hands the whole
  string to `powershell -NoProfile -Command <string>` — PowerShell parses
  `;`, `&`, backticks, `$()` as control characters, so e.g. `/netscan.scan
  127.0.0.1; calc.exe` executed the injected command. **Fixed**: added a
  strict `^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(/\d{1,2})?$` regex validator
  before the subnet ever reaches a shell, and switched the nmap call to
  list-form args. Verify: `/netscan.scan 127.0.0.1; calc.exe` should return
  `"[net.scan] Invalid subnet ..."`, not execute anything; a real CIDR
  (`/netscan.scan 192.168.1.0/30`) should still scan normally. Checked all
  other `shell=True`/`_run(f"...")` call sites in `sysmonitor`, `hardware`,
  `learner`, `netdeep` — all use hardcoded strings or list-form args, no
  other user-controlled interpolation found. `git`/`docker` use list-form
  `subprocess.run` (no shell), so no command injection there, but added a
  `--` separator in `git diff`/`git add` to close a minor CLI-flag-injection
  edge case (e.g. a path argument starting with `-`).

### 2026-07-14 second hardening pass (post module-expansion)

- **`learner.watch` blocking `time.sleep(5)`**: unconditionally froze the
  single-threaded event loop for 5s on every call, for every connected user,
  while not sampling anything real during the wait (strictly worse than
  `/learn.baseline`, which takes one real bounded sample). **Fixed** by
  reusing `/learn.baseline`'s instant capture instead of sleeping.
- **`netscan.watch` blocking `time.sleep(5)`**: same class of bug, but this
  one had a real reason to observe change over an interval (before/after
  connection-count delta), so simply removing the sleep would have lost the
  feature. **Fixed** by splitting into two non-blocking calls: `/netscan.watch`
  captures the baseline and returns immediately; `/netscan.watch finish`
  (called whenever the user is ready) computes the delta against the stored
  baseline. Moves the waiting into the user's own time instead of the shared
  server's. Verified live: first call ~1.6s (real socket enumeration cost,
  not a sleep), `finish` reported an accurate delta over the real elapsed gap.
- **`nettools.latency`'s `count` argument was unbounded**: `/nettools.latency
  <host> 999999` would try to block for roughly count × ~0.25s — a
  user/typo-controlled hang measured in hours, not a fixed 5s like the two
  above. **Fixed** by capping to `max(1, min(count, 30))`, matching the
  existing cap pattern used elsewhere (`git.log` caps at 200, `find` caps at
  200 results). Verified live: `count=999999` completed in ~7s (30 real
  pings), not a hang.
- Swept the rest of the modules tree for the same patterns
  (`time.sleep`/`input(` calls, and `for _ in range(<user-controlled var>)`
  loops containing a subprocess/socket call): every other instance found is
  either a fixed, non-user-controlled iteration count with its own
  per-iteration timeout (bounded aggregate time — `nettools.http-ping`'s
  fixed 5 samples, `nettools.mtu`'s fixed 8-step binary search, `bench.net`'s
  fixed 4 samples), or already explicitly capped (`password.passphrase`'s
  word count). No further instances of this bug class found as of this pass.

### 2026-07-14 DANGEROUS-tier build + audit (27 modules)

Built the entire DANGEROUS tier (`syscmd`, `sudo`, `perms`, `admin`,
`privesc`, `security`, `sec`, `adb`, `fastboot`, `uefi`, `bootmgr`, `boot`,
`firmware`, `fwown`, `disktool`, `device`, `devicescan`, `usbdeep`, `sysint`,
`recovery`, `rootguide`, `dualboot`, `multiboot`, `firstrun`, `selfmod`,
`hardlines`, `crypto`) — 114/114 modules now load. Two real command-
injection bugs were caught and fixed *during* the build itself, both from
embedding a variable into a PowerShell `-Command` string without the
established `_ps_escape()` (single-quote-doubling) guard first used in
`/vm`:

- **`device.py`**: `device_id` interpolated into `Get-PnpDevice -InstanceId
  '{device_id}'` etc. with no escaping at all. **Fixed** by adding the same
  `_ps_escape()` helper `/vm` uses and applying it at all three call sites.
- **`disktool.py`**: `disk` and `partition` interpolated **bare** (no quotes
  at all) into `-DiskNumber {disk}` / `-DriveLetter {partition}` — worse
  than the device.py case since there's no string-boundary protection
  whatsoever. **Fixed** with strict shape validation instead of escaping
  (`disk.isdigit()`, single-alpha drive letter) since these params only
  ever take a narrow type anyway — validating the shape a bare interpolation
  needs is more robust here than trying to quote-escape a bare (unquoted)
  slot. Verified live: `disktool.list-partitions "1; calc.exe"` and
  `device.info "test'; Remove-Item C:/ -Recurse -Force #"` both rejected/
  neutralized, no execution.

Post-build systematic re-audit of all 27 modules (not just the two above)
found no further instances: every other `{var}` embedded in a `-Command`
string is either already `_ps_escape()`-guarded, validated to a narrow
shape first, or provably constrained to a fixed safe literal by the code
path (e.g. `sec.py`'s firewall toggle computes `flag` as `"true"`/`"false"`
via a ternary before it ever reaches the string — not free text). Also
confirmed: zero `time.sleep()`/`input()` calls, every `subprocess.run` has
an explicit `timeout=` (the only calls without one are `privesc`'s two
`Popen` launches, which are intentionally non-blocking UAC/polkit prompts
by design), and zero double-classification across all four policy tiers
(`SAFE`/`AI`/`SYSTEM`/`DANGEROUS` are fully disjoint — 114 unique modules
across all four tiers, matching the sum of tier sizes exactly).

`selfmod`/`hardlines` were built with real write access (per explicit
request) to edit TermAId's own module source / baseline safety-string
constants, scoped to `modules/` only (never `backend/policy.py` or
`backend/main.py` — editing the access-control engine itself is a
different, out-of-scope capability). Every write auto-backs-up first and
`compile()`-validates syntax before committing. Verified live end-to-end:
`hardlines.set-identity` changed `brain._IDENTITY`, then `selfmod.edit`
restored it from the auto-created backup — proving both the write path and
the cross-module recovery path work.

`.env`'s `MODULE_EXTRA_ALLOW` currently opts in all 27 DANGEROUS modules
for testing purposes — trim it down to only what's actually wanted before
this runs unattended; DANGEROUS modules require this even in local mode
(server mode blocks the whole tier regardless, per `backend/policy.py`).
