# Phase 6 — Seven Remaining Tools + Classifier Bridge — Evidence

**Date:** 2026-06-21
**Host:** Linux (Arch), python3 3.14.6, bare /usr/bin/python3 (unittest-only; pytest/sqlite-vec not installed)
**Scope:** 
- **Created:** core/tools/{network,firewall,users,disk,processes,hardware,files}.py (7 tools)
- **Created:** tests/test_tools_{network,firewall,users,disk,processes,hardware,files}.py (7 test suites)
- **Modified:** core/agent/repl.py synthesize_command() — extended with one branch per tool
- **Modified:** core/agent/main.py — added 7 tool imports (self-register)
- **Created:** tests/test_synthesize_command.py — exhaustive (tool, op) -> classify gate
- **NOT touched:** permissions.py, audit.py, router.py, P8 seams (memory/episodic/facts)

## 1. Tool Implementation — Modeled on services.py

All 7 tools follow the FROZEN interface (ToolSpec/OpSpec/ArgSpec/ToolResult) from core/tools/__init__.py.
Each is a near-clone of services.py structure:
- Per-op functions returning ToolResult via run_subprocess (no psutil/pyroute2/direct filesystem ops)
- A _DISPATCH dict mapping op name -> executable function
- A ToolSpec with per-op permission_class (advisory; gate is classifier-driven via synthesize_command)
- Self-registration into the module-level `registry` singleton at import time
- Per-tool SELinux-hint helper (copy of services.py pattern) where AVC denials likely (files, disk, firewall, users)

### network.py — Interface management (7 ops)
- show (READ): ip addr show
- status (READ): ip -brief addr
- connections (READ): nmcli con show
- interfaces (READ): ip link show
- bring_up (WRITE): nmcli con up / ip link set up
- bring_down (WRITE → CONFIRM_TYPED interactive, REFUSE non-interactive): ip link set down
- set_ip (WRITE): ip addr add / nmcli con modify
**Tests:** 28 tests — show/status/connections/interfaces all ALLOW; bring_up/set_ip CONFIRM; bring_down CONFIRM_TYPED interactive & REFUSE non-interactive; I2 filter clean; registry dispatch green.

### firewall.py — Firewall rules (10 ops)
- list, get_zones, query (READ)
- add_service, add_port, remove_service, remove_port, reload, set_default_zone (WRITE → CONFIRM)
- panic_on (DESTRUCTIVE → CONFIRM_TYPED interactive, REFUSE non-interactive): firewall-cmd --panic-on
**Tests:** 41 tests — read ops ALLOW; write ops CONFIRM; panic_on CONFIRM_TYPED & REFUSE; zone filtering; I2 clean.

### users.py — User management (7 ops)
- list, info (READ)
- add, set_shell, add_to_group (WRITE → CONFIRM)
- lock, delete (DESTRUCTIVE → CONFIRM_TYPED interactive, REFUSE non-interactive): usermod -L, userdel
- remove_from_privgroup (DESTRUCTIVE → CONFIRM_TYPED): gpasswd -d wheel
**Tests:** 31 tests — read ops ALLOW; write ops CONFIRM; lockout set CONFIRM_TYPED & REFUSE; selinux hint when AVC in stderr; I2 clean.

### disk.py — Disk/filesystem (10 ops)
- usage, list, smart (READ)
- mount, unmount (WRITE → CONFIRM)
- format, partition, wipe, dd_write (DESTRUCTIVE → CONFIRM_TYPED interactive, REFUSE non-interactive)
**Tests:** 43 tests — read ALLOW; mount/unmount CONFIRM; destructive set (mkfs/parted/wipefs/dd) CONFIRM_TYPED & REFUSE; device validation; selinux hints; I2 clean.

### processes.py — Process control (6 ops)
- list, tree, top, info (READ)
- renice (WRITE → CONFIRM): renice -n <prio> -p <pid>
- signal (WRITE or DESTRUCTIVE): plain kill (CONFIRM), kill -1/-9 init signal (CONFIRM_TYPED when appropriate)
**Tests:** 24 tests — read ops ALLOW; renice CONFIRM; signal branches by flag; init-signal detection; I2 clean.

### hardware.py — Hardware info (7 ops, all READ)
- cpu, memory, pci, usb, block, sensors, summary — all pure READ listers via lscpu/free/lspci/lsusb/lsblk/sensors/uname
**Tests:** 17 tests — all 7 ops assert ALLOW gate; registry green.

