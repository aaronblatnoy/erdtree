# Phase 6 Tool Audit: core/tools/files.py

**Date:** 2026-06-21
**Slice:** files.py (ls/stat/cat/find/cp/mv/rm/mkdir/chmod/chown/tee)
**Status:** COMPLETE — all tests green

## Files Touched

- `core/tools/files.py` — created
- `tests/test_tools_files.py` — created

## Test Run

```
python3 -m unittest tests.test_tools_files
......................................................................
Ran 70 tests in 0.014s
OK
```

## Invariant Compliance

| Invariant | Status | Notes |
|-----------|--------|-------|
| I1 | PASS | All ops shell out via `run_subprocess` only; no psutil/shutil/os.* mutation |
| I2 | PASS | All descriptions and summaries pass `_FORBIDDEN_AI_TERMS` filter (asserted in 22 test cases) |
| I3 | PASS | No `permissions.classify()` or `audit.AuditLog` calls inside the tool; gate is caller's responsibility |
| I4 | PASS | No audit code inside the tool; caller writes the record |
| I6 | PASS | Zero tier/product/model names in the file |
| I9 | PASS | Unknown ops return a ToolResult (exit_code=1); no exceptions escape |

## Op/Permission Map Implemented

| Op     | Permission Class | Binary | Notes |
|--------|-----------------|--------|-------|
| list   | READ            | ls     | `ls -lah <path>` |
| read   | READ            | cat    | line-capped (default 200, max 1000) |
| stat   | READ            | stat   | `stat <path>` |
| find   | READ            | find   | supports name/type/maxdepth args |
| copy   | WRITE           | cp     | supports recursive flag |
| move   | WRITE           | mv     | `mv <src> <dst>` |
| mkdir  | WRITE           | mkdir  | `-p` by default |
| chmod  | WRITE           | chmod  | supports recursive flag |
| chown  | WRITE           | chown  | supports recursive flag |
| write  | WRITE           | tee    | content passed via stdin |
| remove | WRITE (declared)| rm    | synthesize_command in repl.py emits `rm -rf <path>` when recursive+force; classifier escalates to DESTRUCTIVE |

## Destructive Gate Verification

The classifier correctly escalates `rm -rf` via the existing `permissions.classify()` logic:

- `rm -rf /tmp/scratch` → DESTRUCTIVE → CONFIRM_TYPED (interactive)
- `rm -rf /etc/mydir` → DESTRUCTIVE → CONFIRM_TYPED (interactive)
- `rm -rf /tmp/scratch` → DESTRUCTIVE → REFUSE (non-interactive)
- `rm /tmp/foo.txt` (plain) → WRITE → CONFIRM

These are asserted in `TestRemoveDestructiveGate` (4 test cases).

## SELinux Hint

`_maybe_selinux_hint()` copied from `services.py` (canonical template). Surfaces hint on AVC/Permission-denied patterns in stderr. Verified for copy and chmod ops.

## Self-Registration

`registry.register(FILES_SPEC)` at module import time. Verified by `TestRegistration` (3 test cases). `registry.get("files")` is not None after import.

## Summary

Phase 6 files.py slice: COMPLETE. 70 tests, all green, on `python3 -m unittest tests.test_tools_files`. I2 filter clean across all descriptions and summaries. No real processes launched (run_subprocess patched throughout).
