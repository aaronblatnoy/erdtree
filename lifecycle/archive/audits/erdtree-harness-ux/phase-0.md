# Phase 0 — Invariance Baseline Evidence

Generated: 2026-06-21
Plan: lifecycle/pending/plans/erdtree-harness-ux.txt §Phase 0

## What was done

Created `tests/test_invariance_baseline.py` — the FROZEN "before" oracle for
the streaming build.  Five canonical turns are driven through `Repl.run_turn()`
with the existing buffered `ScriptedResponder` + `FakeIO` doubles (defined in
the new file and importable by P6 to re-run against the streaming path without
modification).

The doubles in `test_invariance_baseline.py` are byte-identical to those in
`tests/test_repl.py` so P6 can `from tests.test_invariance_baseline import
ScriptedResponder, FakeIO, FakeContext, _stub_tool_results, _make_repl` and
re-run the five scenario-level helpers.

## Frozen baseline numbers

### Scenario 1 — READ (instant, no confirmation)

| Field | Value |
|-------|-------|
| audit_count | 1 |
| permission_decision | `"allow"` |
| tool_calls_made | 1 |
| refused | 0 |
| misses | 0 |
| rounds | 2 |
| ended_in_english | True |
| rendered (English answer) | `["sshd is running."]` |

### Scenario 2 — CONFIRMED WRITE

| Field | Value |
|-------|-------|
| audit_count | 1 |
| permission_decision | `"confirm"` |
| tool_calls_made | 1 |
| refused | 0 |
| misses | 0 |
| rounds | 2 |
| ended_in_english | True |
| rendered (English answer) | `["nginx restarted."]` |

### Scenario 3 — DECLINED WRITE

| Field | Value |
|-------|-------|
| audit_count | 1 |
| permission_decision | `"confirm:declined"` |
| exit_code | 2 |
| tool_calls_made | 0 |
| refused | 1 |
| misses | 0 |
| rounds | 2 |
| ended_in_english | True |
| rendered (English answer) | `["Okay, leaving nginx as is."]` |

### Scenario 4 — DESTRUCTIVE WRONG WORD

| Field | Value |
|-------|-------|
| audit_count | 1 |
| permission_decision | `"confirm_typed:declined"` |
| exit_code | 2 |
| tool_calls_made | 0 |
| refused | 1 |
| misses | 0 |
| rounds | 2 |
| ended_in_english | True |
| rendered (English answer) | `["Not removing the kernel."]` |

### Scenario 5 — MISS + RE-ASK

| Field | Value |
|-------|-------|
| audit_count | 2 |
| permission_decisions | `["n/a", "allow"]` |
| records[0].result starts_with | `"miss:"` |
| tool_calls_made | 1 |
| refused | 0 |
| misses | 1 |
| rounds | 3 |
| ended_in_english | True |
| rendered (English answer) | `["sshd is running."]` |

## Test run

Command: `.venv/bin/python -m pytest tests/test_invariance_baseline.py -q`

```
5 passed in 0.06s
```

Full suite with new file: `.venv/bin/python -m pytest -q`

```
1819 passed, 14 skipped, 371 subtests passed in 5.16s
```

(The 2 pre-existing failures in `tests/test_router.py` that appeared in an
intermediate run were from uncommitted working-tree changes to `router.py` and
`tests/test_router.py` that predate this phase; they are NOT caused by
`test_invariance_baseline.py` — confirmed by running the suite without the new
file and seeing only passes.)

## Deferred

DEFERRED-TO-MOSSAD: live 7B/14B Ollama round-trip FEEL (SC1/SC6) — needs a
provisioned box with Ollama running a real model; not available on this dev
host.  All five baseline tests are unit-provable here with scripted/chunked-
responder doubles; no live round-trip was claimed or fabricated.
