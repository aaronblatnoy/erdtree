# Phase 7(b) — Retrieve Engine + Docs Tool: Audit Evidence

**Date:** 2026-06-21  
**Executor:** claude-sonnet-4-6  
**Scope:** P7 sibling (b) — rag/retrieve.py (already present from Step 1) + core/tools/docs.py + tests

---

## What Was Already Built (P7 Step 1 / sibling a)

The following existed and were verified passing before this session:
- `rag/retrieve.py` — frozen engine with signature `retrieve(query, index_path, k, max_chars) -> list[Chunk]`
- `rag/embed.py` — hashed (stdlib) + sentence-transformer (mossad-deferred) backends
- `rag/index.py` — sqlite-vec backend, frozen ON-DISK format
- `rag/__init__.py` — lazy re-export
- `rag/fixtures/corpus.jsonl` — 12-chunk test corpus
- `rag/fixtures/mini_index.db` — pre-built fixture index
- `rag/fixtures/build_fixture_index.py` — fixture build script
- `tests/test_rag_retrieve.py` — 9 tests covering the frozen contract

## What This Session Built

**Files touched (ONLY these — per brief constraint):**
- `core/tools/docs.py` (CREATED) — the "docs" tool
- `tests/test_tools_docs.py` (CREATED) — 21 tests

## Design Decisions

### docs.py shape
Mirrors `core/tools/services.py` exactly:
- Per-op function (`_op_retrieve`) returning `ToolResult`
- `_DISPATCH` table
- `ToolSpec` with per-op `permission_class=OpClass.READ`
- Self-registration via `registry.register(DOCS_SPEC)`

Does NOT call `run_subprocess` (retrieval is pure Python against a local sqlite file — no subprocess needed). The classifier sees a read-shaped command string from `synthesize_command()` in repl.py (P6.8 pass — not touched here per brief).

### Degradation (I9)
Four failure modes all return `ToolResult(exit_code=0, stdout="", stderr="", summary="Retrieved 0 reference passages.")`:
1. `ERDTREE_CORPUS_INDEX` unset or empty
2. rag backend (`sqlite_vec`) not importable
3. `rag.retrieve` raises at runtime
4. `rag.retrieve` returns `[]` (missing index file)

### I2 compliance
- Summary: `"Retrieved N reference passages."` — no AI/LLM/model/retrieval/embedding/inference language
- Tool description and op descriptions: scanned by `_AI_PATTERN` from `core.agent.prompt` in tests; all clean
- Each forbidden term individually asserted against `_FORBIDDEN_AI_TERMS`

### I6 compliance
- No tier names anywhere
- `k` default reads from `ERDTREE_RETRIEVAL_K` env var; `max_chars` from `ERDTREE_RETRIEVAL_MAXCHARS`
- Index path from `ERDTREE_CORPUS_INDEX`

### SC-P7.3 (index_path as parameter)
- `test_retrieve_called_with_index_path` asserts that `_execute` passes `_INDEX_PATH` through to `_retrieve_fn` as a positional parameter — the same engine with a different path is the reuse property P8 episodic depends on

## Test Results

**Command:** `/tmp/erdtree-venv/bin/python3 -m unittest tests.test_rag_retrieve tests.test_tools_docs`  
**Result:** 30 passed, 0 failed, 0 errors

```
tests.test_rag_retrieve: 9 tests — OK
tests.test_tools_docs: 21 tests — OK
Total: 30/30 PASS
```

Backend requirement: `sqlite-vec==0.1.9` installed in `/tmp/erdtree-venv` (not available system-wide on this Arch Linux host; the tool itself degrades cleanly when absent per I9).

## Invariant Checklist

| Invariant | Status |
|-----------|--------|
| I1 — No network | PASS: no socket opened; `NoSocket` test asserts |
| I2 — No AI language | PASS: `_AI_PATTERN` + `_FORBIDDEN_AI_TERMS` asserted in 5 tests |
| I3 — Gate before write | N/A: op is READ; `Gate.ALLOW` asserted in `test_docs_retrieve_classifies_as_allow` |
| I4 — Audit by REPL | PASS: tool has no audit code; REPL handles it |
| I6 — No tier names | PASS: zero tier/product names in docs.py |
| I9 — No crash on failure | PASS: 4 degradation tests; all return empty-but-valid |

## Deferred Items

- D1: `synthesize_command()` docs branch in `repl.py` — folded into P6.8 pass (single-writer constraint; not touched here per brief)
- D2: Full corpus embed — DEFERRED-TO-MOSSAD (GPU); recipe ships; fixture index tested offline
