# Phase 2 Audit Evidence — Tool Registry (core/tools/__init__.py)

Date: 2026-06-21
Executor: claude-sonnet-4-6

## Scope

Phase 2 REGISTRY slice only: `core/tools/__init__.py` — the frozen shared
contract that `router.py` (Phase 4) and every tool bind to.

## Files touched

- `core/tools/__init__.py` — CREATED (new; did not exist)
- `tests/test_tools_registry.py` — CREATED (new; did not exist)

No other files were modified.

## What was built

### core/tools/__init__.py

Defines the complete tool interface contract:

| Symbol | Role |
|---|---|
| `ToolResult` | Frozen dataclass: `exit_code`, `stdout`, `stderr`, `summary`. The structured return type every `execute()` must produce. `.ok` property, `.as_dict()` for audit transcription. |
| `ArgSpec` | Schema for one argument: name, type, required, description, default. |
| `OpSpec` | Declaration of one tool operation: `op_name`, `permission_class` (from `core.agent.permissions.OpClass`), `args: list[ArgSpec]`, `description`. |
| `ToolSpec` | Complete tool descriptor: `name`, `ops: dict[str, OpSpec]`, `execute: Callable[[str, dict], ToolResult]`, `description`. Methods: `get_op()`, `permission_class_for()`. |
| `ToolRegistry` | Central registry: `register()`, `unregister()`, `get()`, `list_tools()`, `permission_class_for(tool, op)`, `dispatch(tool, op, args)`. |
| `_validate_args()` | Internal: validates args dict against declared `ArgSpec` list; raises `TypeError` on violation. |
| `run_subprocess()` | Shared helper for tool implementations: shells out via `subprocess.run()`, returns `ToolResult`, never raises on non-zero exit, enforces timeout. Exit codes: 0=ok, 1=error, 124=timeout, 127=not found. |
| `registry` | Module-level singleton `ToolRegistry` instance. Individual tool modules register against this. |

### Invariant compliance

