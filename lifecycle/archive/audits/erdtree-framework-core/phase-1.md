# Phase 1 Audit — core/agent/audit.py + core/context/ (collector/snapshot/cache)

**Slices:**
- `core/agent/audit.py` + `tests/test_audit.py` (prior sibling)
- `core/context/collector.py`, `core/context/snapshot.py`, `core/context/cache.py` + `tests/test_snapshot.py` (this run)

**Date:** 2026-06-21
**Agent:** claude-sonnet-4-6

---

# Context/ slice (collector + snapshot + cache)

## What was built

### core/context/snapshot.py
Typed `SystemSnapshot` dataclass (stdlib only) carrying: hostname, os_name, os_id,
kernel, cpu_model, cpu_cores, mem_total_bytes, mem_avail_bytes, installed_package_count,
installed_packages_sample, failed/active/inactive services, disks (DiskEntry), listen_ports
(PortEntry), recent_audit_lines, collected_at (ISO-8601 UTC), collection_errors.
Serialization: `.to_dict()`, `.to_json()`, `.to_prompt_text()` (compact for prompt injection).
No tier names in any output (I6). No AI/LLM language (I2).

### core/context/collector.py
`Collector` class; each domain isolated, tolerates missing subsystems gracefully.
Domains: `cat /etc/os-release` + `uname -r` (OS), `/proc/cpuinfo` + `/proc/meminfo`
(hardware), `rpm -qa` (packages, Rocky/RHEL not apt), `systemctl list-units` (services),
`df --block-size=1 -x tmpfs` (disks), `ss -tlnpH`/`ss -ulnpH` (TCP/UDP ports + process info),
audit JSONL tail. The `run` callable is injected at construction — default `subprocess.run`,
replaced with fixture runners in tests (the Linux test seam).

