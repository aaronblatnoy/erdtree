# Phase 8 Consolidation (P8.c) — evidence

Date: 2026-06-21
Scope: surgical repl.py memory edit + main.py wiring + amnesia integration gate.
Single-writer of repl.py this pass; P6.8's synthesize_command preserved untouched.

## Files touched (ONLY these three)
- `core/agent/repl.py`   — optional ctor params (`memory`, `episodic`,
  `compaction_threshold`); `run_turn` history arg now from
  `memory.compacted_history(threshold)` (was hardcoded `history=[]`); new
  private `_record_turn()` folds each completed turn into TranscriptMemory.
  synthesize_command + the gate/dispatch/audit path are BYTE-UNTOUCHED.
- `core/agent/main.py`   — `AppConfig` gains 4 opaque knobs
  (`ERDTREE_FACTS_PATH`, `ERDTREE_CORPUS_INDEX`, `ERDTREE_RETRIEVAL_K`,
  `ERDTREE_COMPACTION_THRESHOLD`, read like ERDTREE_MODEL); `build_repl`
  constructs TurnContext(facts), TranscriptMemory, EpisodicMemory and passes
  them into Repl. `_int_env` helper. P6.8 tool/docs imports preserved.
- `tests/test_compaction.py` — NEW integration keystone (SC-P8.1..SC-P8.4).

## Backward compatibility (I9)
- `memory=None` -> `history=[]` EXACTLY (today's behavior). Verified by
  `TestBackwardCompatibleDefault` and the full pre-P6 suite staying green.
- Every P8 piece in `build_repl` degrades OFF on absence/error (facts file
  absent -> empty preamble; corpus index absent -> docs/episodic off;
  malformed int knob -> default). `build_repl` never crashes.
- Episodic recall is NOT auto-injected: stored on the Repl, the loop PREFERS
  routing recall through the docs-tool engine (the "loop decides" property).

## Invariants threaded
- I2: amnesia gate reuses `core/agent/prompt._FORBIDDEN_AI_TERMS` (imported,
  not re-listed) PLUS a dedicated amnesia-phrase blocklist
  (context/limit/reset/forgot/earlier session/no longer have/...).
- I3/I4: gate + audit path in repl.py untouched — the classifier still fires
  off the synthesized command string.
- I6: all new knobs read opaquely; no tier/product names.
- I9: `_record_turn` failure is swallowed; no new exception escapes run_turn.

## test_compaction (the keystone) — SC-P8.1..SC-P8.4
- (a) over-window 55-task session: eviction fires (window bounded by budget,
  svc0 evicted), and every operator-facing line passes the I2 + amnesia filter.
- (b) a billing-service op established at task 1, buried by 52 tasks, is GONE
  from the compacted window yet recalled via EpisodicMemory (reused rag engine
  over the audit log the loop wrote; episodic index_path != docs corpus index).
- (c) "restart it" after 41 tasks: the recent unit (redis-cache.service)
  survives VERBATIM in the assembled history so the deictic referent resolves.

## Test commands + tally
- New test (mandated style): `python3 -m unittest tests.test_compaction`
  -> Ran 4 tests ... OK.
- Full regression: `python3 -m unittest discover -s tests`
  -> Ran 476 tests ... OK (skipped=3).  (Baseline was 472; +4 = new keystone.)
  Run inside .venv (pytest installed there so the existing fixture-based tests
  resolve; absent pytest the fixtures error under bare unittest — environmental,
  not a logic regression).
- Cross-check under pytest (core suites + compaction):
  `python3 -m pytest tests/test_repl.py tests/test_main.py tests/test_router.py
  tests/test_memory.py tests/test_episodic.py tests/test_facts.py
  tests/test_permissions.py tests/test_audit.py tests/test_dispatch.py
  tests/test_deadman.py tests/test_snapshot.py tests/test_compaction.py`
  -> 1047 passed, 2 skipped, 7 subtests passed.

PASS: test_compaction green AND full suite green (no regression) AND amnesia
blocklist clean.
