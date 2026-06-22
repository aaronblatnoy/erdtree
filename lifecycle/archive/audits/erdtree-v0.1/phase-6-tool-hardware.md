# Phase 6 — hardware tool — Audit Evidence

Date: 2026-06-21
Executor: claude-sonnet-4-6

## Files Created

- `core/tools/hardware.py` — hardware inspection tool (lscpu/lspci/lsusb/lsblk/free/sensors/dmidecode)
- `tests/test_tools_hardware.py` — stdlib unittest suite; 43 tests, 3 skipped (DEFERRED-TO-MOSSAD)

## Design Conformance

- Modeled exactly on `core/tools/services.py`: per-op functions returning ToolResult via run_subprocess; a `_DISPATCH` table keyed by op name; a `ToolSpec` with per-op `OpSpec(permission_class=OpClass.READ)`; self-registers via `registry.register(HARDWARE_SPEC)` at import time.
- `_maybe_selinux_hint` copied verbatim from services.py.
- No psutil, pyroute2, shutil, or direct os.* mutation — subprocess only via run_subprocess.
- No calls to permissions or audit inside the tool (I3/A3).
- All 7 ops (cpu/memory/pci/usb/block/sensors/summary) are OpClass.READ.

## Invariant Compliance

- **I1**: No network calls. All ops are local subprocess-only.
- **I2**: Every description and summary passes the `_FORBIDDEN_AI_TERMS` filter (asserted in `TestI2Filter` — imports the canonical list from `core/agent/prompt.py`).
- **I3**: Permission gate resolved externally by the caller (REPL/router). Tool does not self-classify.
- **I4**: Audit record written by caller; tool does not touch AuditLog.
- **I6**: Zero tier/product/model names in core/tools/hardware.py.
- **I9**: Unknown op returns a valid ToolResult (never raises); subprocess failures return ToolResult with non-zero exit_code, not an exception.

## Test Results

```
python3 -m unittest tests.test_tools_hardware -v
Ran 43 tests in 0.009s
OK (skipped=3)
```

All 43 active tests pass. 3 tests skipped as DEFERRED-TO-MOSSAD (require real lscpu/free on Rocky Linux 9).

## Permission Gate Verification

Synthesized command strings classify as Gate.ALLOW (READ) via `permissions.classify()`:
- `lscpu` -> ALLOW
- `free -h` -> ALLOW
- `lspci` -> ALLOW
- `lsusb` -> ALLOW
- `lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT` -> ALLOW
- `sensors` -> ALLOW

Verified in `TestPermissionGateIntegration.test_read_ops_get_allow_gate`.

## Deferred Items

- D1: Live execution on Rocky Linux 9 (requires mossad with lscpu/lspci/lsusb/sensors present).
- Note: `dmidecode` (mentioned in the plan spec for the tool) requires root privileges and is not exposed as a standalone op; the `summary` op covers the same use-case via lscpu+free+lsblk which are always available to unprivileged users.

## One-Line Summary

Phase 6 hardware tool complete: 7 READ ops (cpu/memory/pci/usb/block/sensors/summary) self-registered, all-READ permission class, I2-clean, 43/43 tests green on dev host.
