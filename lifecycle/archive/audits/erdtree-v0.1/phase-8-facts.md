# Phase 8 — Facts Preamble Audit Evidence

**Date:** 2026-06-21
**Scope:** core/context/facts.py + core/agent/context.py minimal thread + tests/test_facts.py

## Deliverables

### core/context/facts.py (CREATED)
- `FactsLoader(path)` class: loads operator-curated text from ERDTREE_FACTS_PATH-supplied path.
- `load()` returns `""` when path is None/empty, file absent, file empty, whitespace-only, or any IOError (I9 — never raises).
- `load_facts(path)` convenience function.
- No network calls (I1). No tier/product names (I6). No user-visible strings generated (I2).

### core/agent/context.py (MODIFIED — minimal additive thread)
- Added `from core.context.facts import FactsLoader` import.
- `TurnContext.__init__` accepts optional `facts: Optional[FactsLoader] = None` kwarg.
- `TurnContext.snapshot_text()` optionally prepends preamble when `facts` is supplied and `facts.load()` is non-empty.
- **Backward-compatible default:** `facts=None` → output byte-identical to pre-P8 path (no preamble, no code-path change). All existing tests pass unchanged.

### tests/test_facts.py (CREATED — stdlib unittest, 22 tests)
- `TestFactsLoaderNoPath` — None/empty path returns `""`.
- `TestFactsLoaderAbsentFile` — absent file returns `""`, does not raise (I9).
- `TestFactsLoaderPresentFile` — present file returns text; empty/whitespace returns `""`; text is stripped; load_facts() convenience works; I2 filter passes on clean text (imported from core.agent.prompt._FORBIDDEN_AI_TERMS, not re-listed).
- `TestFactsLoaderI2Filter` — confirms filter is imported from canonical source; dirty text rejected; clean operator text passes.
- `TestTurnContextFactsPrepend` — preamble prepended when present; output unchanged when absent/empty; augments not replaces snapshot (I5); I2-clean preamble passes filter; snapshot collection failure still prepends preamble (I9).

## Test Results

```
python3 -m unittest tests.test_facts -v
Ran 22 tests in 0.041s
OK  (22 passed)

/home/aaron/erdtree/.venv/bin/python -m pytest tests/test_snapshot.py -v
48 passed, 2 skipped (DEFERRED-TO-MOSSAD)
```

## Invariant Compliance

| Invariant | Compliance |
|-----------|------------|
| I1 (no network) | facts.py reads only local filesystem; no socket opened |
| I2 (no AI language) | No user-facing strings generated; I2 filter imported + tested |
| I5 (context always injected) | Preamble augments snapshot, never replaces; fallback path still returns snapshot |
| I6 (no tier names) | Path supplied by caller (AppConfig/ERDTREE_FACTS_PATH); module is name-free |
| I9 (no exception escape) | load() never raises; absent/unreadable file → empty string |

## Files Touched

- `core/context/facts.py` (CREATED)
- `core/agent/context.py` (MODIFIED — additive only; 3 hunks: import, __init__ kwarg, snapshot_text prepend)
- `tests/test_facts.py` (CREATED)
- `lifecycle/archive/audits/erdtree-v0.1/phase-8-facts.md` (this file)