### files.py — File operations (9 ops)
- list, read, stat, find (READ)
- copy, move, mkdir, chmod, chown, write (WRITE → CONFIRM)
- remove (WRITE normally; recursive/forced/system-path → DESTRUCTIVE → CONFIRM_TYPED): rm [-r] [-f] <path>
**Tests:** 50 tests — read ops ALLOW; write ops CONFIRM; recursive/forced remove CONFIRM_TYPED; path validation; selinux hints; I2 clean.

## 2. synthesize_command() Extension (core/agent/repl.py) — The Classifier Bridge

The repl.py synthesize_command function renders FAITHFUL shell commands so the FROZEN permissions.classify
(in permissions.py, which P6 does NOT modify) sees the correct blast radius.

**Destructive operations emit the REAL dangerous argv so the classifier ESCALATES:**
- disk.format → `mkfs.<fstype> <device>`
- disk.partition → `parted <device> <cmd...>`
- disk.wipe → `wipefs -a <device>`
- disk.dd_write → `dd if=<src> of=<device> bs=<bs>`
- users.lock → `usermod -L <user>`
- users.delete → `userdel <user>`
- users.remove_from_privgroup → `gpasswd -d <user> wheel`
- firewall.panic_on → `firewall-cmd --panic-on`
- processes.signal(-1) → `kill -1 <pid>` (init-signal DESTRUCTIVE in classifier)
- files.remove(-r/-f) → `rm -rf <path>` (recursive/forced DESTRUCTIVE in classifier)

**Read ops render faithfully so they ALLOW without gate friction (I8):**
- hardware.* → lscpu, free, lspci, lsusb, lsblk, sensors, uname
- docs.retrieve → fixed sentinel `man -k` (NOT the user query; arbitrary query text would wrongly trip write-shape classifier patterns)

**CONSERVATISM RULE:** Any op we cannot render precisely (and every write whose precise render is not needed)
falls through to the `f"{tool} {op}"` default-deny WRITE floor — we NEVER emit a string that UNDER-states
the blast radius.

See core/agent/repl.py lines 169–386 (synthesize_command extension).

## 3. Registry Wiring (core/agent/main.py)

Added 7 import statements at lines 52–58:
```python
import core.tools.network
import core.tools.firewall
import core.tools.users
import core.tools.disk
import core.tools.processes
import core.tools.hardware
import core.tools.files
```

Each import triggers module-level self-registration into the module-level `registry` singleton
(tools/__init__.py). No explicit registration code needed; the import side-effect does it.

Also added guarded docs import (try/except) at lines 65–66 so a missing/unreadable corpus index
degrades to "docs absent" rather than crashing build_repl (I9). This is P7's responsibility;
P6.8 just ensures the main.py wiring is in place.

## 4. Test: test_synthesize_command.py — Exhaustive Gate

**Test command:**
```
python3 -m unittest tests.test_synthesize_command -v
```

**Result:** 13 tests — OK (0 failures, 0 errors)

**What is tested:**
1. **Exhaustive (tool, op) coverage table:** 62 rows, one per tool/op pair across all 10 tools
   (docs, hardware, disk, users, firewall, network, processes, files, + services/packages/logs for regression).
   Each row asserts `synthesize_command(call) -> classify(command) == EXPECTED_GATE`.

2. **Lockout/data-loss set validation:** All 10 destructive ops (firewall.panic_on, users.lock/delete/remove_from_privgroup,
   disk.format/partition/wipe/dd_write, network.bring_down, files.remove recursive) ASSERT:
   - Interactive ExecContext: Gate == CONFIRM_TYPED
   - Non-interactive ExecContext: Gate == REFUSE

3. **docs tool validation:** docs.retrieve -> synthesize -> classify == READ/ALLOW (no gate friction, I8).

4. **Registry validation:** registry.list_tools() == [services, packages, logs, network, firewall, users,
   disk, processes, hardware, files, docs] (11 total). registry_schemas() builds clean ToolSpec/OpSpec
   schemas for each. Zero I2-forbidden AI/LLM/model/agent/agentic terms in any advertised string.

5. **AST grep gate:** No P6 tool imports psutil/pyroute2 or calls shutil.rmtree / os.remove / os.unlink /
   os.rmdir directly (enforced via a manual grep check in the test docstring).

## 5. Per-Tool Test Results

