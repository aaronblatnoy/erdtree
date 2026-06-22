# Phase 6 — processes tool audit evidence

**Date:** 2026-06-21
**Slice:** core/tools/processes.py (ps/top/kill/pkill/renice)
**Agent:** claude-sonnet-4-6

## Files touched

- `core/tools/processes.py` — CREATED
- `tests/test_tools_processes.py` — CREATED

## Conformance checklist

| Invariant | Status | Evidence |
|-----------|--------|----------|
| I1: No network calls; subprocess only via run_subprocess | PASS | Only `run_subprocess` called; no psutil/pyroute2/os.kill/shutil imports |
| I2: No AI/LLM/model/agent language in user-facing strings | PASS | TestI2Filter (5 test classes) all green; imports _FORBIDDEN_AI_TERMS from core.agent.prompt |
| I3: No permissions/audit calls inside the tool | PASS | No import of permissions or audit in processes.py |
| I4: Audit written by caller | PASS | _execute() returns ToolResult only; no audit.write() call |
| I6: No tier/product names in core/ | PASS | Zero tier names in the file |
| I9: Unknown op degrades to valid ToolResult | PASS | TestUnknownOp.test_unknown_op_returns_tool_result green |

## Op / permission map

| Op      | Permission  | Synthesized command                     | Gate (interactive) |
|---------|-------------|-----------------------------------------|--------------------|
| list    | READ        | `ps aux`                                | ALLOW              |
| tree    | READ        | `ps -ejH`                               | ALLOW              |
| top     | READ        | `ps aux --sort=-%cpu`                   | ALLOW              |
| info    | READ        | `ps -p <pid> -o pid,ppid,...`           | ALLOW              |
| signal  | WRITE       | `kill <pid>` / `kill -<n> <pid>`        | CONFIRM            |
| signal  | WRITE→DESTR | `kill -1 <pid>` (signal_num=-1)         | CONFIRM_TYPED      |
| renice  | WRITE       | `renice <prio> -p <pid>`                | CONFIRM            |

## Classifier gate verification

Key: `kill -1 <pid>` synthesizes `["kill", "-1", "1234"]` in the subprocess vector.
The classifier's `_classify_argv` sees `"-1" in tokens` for verb `kill` and escalates
to DESTRUCTIVE → CONFIRM_TYPED. Non-interactive context → REFUSE.
Verified by `TestPermissionGateIntegration.test_signal_kill_minus1_classifies_destructive` and
`test_signal_kill_minus1_refused_non_interactive`.

## SELinux hint

`_maybe_selinux_hint` copied verbatim from services.py (canonical template).
Triggered when stderr contains AVC/dontaudit/Permission denied.
Verified by `TestSELinuxHint` (2 tests).

## Signal number encoding fix

When `signal_num < 0` (e.g. -1), the flag is `str(sig)` (already "-1") rather than
`f"-{sig}"` (which would give "--1"). This ensures the subprocess argv matches the
synthesized command string the classifier reasons over.

## Test run

```
python3 -m unittest tests.test_tools_processes -v
Ran 59 tests in 0.010s
OK
```

All 59 tests pass. Zero failures. Zero errors. I2 filter clean on all descriptions and summaries.
