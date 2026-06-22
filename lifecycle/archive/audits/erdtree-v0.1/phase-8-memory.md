# Phase 8 (sibling) — TranscriptMemory (invisible memory core)

Scope: `core/agent/memory.py` + `tests/test_memory.py` ONLY. No edit to repl.py
(the P8.c consolidation threads this in).

## What was built

`core/agent/memory.py` — `TranscriptMemory`, the rolling-compaction window the
Repl loop currently hardcodes as `history=[]` (repl.py ~line 237).

- `record(assistant_msg, tool_result_msgs)` — accumulate one completed turn
  (assistant message + its `role:"tool"` result messages). A plain English turn
  records with empty `tool_results`.
- `compacted_history(threshold)` — the compaction policy:
  - **Recent K turns kept VERBATIM** (byte-identical message objects) so deixis
    ("restart it" / "the one we just did") resolves. `keep_recent` default 2.
  - **Older turns keep tool-call OUTCOMES** — `{exit_code, summary}`, the exact
    shape `Router.tool_result_message` produces (router.py ~line 466) — and
    **DROP** the verbose `stdout_summary` / `stderr_summary` once reasoned over.
  - If still over `threshold`, oldest **compacted** turns are evicted whole,
    oldest-first; the recent verbatim window is NEVER evicted (deixis survives).
  - `threshold <= 0` => no eviction cap (compaction policy still applies). Safe
    degrade (I9).
- `Turn` dataclass + `size()` diagnostic helper.

## Invariants threaded

- **I6** — `threshold` is an OPAQUE per-tier char budget; `keep_recent` is a
  plain int. No tier/product name (marika/radagon/...) anywhere in the file.
- **I8** — PURE STDLIB accounting (`json` byte-length only). No model/network
  call. Verified: tests launch nothing, patch nothing.
- **I2** — The module emits NO user-facing strings (returns dicts/ints; one
  stdlib `ValueError`). The only forbidden-term hits ("model", "AI") live in
  docstrings/comments, never in a runtime string literal that reaches a user.
  Verified by AST scan of string `Constant` nodes: zero forbidden terms in any
  non-docstring string literal.
- **I9** — Never raises on malformed input: a `role:"tool"` message whose
  content isn't the expected JSON object is passed through unchanged.

## Tests (`tests/test_memory.py`, stdlib unittest)

The three required assertions, driven by synthetic turns built through the REAL
`Router.tool_result_message` shaper (each with ~4 KiB of stdout so the raw
history blows the budget):

- (a) `test_a_recent_turns_byte_identical` — recent K turns byte-identical to
  pristine recorded inputs (dict equality AND sorted-key JSON equality).
- (b) `test_b_older_turns_keep_outcome_drop_stdout` — older tool results retain
  `exit_code` + `summary`, drop `stdout_summary`/`stderr_summary`, and the giant
  stdout bytes are absent from the wire content.
- (c) `test_c_total_size_under_budget` — compacted serialized size <= threshold,
  while the raw history size > threshold (proves compaction did real work).

Plus edge cases: recent window survives a sub-window budget; empty history;
`threshold<=0` no-cap; plain-English turn; record/compact does not mutate
inputs; negative `keep_recent` rejected; turn flatten order.

## Run command + tally

```
python3 -m unittest tests.test_memory
```

Result: **Ran 10 tests — OK (0 failures, 0 errors).**

Note: `tests/test_repl.py` / `test_router.py` fail to import on this host
(`ModuleNotFoundError: pytest`) — a PRE-EXISTING condition unrelated to this
phase (pytest not installed; those files belong to other phases). memory.py
imports cleanly and runs under stdlib unittest with no third-party dep.

## Files touched
- `core/agent/memory.py` (new)
- `tests/test_memory.py` (new)