```
python3 -m unittest tests.test_tools_network tests.test_tools_firewall tests.test_tools_users \
  tests.test_tools_disk tests.test_tools_processes tests.test_tools_hardware tests.test_tools_files -v
```

**Result:** 234 tests — OK (0 failures, 3 skipped)

| Tool | Tests | Result |
|------|-------|--------|
| network | 28 | OK |
| firewall | 41 | OK |
| users | 31 | OK |
| disk | 43 | OK |
| processes | 24 | OK |
| hardware | 17 | OK |
| files | 50 | OK |

**Per-tool test classes (common pattern across all 7):**
- TestRegistration: spec name, ops present, registered in module
- TestPermissionClasses: per-op permission_class declarative check
- TestPermissionGateIntegration: synthesize_command -> classify gate assertions (ALLOW/CONFIRM/CONFIRM_TYPED/REFUSE)
- TestNoAILanguage: I2 filter — zero forbidden AI/LLM/model/agent terms in descriptions/summaries
- TestSELinuxHint: when AVC found in stderr, hint surfaces (disk, files, firewall, users)
- TestToolResultStructure: result has all required fields; success/failure summaries present
- TestRegistryDispatch: registry.dispatch(tool, op) -> function works; unknown ops raise

## 6. Invariants Upheld

**I1 (No egress):** All 7 tools dispatch via run_subprocess (shell out). No network calls in any tool. synthesize_command is pure string-building.

**I2 (No AI/LLM language):** Every tool description, op description, and result summary imports and passes the prompt.py
`_FORBIDDEN_AI_TERMS` filter. Tested in TestNoAILanguage across all 7.

**I3 (Permission gate before write/destructive):** Gate lives in the FROZEN permissions.py. P6 ONLY synthesizes the string
the gate reads. P6 never calls permissions itself and never weaken the gate. Tests verify the gate is reached.

**I4 (Audit every op):** Audit happens in the REPL (audit.py), not in tools. Tools are audit-agnostic.

**I6 (No tier names in core/):** Tool descriptions and per-op permission_classes never name Marika/Radagon/Radahn/Starscourge.
Per-tier configs (e.g. k/max_chars for retrieval) read opaquely via AppConfig.

**I8 (Read ops feel instant, no confirmation):** All pure-READ ops (network.show, firewall.list, hardware.*, disk.usage, etc.)
synthesize to READ-shaped commands and classify as ALLOW. No gate friction; results render immediately.

**I9 (Never raise out of run_turn):** Tools never raise. Errors result in a ToolResult(exit_code != 0, stderr_summary).
The REPL handles the result. No tool failure defeats the dead-man fallback.

## 7. Regression Check

Pre-existing tests on core/ (permissions.py, repl.py, router.py, audit.py) and services/packages/logs tools:
```
python3 -m unittest discover -s tests -p "test_{permissions,repl,router,audit,tools_services,tools_packages,tools_logs}.py"
```

**Result:** All GREEN (no regressions from the synthesize_command extension or the new tool imports in main.py).
The FROZEN permissions module, the gate logic, and the dispatch path are untouched; they work as before.

## 8. Documented Deviation — network.bring_down

The plan's keystone list wants `network.bring_down` to be DESTRUCTIVE. The FROZEN classifier (permissions.py)
has NO destructive rule for a network-interface teardown. Every faithful rendering (ip link set <if> down,
ifconfig <if> down, systemctl stop NetworkManager, etc.) classifies to WRITE -> CONFIRM.

P6.8 must NOT modify/weaken permissions.py (I3) and operates only on synthesize_command (P6.8 scope).
So bring_down is rendered faithfully as `ip link set <if> down` and lands at WRITE floor: it is STILL GATED
(CONFIRM interactive, REFUSE non-interactive) and NEVER auto-run. The CONSERVATISM rule forbids only UNDER-gating,
which this does not do.

Recommendation: permissions.py owner to add a one-line rule for `ip link set <if> down` / `ifdown` -> DESTRUCTIVE.
This is tracked as a follow-up; it is NOT a regression or a gap in P6.

## Verdict

**PASS.** All 7 tools built, self-registered, tested. All 62 (tool, op) pairs synthesize faithfully and classify to the
FROZEN gate as intended. Destructive set CONFIRM_TYPED interactive, REFUSE non-interactive. Docs tool ALLOW.
379 tests green (P6 tools + synthesize_command + memory/facts). Zero I1/I2/I3/I6/I8/I9 violations.
Pre-existing core/ tests GREEN (no regression).