| Invariant | How satisfied |
|---|---|
| I2 (no AI language) | Zero AI/LLM/model/agent/agentic strings in any user-facing output path. |
| I3 (permission gate) | `dispatch()` doc-contracts that the caller has already resolved the gate; the registry validates args but does NOT re-run the gate (gate is the caller's concern, as in Phase 1 design). `permission_class_for()` lets Phase 4 router look up the declared class before prompting the user. |
| I4 (audit) | `ToolResult.as_dict()` maps 1:1 to `AuditLog.write()` fields. The caller (router.py) is responsible for writing the audit record after dispatch. |
| I6 (no tier names) | Zero "marika", "radagon", or product names in this file. `grep -n 'marika\|radagon\|rocky' core/tools/__init__.py` returns nothing. |

## Test results

```
platform darwin -- Python 3.13.13, pytest-9.0.3
33 passed in 0.15s (tests/test_tools_registry.py)
916 passed, 2 skipped (full suite — no regressions)
```

### Test coverage

- `ToolResult`: ok, frozen, as_dict
- `ToolRegistry`: register, duplicate guard, lookup, list (sorted), unregister
- `permission_class_for`: known read, known write, unknown tool, unknown op
- `dispatch`: read round-trip, write with args, optional args, unknown tool (KeyError), unknown op (ValueError), missing required arg (TypeError), wrong arg type (TypeError), extra args accepted
- Full lifecycle simulation: DESTRUCTIVE op — register, look up permission class, dispatch, verify ToolResult fields are audit-ready
- `run_subprocess`: success, nonzero exit, timeout (exit 124), not-found (exit 127), OSError
- Module-level `registry` singleton import and type check

## Deferred to mossad

None — this slice is pure logic; no live subprocess execution or Linux
subsystem is required. All tests pass on the macOS dev host.

---

# Phase 2 Audit Evidence — Services Tool (core/tools/services.py)

Date: 2026-06-21
Executor: claude-sonnet-4-6

## Scope

Phase 2 SERVICES slice: `core/tools/services.py` + `tests/test_tools_services.py`.
Implements the systemctl/journalctl service management tool against the frozen
interface in `core/tools/__init__.py`.

## Files touched

- `core/tools/services.py` — CREATED (new; did not exist)
- `tests/test_tools_services.py` — CREATED (new; did not exist)

No other files were modified.

## What was built

### core/tools/services.py

Eight operations against the Phase 2 tool interface:

| Op | Permission class | Command |
|---|---|---|
| `status` | READ | `systemctl status --no-pager <unit>` |
| `start` | WRITE | `systemctl start <unit>` |
| `stop` | WRITE | `systemctl stop <unit>` |
| `restart` | WRITE | `systemctl restart <unit>` |
| `enable` | WRITE | `systemctl enable <unit>` |
| `disable` | WRITE | `systemctl disable <unit>` |
| `logs` | READ | `journalctl -u <unit> -n <lines> --no-pager` |
| `mask` | WRITE | `systemctl mask <unit>` |

Structural details:
- All subprocess calls go through `run_subprocess()` from `core.tools` — no direct `subprocess` usage.
- SELinux AVC detection: stderr/stdout scanned for AVC denial patterns; when found, a hint pointing to `ausearch`/`journalctl -t setroubleshoot` is appended to the summary.
- `logs` lines argument: clamped to [1, 500]; default 50. Used `None`-check (not `or`) to correctly handle `lines=0` input.
- Self-registers into module-level `registry` singleton on import.
- Zero tier/product names (I6). Zero AI/LLM/model/agent language (I2).
- `execute()` does NOT call `permissions.classify()` or write audit itself — both are the Phase 4 router's responsibility (I3/I4 contract).

### Invariant compliance

| Invariant | How satisfied |
|---|---|
| I2 (no AI language) | Verified by `TestNoAILanguage` across all 8 ops x success/failure paths. |
| I3 (permission gate) | `execute()` trusts the gate was resolved externally. Permission class declared per-op in `SERVICES_SPEC.ops`. `TestPermissionGateIntegration` verifies that `permissions.classify()` agrees with the declared class for the actual command strings. |
| I4 (audit) | `TestAuditIntegration` demonstrates the full caller-writes-audit pattern: execute, then `AuditLog.write()` with the result. |
| I6 (no tier names) | Zero tier/product strings in services.py. |

## Test results

```
platform darwin -- Python 3.13.13, pytest-9.0.3
84 passed, 3 skipped in 0.15s (tests/test_tools_services.py)
```

All subprocess calls mocked via `patch("core.tools.services.run_subprocess")`.

### Test coverage

- Registration: spec in registry, name, all 8 ops present
- Permission classes: READ for status/logs; WRITE for start/stop/restart/enable/disable/mask
- Permission gate integration: classify() returns ALLOW for read ops, CONFIRM for write ops
- Each op: success path (ok=True, correct summary) + failure path (ok=False, error summary)
- logs: default lines (50), custom lines, max clamp (500), min clamp (0→1), line count in summary
- mask: WRITE class confirmed
- SELinux hints: AVC in stderr/stdout → hint in summary; clean stderr → no hint
- ToolResult structure: all 8 ops x required fields + as_dict() keys
- Audit integration: read op + write op — audit record written, correct fields
- Registry dispatch: status, restart, missing unit arg (TypeError), unknown op (ValueError), logs with lines
- No AI language: 8 ops x success, 3 ops x failure

## Deferred to mossad

3 tests explicitly marked `DEFERRED-TO-MOSSAD`:
- `test_live_status_sshd` — real `systemctl status sshd` on the target Linux host
- `test_live_logs_sshd` — real `journalctl -u sshd` on the target Linux host
- `test_live_restart_requires_sudo` — real `systemctl restart crond` (privilege + gate verification)

---

# Phase 2 Audit Evidence — Logs Tool (core/tools/logs.py)

Date: 2026-06-21
Executor: claude-sonnet-4-6

## Scope

Phase 2 LOGS slice: `core/tools/logs.py` — journalctl + dmesg query/filter/tail/since
tool, plus `tests/test_tools_logs.py`.

## Files touched

- `core/tools/logs.py` — CREATED (new; did not exist)
- `tests/test_tools_logs.py` — CREATED (new; did not exist)

No other files were modified.

## What was built

### core/tools/logs.py

Six operations against the Phase 2 tool interface:

| Op | Permission class | Backend |
|---|---|---|
| `query` | READ | `journalctl --no-pager --output=short-iso` with unit/since/until/priority/lines/grep/identifier/boot filters |
| `tail` | READ | `journalctl --no-pager -n N` (default 50), optional unit |
| `since` | READ | `journalctl --no-pager --since <expr>` with optional unit/lines cap |
| `boot_errors` | READ | `journalctl --boot <id> -p err` (default current boot) |
| `dmesg_query` | READ | `dmesg --color=never -T` with optional level/-l, --since, python-side grep, tail cap |
| `dmesg_errors` | READ | `dmesg --color=never -T -l err,crit,alert,emerg`, tail cap |

Structural details:
- SELinux awareness: `_extract_selinux_hints()` parses AVC denial lines via `_AVC_RE`
  and returns audit2allow-style remediation text per denial, included in `ToolResult.stderr`.
- dmesg grep filter applied in Python (not via shell pipe) so bad regexes return a clean
  `exit_code=1` without launching a subprocess.
- dmesg level names mapped to kernel numbers (err→3, warn/warning→4, etc.).
- Output capped via `_head_lines()` (journalctl) and `_tail_lines()` (dmesg) to keep
  results within model context budget.
- All subprocess calls go through `run_subprocess()` from `core.tools`.
- Self-registers into module-level `registry` singleton at import time.
- Zero tier/product names (I6). Zero AI/LLM/model/agent language (I2).

### Invariant compliance

| Invariant | How satisfied |
|---|---|
| I1 (localhost only) | All subprocess calls target `journalctl` and `dmesg` — local Linux binaries, no network endpoints. Verified by `TestEgressInvariant`. |
| I2 (no AI language) | Verified by `TestNoAILanguage` across all ops + SELinux hints + ToolSpec descriptions. |
| I3 (permission gate) | All 6 ops declared READ; gate is the caller's responsibility. `TestPermissionGate` verifies ops and `permissions.classify()` agreement. |
| I4 (audit) | `TestExecuteDispatcher.test_execute_result_is_audit_compatible` writes the result into a real `AuditLog`. |
| I6 (no tier names) | `TestNoTierNames` greps source for marika/radagon/rocky/starscourge/radahn — all absent. |

## Test results

```
platform darwin -- Python 3.13.13, pytest-9.0.3
92 passed, 5 skipped in 0.14s (tests/test_tools_logs.py)
1092 passed, 10 skipped in 0.91s (full suite — no regressions)
```

All subprocess calls mocked via `patch("subprocess.run")`.

### Test coverage

- Registration: tool in global registry, name, all 6 ops, all READ, no AI language in spec
- Permission gate: all ops READ via op_spec; `permissions.classify()` returns ALLOW for journalctl and dmesg commands
- SELinux hints: no AVC → empty list; single AVC → 1 hint with scontext/tcontext/audit2allow text; two AVCs → 2 hints; empty string safe
- Line caps: `_head_lines` truncates at N with notice; `_tail_lines` returns last N lines
- journalctl query: cmd vector shape; unit/-u, --since, --until, -p, -n, --grep, -t, --boot flags; default 100 lines; ToolResult structure; success/error exit codes; AVC hints in output+summary
- journalctl tail: --no-pager, default 50 lines, custom lines, unit filter, ToolResult
- journalctl since: --since flag, unit filter, default fallback to "1 hour ago", lines cap, ToolResult
- journalctl boot_errors: default boot=0, custom boot, -p err flag, ToolResult
- dmesg_query: --color=never -T; level→-l mapping (err=3, warn=4, warning=4); python-side grep filter; no-match→empty stdout; bad regex→exit_code=1 without subprocess; --since flag; lines cap (default 200); AVC hints; ToolResult
- dmesg_errors: -l err,crit,alert,emerg; default 100 lines; custom lines; ToolResult
- execute() dispatcher: all 6 ops; unknown op → exit_code=1; audit-compatible ToolResult
- Registry dispatch: all 6 ops; since missing required arg → TypeError; unknown op → ValueError; wrong arg type → TypeError
- Egress invariant: all subprocess calls use journalctl or dmesg only, no URL-like tokens
- No AI language: execute() results, SELinux hints, TOOL_SPEC descriptions
- No tier names: source-level check for marika/radagon/rocky/starscourge/radahn

## Deferred to mossad

5 tests marked `DEFERRED-TO-MOSSAD`:
- `test_live_journalctl_query_returns_output` — real journalctl on a live Linux host
- `test_live_journalctl_boot_errors` — real journalctl --boot on a live Linux host
- `test_live_dmesg_query_returns_output` — real dmesg on a live Linux host
- `test_live_dmesg_errors` — real dmesg -l err on a live Linux host
- `test_live_selinux_avc_hint_end_to_end` — SELinux enforcing mode with triggered AVC denial

---

# Phase 2 Audit Evidence — Packages Tool (core/tools/packages.py)

Date: 2026-06-21
Executor: claude-sonnet-4-6

## Scope

Phase 2 PACKAGES slice: `core/tools/packages.py` + `tests/test_tools_packages.py`.
Implements the dnf package-management tool (Rocky Linux 9 / RHEL) against the
frozen interface in `core/tools/__init__.py`.

## Files touched

- `core/tools/packages.py` — CREATED (new; did not exist)
- `tests/test_tools_packages.py` — CREATED (new; did not exist)

No other files were modified.

## What was built

### core/tools/packages.py

Five operations against the Phase 2 tool interface:

| Op | Permission class | Command |
|---|---|---|
| `search` | READ | `dnf search --color=never <keyword>` |
| `info` | READ | `dnf info --color=never <package>` |
| `install` | WRITE | `dnf install -y --color=never <packages...>` |
| `update` | WRITE | `dnf update -y --color=never [packages...]` (empty = full-system) |
| `remove` | DESTRUCTIVE | dry-run via `dnf remove --assumeno`, then real `dnf remove -y` if gate cleared |

Structural details:
- All subprocess calls go through `run_subprocess()` from `core.tools`.
- SELinux AVC detection: `_selinux_hint()` scans stderr for `avc: denied` /
  `type=AVC` patterns; appended to summary when detected.
- Destructive remove detection: `_parse_transaction_plan()` extracts package
  names from the `Removing:` section of `dnf --assumeno` output. If any match
  `_is_critical_package()` (kernel, openssh, sudo, bash, glibc, grub2, etc.),
  a WARNING is appended to the summary.
- Two-phase remove: `_exec_remove()` always runs a dry-run first. If
  `gate_cleared=False` (default), returns a preview `ToolResult` with
  `exit_code=None` so the router can surface the transaction plan before
  prompting the user. With `gate_cleared=True`, the real remove runs.
- Self-registers into module-level `registry` singleton on import.
- Zero tier/product names (I6). Zero AI/LLM/model/agent language (I2).

### Invariant compliance

| Invariant | How satisfied |
|---|---|
| I2 (no AI language) | `TestI2InvariantAllPaths` runs whole-word regex against all 9 executor code paths. |
| I3 (permission gate) | `execute()` trusts the gate was resolved externally. `remove` declares DESTRUCTIVE; router must resolve `CONFIRM_TYPED` gate before passing `gate_cleared=True`. |
| I4 (audit) | Callers write audit after dispatch (registry/router contract). ToolResult fields map 1:1 to AuditLog.write() parameters. |
| I6 (no tier names) | Zero "marika"/"radagon"/"rocky" strings in packages.py. |

## Test results

```
platform darwin -- Python 3.13.13, pytest-9.0.3
77 passed in 0.15s (tests/test_tools_packages.py)
1169 passed, 10 skipped (full suite — no regressions)
```

All subprocess calls mocked via `patch("subprocess.run")`.

### Test coverage

- `_selinux_hint`: avc:denied hit, type=AVC hit, case-insensitive, miss, no AI language
- `_is_critical_package`: kernel/kernel-core/kernel-versioned, openssh/openssh-server,
  sudo, bash, glibc, grub2-common; non-critical (htop/vim/nginx/python3)
- `_parse_transaction_plan`: basic single, kernel (2 pkgs), ssh, multi-package, no-section, empty
- `PACKAGES_SPEC`: registered in global registry, all 5 ops declared, correct permission
  classes, unknown op returns None, dispatch unknown op raises ValueError
- `search`: success, no matches (exit 1), other error (exit 2), no AI language
- `info`: success, not found (exit 1), other error, no AI language
- `install`: success, failure, empty package list guard, multiple packages, SELinux hint, no AI language
- `update`: full-system (empty packages), named package, failure, None as full-system, no AI language
- `remove` dry-run: gate absent preview, gate=False preview, preview surfaces names,
  non-critical no WARNING, kernel WARNING, SSH WARNING, empty list guard
- `remove` gate-cleared: success (2 subprocess calls), failure, SELinux hint, kernel WARNING, no AI language
- Registry round-trip: search/info dispatched through global registry; permission class lookup
- I2 invariant scan: 9 paths x all AI terms (whole-word regex)

## Deferred to mossad

All live execution deferred:
- Real `dnf search`/`dnf info` on Rocky Linux 9 with actual repos
- Real `dnf install`/`dnf remove`/`dnf update` (requires root + RPM database)
- SELinux AVC triggers via post-install scriptlets (requires enforcing SELinux)
- Kernel/SSH cascade removal dry-run against actual dnf dependency solver
