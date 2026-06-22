# Phase 8 Episodic Memory — Audit Evidence

**Date:** 2026-06-21
**Phase:** P8 sibling — core/agent/episodic.py + tests/test_episodic.py

## Files Created

- `core/agent/episodic.py` — EpisodicMemory class
- `tests/test_episodic.py` — 15 stdlib unittest tests

## Files NOT Touched

- `core/agent/repl.py` — unchanged (consolidation step does this)
- `core/agent/main.py` — unchanged (consolidation step does this)
- `rag/retrieve.py` — imported as-is (SC-P7.3: reuse, not fork)

## Design

EpisodicMemory builds and refreshes a local vector index over the audit JSONL
that the REPL writes at `/var/log/{tier}/audit.jsonl`.  Key properties:

**Reuse-not-fork (SC-P7.3):** `rag.retrieve.retrieve()` is imported and called
with a caller-supplied `index_path` pointing at the episodic sqlite-vec database
(e.g. `/var/log/tier/episodic.db`).  This is provably different from the docs
corpus index path (`rag/fixtures/mini_index.db` in tests; `ERDTREE_CORPUS_INDEX`
in production).  Zero code duplication of retrieval logic.

**Incremental rebuild (REBUILD_DELTA_BYTES = 4096):** The index is rebuilt
whenever the audit log grows by more than `rebuild_delta` bytes since the last
build, giving cheap eventual consistency.  A just-written op is simultaneously
still in the verbatim recent-history window (A5).

**Corpus fields (A5):** Each audit JSONL record is rendered as:
  `request: {nl_input}  command: {translated_command}  tool: {tool}  exit: {exit_code}  result: {result}`
Plain operator language only — no I2-forbidden terms in any rendered text.

**I9 degradation:** All failure paths (missing audit log, index-build failure,
empty query, k<=0, max_chars<=0, backend unavailable) return `[]` and never
raise out to the caller.

**I2 compliance:** `_record_to_text()` output and all recalled Chunk.text values
are verified clean against `core/agent/prompt._AI_PATTERN` by the test suite.

## Test Run

Command: `/home/aaron/erdtree/.venv/bin/python3 -m unittest tests.test_episodic -v`

```
test_blank_query_returns_empty ... ok
test_empty_audit_log_returns_empty ... ok
test_empty_query_returns_empty ... ok
test_k_negative_returns_empty ... ok
test_k_zero_returns_empty ... ok
test_max_chars_zero_returns_empty ... ok
test_missing_audit_log_returns_empty ... ok
test_recalled_text_is_i2_clean ... ok
test_record_to_text_is_i2_clean ... ok
test_new_record_becomes_retrievable_after_rebuild ... ok
test_k_limits_results ... ok
test_matching_op_is_recalled ... ok
test_max_chars_respected ... ok
test_results_are_chunks ... ok
test_index_path_is_a_parameter_reuse_property ... ok

Ran 15 tests in 0.031s — OK
```

## Key Assertions Verified

1. `test_matching_op_is_recalled` — a query about "nginx restart" returns the
   nginx audit record as the top chunk.
2. `test_index_path_is_a_parameter_reuse_property` — the episodic index_path
   (`episodic.db` in a temp dir) differs from the docs fixture index path
   (`rag/fixtures/mini_index.db`), proving reuse-not-fork.
3. `test_new_record_becomes_retrievable_after_rebuild` — a record appended after
   the initial index build appears in results after the size delta triggers a
   rebuild.
4. All 7 degradation cases return `[]` without raising (I9).
5. I2 compliance verified against the canonical `_AI_PATTERN` filter.

## Invariants Satisfied

- **I1:** No network socket opened. `rag.retrieve` and `rag.index` use only
  local file I/O and the sqlite-vec extension.
- **I2:** All user-facing strings (chunk text, operator summaries) clear the
  `_AI_PATTERN` filter. Confirmed by test suite.
- **I6:** No tier/product names in `core/`. `audit_path` and `index_path` are
  caller-supplied parameters; defaults are constants, not tier names.
- **I9:** Every failure path degrades to `[]`, never raises to the caller.
- **SC-P7.3:** `rag.retrieve.retrieve()` is the single retrieval engine;
  EpisodicMemory supplies a different `index_path` — no second retriever built.
- **SC-P8.3:** A fact (audit record) established earlier is recalled via the
  reused engine when queried.

## Notes

- `sqlite_vec` must be installed in the Python environment (present in
  `/home/aaron/erdtree/.venv`; absent from system Python 3.14). Tests must
  run with `.venv/bin/python3`.
- The episodic index_path defaults to being beside the audit log; the caller
  (main.py consolidation step) supplies the actual paths from `AppConfig`.