### core/context/cache.py
`SnapshotCache` — thread-safe, TTL-based (default 5 s) cache. Live box always source of
truth (decision #5 / I8); cache is latency optimization only. API: `.get()`,
`.get(force=True)`, `.invalidate()`, `.is_warm()`, `.ttl` (settable).

## Test results (context/ slice)

```
48 passed, 2 skipped in 0.14s  (Python 3.13.13, pytest 9.0.3, macOS Darwin 24.5.0)
```

Test classes: OS (4), Hardware (4), Packages (4), Services (4), Disks (4), Ports (5),
Errors (3), Serialization (7), Cache (10), AuditTail (2). 2 skipped = DEFERRED-TO-MOSSAD.

## Invariants verified (context/ slice)

| Invariant | Status |
|---|---|
| I2 — no AI/LLM language in prompt text | VERIFIED by test_no_ai_language_in_prompt_text (whole-word regex) |
| I5 — system context always injectable; graceful on partial | VERIFIED by test_graceful_on_missing_command |
| I6 — no tier/product names in core/ | VERIFIED by reading source + test_no_tier_name_in_prompt_text |
| I8 — cache keeps reads instant within TTL | VERIFIED by test_second_get_returns_same_object + test_ttl_expiry |

## Deferred (DEFERRED-TO-MOSSAD — honest, not fabricated)

- `test_live_collection_rocky_linux`: run on mossad (Rocky Linux 9). Expected: os_id="rocky",
  package_count > 100, port 22 present, collection_errors=[].
- `test_live_cache_invalidation`: TTL expiry under real wall-clock on mossad.

---

# Audit.py slice (prior sibling — preserved)

**Slice:** `core/agent/audit.py` + `tests/test_audit.py`

---

## What was built

### `core/agent/audit.py`
Append-only JSONL audit writer implementing I4. Key design decisions:

- **Atomicity:** Records are built entirely in memory then written via a single `os.write()` to an `O_APPEND` fd. POSIX guarantees this is atomic for writes smaller than `PIPE_BUF` (4 KiB). Records are capped well below this limit via field truncation.
- **fsync-on-write:** `os.fsync(fd)` is called after every `os.write()` call before returning. The caller is guaranteed durable storage before `write()` returns.
- **Partial-write recovery (reader side):** `iter_records()` skips any line that fails `json.loads()`. A crash mid-write leaves an invalid JSON line; it is silently dropped and surrounding records are returned normally.
- **Append-only:** fd opened with `O_CREAT | O_APPEND | O_WRONLY`. No truncation flag. File only ever grows.
- **I6 compliance:** No tier or product names anywhere in the module source (enforced by `TestI6NoTierNames`). The `tier` field is opaque data from the caller.

### Record schema (matches plan §4 Data Model)
```
ts, tier, nl_input, translated_command, tool, args,
permission_decision, exit_code, stdout_summary, stderr_summary, result
```

### Public surface
- `AuditLog(path)` — keep-open context manager for the write hot-path
- `append_record(path, **kwargs)` — one-shot convenience (open / write / close)
- `iter_records(path)` — reader that skips corrupt lines

---

## Test results

```
28 passed in 0.12s  (Python 3.13.13, pytest 9.0.3, macOS Darwin 24.5.0)
```

### Test coverage by category

| Category | Tests | Result |
|---|---|---|
| One line per op | 6 | PASS |
| Append-only | 3 | PASS |
| Partial-write / crash recovery | 5 | PASS |
| fsync-on-write | 3 | PASS |
| Schema / field content | 6 | PASS |
| I6 no tier names in source | 1 | PASS |
| Context-manager lifecycle | 3 | PASS |
| Directory auto-creation | 1 | PASS |

---

## Deferred to MOSSAD (live Linux / Ollama required)

None for this slice. The entire audit module is pure Python using only `os`, `json`, `time`, and `pathlib` — no OS-specific syscalls beyond POSIX. All tests pass on the macOS dev host. No mock or stub required; the module is fully exercised.

---

## Invariants verified

| Invariant | Status |
|---|---|
| I4 — append-only JSONL, every op | VERIFIED by TestOneLine + TestAppendOnly |
| I6 — no tier names in core/ | VERIFIED by TestI6NoTierNames |
| Crash-safe partial-write recovery | VERIFIED by TestPartialWriteRecovery |
| fsync-on-write durability | VERIFIED by TestFsync |

---

# Permissions slice (KEYSTONE — this run)

**Slice:** `core/agent/permissions.py` + `tests/test_permissions.py`
**Date:** 2026-06-21. **Host:** macOS dev host. **Agent:** claude-opus-4-8[1m].
Pure logic — no model/Linux/network. Fully testable on the dev host.

## What was built — public surface
- `OpClass` = READ | WRITE | DESTRUCTIVE
- `Gate` = ALLOW | CONFIRM | CONFIRM_TYPED | REFUSE
- `ExecContext(interactive, remote)`
- `Decision(op_class, gate, reason, auto_ok)` (frozen) + `.requires_typed_word`, `.confirm_word`
- `classify(command, context) -> Decision`
- `confirms_destructive(typed) -> bool` — only literal `DESTROY` typed IN FULL (whitespace-
  trimmed, case-sensitive) clears the gate; ""/"y"/"yes"/partial/None all fail.
- `is_auto_confirmable(decision) -> bool` — True ONLY for read/ALLOW.
- `DESTRUCTIVE_CONFIRM_WORD = "DESTROY"`

## Gate derivation (SC5 / I3)
- READ -> ALLOW (auto_ok), even non-interactively.
- WRITE -> CONFIRM interactively; **REFUSE non-interactively**; never auto.
- DESTRUCTIVE -> CONFIRM_TYPED interactively; **REFUSE non-interactively** (no human to
  type the word); never auto_ok in ANY context.

## Classification design
Precedence: DESTRUCTIVE whole-string taxonomy -> sub-command map (systemctl/dnf/firewall-
cmd/git/ip; a read sub-verb like `ip addr` cannot mask `ip addr add`) -> read commands ->
write shapes -> **default-deny floor (unknown shape => at least WRITE, never READ)**.
`sudo`/`doas`/`env`/`VAR=val` prefixes are stripped so they cannot hide a verb. Read verbs
(`echo`,`cat`) with `>` redirection escalate to write, or destructive when the target is a
block device or critical file. Unparseable quoting => not-read.

Destructive taxonomy covers: rm -rf/-fr/--force, rm of root/`/etc/*`/`~`/`$HOME`/SSH keys,
mkfs/mke2fs/wipefs/blkdiscard/shred, `find -delete` / `find -exec rm`, dd-to-/dev, redirect-
to-/dev, fdisk/gdisk/sgdisk/parted/sfdisk/cryptsetup, pv|vg|lv remove, zpool destroy,
reboot/shutdown/poweroff/halt/init 0|6, systemctl reboot/poweroff/isolate/set-default
emergency, grub install/mkconfig, userdel, groupdel wheel|sudo, passwd -l / passwd root,
usermod -L / nologin, chsh nologin, systemctl stop|disable|mask sshd, truncate/rm of
sshd_config & authorized_keys, iptables -P INPUT DROP, nft flush ruleset, ufw disable|reset,
firewall-cmd --panic-on, systemctl stop firewalld, truncate/rm of /etc/{fstab,passwd,shadow,
sudoers}, setenforce 0, fork bomb, killall -9 -1, dnf remove|erase|autoremove (cascade risk).

## Test results
```
427 passed in 0.22s   (python3 -m pytest tests/test_permissions.py -q, Python 3.13.13, macOS)
```
Curated corpora: READ 32, WRITE 26, DESTRUCTIVE 68. Keystone whole-corpus assertion:
across every destructive op x every (interactive x remote) context — ALWAYS DESTRUCTIVE,
NEVER auto_ok, NEVER auto-confirmable, REFUSE when non-interactive. Only literal `DESTROY`
in full clears the gate.

### Adversarial self-review (found + fixed 2 under-gates, then added to corpus)
- `find ... -delete` was READ -> now DESTRUCTIVE.
- `truncate -s 0 /etc/fstab` was WRITE -> now DESTRUCTIVE.
Already-correct sneaky variants: `rm -rf --no-preserve-root /`, `/bin/rm -rf /home`,
`sudo  dd if=/dev/zero of=/dev/sda` (extra spaces), `ssh host "rm -rf /"`, `mkfs.xfs  /dev/sdb`,
`systemctl --no-block poweroff`.

## Invariants
| Invariant | Status |
|---|---|
| I3 — destructive gated+typed, never auto, refused non-interactive | VERIFIED by test_no_destructive_op_is_ever_auto_confirmable + per-op tests |
| I2 — no AI/LLM language in user-facing strings | VERIFIED: all `reason` strings are plain Linux safety text; "AI/LLM/agent/model" only in the docstring documenting the rule |
| I6 — no tier names in core/ | VERIFIED: grep marika\|radagon\|radahn\|starscourge => NONE |
| I8 — read path instant | 427-case suite in 0.22s; read path is regex + one tokenize |

## Deferred
None for this slice — pure logic, fully exercised on the dev host. No live model / Linux /
network involved. (Wiring `classify()` into audit.py + tool execute() is Phase 2; the
interactive prompt that consumes `confirm_word` is Phase 4.)

**passed=true: code complete + 427 unit tests green; nothing fabricated; no live items deferred in this slice.**
