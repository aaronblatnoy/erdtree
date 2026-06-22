# Phase 3 — Live Tool-Call Display ("running: <cmd>" + status line)

Slice scope (SINGLE-WRITER on repl.py, serialized after P2): touched ONLY
`core/agent/repl.py` and `tests/test_tool_step_display.py`.

## What changed (core/agent/repl.py)

1. `ConsoleIO` gained `tool_step` / `tool_step_result` (the P2 hooks now exist
   on ReplIO + ConsoleIO; ConsoleIO renders them as dim inline lines, I2-clean).
2. New PRESENTATION-ONLY helpers on `Repl`:
   - `_emit_tool_step(text)` / `_emit_tool_step_result(text)` — `getattr`-guarded
     so an IO without the optional hook degrades to a no-op (BACK-COMPAT), and
     wrapped so a display fault never breaks a turn.
   - `_step_status(result)` — terse, I2-clean status from `ToolResult.exit_code`
     (None -> "not run", 0 -> "done", else "exit <code>").
3. In `_dispatch_calls`:
   - Refused/declined op -> `tool_step_result("not run")`. NO "running:" line
     (I3 honesty — never imply an unconfirmed write ran).
   - Gate cleared -> `tool_step("running: " + synthesize_command(call))` AFTER
     `_resolve_gate` returns cleared==True and BEFORE `_safe_dispatch`.
   - After dispatch + the existing audit.write -> `tool_step_result(status)`.

## SC4 — gate/audit/dead-man BYTE-BEHAVIOR-UNCHANGED

No `audit.write` call was added, moved, or removed. No change to
`permissions.classify`, the gate ordering, or `_resolve_gate`. Display is purely
additive presentation. `shell/shell.py` untouched. No new socket/host (I1 — no
network touched at all in this slice).

## Tests run (real output)

```
$ .venv/bin/python -m pytest tests/test_tool_step_display.py -q
........                                                                 [100%]
8 passed in 0.06s

$ .venv/bin/python -m pytest tests/test_invariance_baseline.py -q
.....                                                                    [100%]
5 passed in 0.03s
```

Regression sweep (adjacent suites + full suite):

```
$ .venv/bin/python -m pytest tests/test_repl.py tests/test_router.py tests/test_deadman.py tests/test_main.py -q
55 passed

$ .venv/bin/python -m pytest -q
1842 passed, 14 skipped, 371 subtests passed in 5.24s
```

## Validation mapping

- SC2: `test_confirmed_write_shows_running_then_result` — confirmed write emits
  `tool_step("running: systemctl restart nginx.service")` BEFORE and a
  `tool_step_result` AFTER, ordering asserted, command == synthesize_command (a
  NON-trivial argv, not a default-deny floor). `test_read_op_also_shows_running_line`
  covers the plan's `systemctl status nginx.service` example.
- Declined: `test_declined_write_no_running_only_not_run` +
  `test_non_interactive_refused_write_no_running` — NO "running:" line, a
  "not run" status line.
- SC3/I2: `test_all_step_strings_are_i2_clean` — every captured tool_step /
  tool_step_result string passes `prompt._AI_PATTERN` AND `_assert_no_ai_language`.
- SC4 audit-count parity: `test_display_adds_zero_audit_records_confirmed` /
  `..._declined` — display emits lines but adds ZERO audit records (count == 1
  for one op, matching baseline). `test_io_without_step_hooks_still_works`
  pins BACK-COMPAT for hook-less IOs.

## New user-facing strings introduced (for the P6 I2 inventory)

- `"running: " + <synthesize_command(call)>` (e.g. `running: systemctl restart nginx.service`)
- `"not run"` (refused/declined op status)
- `"done"` (exit_code == 0)
- `"exit <code>"` (non-zero exit, e.g. `exit 1`)

## Deferred

- LIVE 7B/14B Ollama round-trip FEEL -> DEFERRED-TO-MOSSAD (needs a provisioned
  box + Ollama running a real model; unit-proven here with scripted doubles).
