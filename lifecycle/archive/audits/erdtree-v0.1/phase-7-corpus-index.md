# Phase 7 sibling (a) — Corpus + Index Build evidence

Date: 2026-06-21 · Host: Linux (Arch), Python 3.14.6, sqlite 3.53.2 · CPU-only, no GPU

## Outcome

- `rag/build_corpus.py` — corpus assembly recipe implemented: man pages (groff
  render), Rocky/RHEL docs, Arch wiki (recipe-only), Stack Overflow (recipe-only),
  CVE summaries.  Chunker + `_clean_man_text` + `_stable_id` helpers.  Full
  corpus embed **DEFERRED-TO-MOSSAD** (D2 in plan §13).
- `rag/LICENSES.md` — per-source redistribution verdict written.  Default
  posture: **ship the firstboot BUILD RECIPE, not the raw corpus** (Arch wiki
  CC-BY-SA-3.0 and SO CC-BY-SA-4.0 require special handling).
- `rag/embed.py`, `rag/index.py` — unchanged (completed in P7 Step 1).
- `tests/test_rag_index.py` — 21 offline tests: chunker helpers, man-page
  iterator (no socket), smoke-test build_corpus, full index build-and-query
  round-trip, fixture corpus/index consistency, I2 filter, license manifest
  constants.

## Bug found and fixed during implementation

`iter_man_chunks` called `_section_from_path(section_dir)` which reads
`path.parent.name` — designed for a FILE path (parent == the section dir).
When passed the section dir itself, it returned `"man"` instead of `"1"`/`"5"`/
`"8"`, causing all section dirs to be silently skipped and yielding 0 chunks.
Fix: inline `re.match(r"man(\d+)$", section_dir.name)` in the iterator.

## Files touched (only these, per the brief)

- `rag/build_corpus.py` — new (corpus recipe + chunker + per-source iterators)
- `rag/LICENSES.md` — new (per-source redistribution verdict)
- `tests/test_rag_index.py` — new (21 offline tests)

Did NOT edit: `rag/retrieve.py`, `rag/embed.py`, `rag/index.py`, `rag/__init__.py`,
`rag/fixtures/*`, `repl.py`, `main.py`.

## Test run (offline, no socket, no GPU)

```
$ /home/aaron/erdtree/.venv/bin/python3 -m unittest tests.test_rag_index -v
Ran 21 tests in 0.800s
OK
```

Covers:
- `TestChunkerHelpers` (5): `_chunk_text` basic/empty/short; `_clean_man_text`
  strips ANSI escapes and backspace overstrikes.
- `TestIterManChunks` (5): yields RawChunks from real `/usr/share/man` with no
  socket; chunk length bounds; I2 forbidden-term filter on every chunk text;
  license field populated; skips nonexistent dir gracefully.
- `TestBuildCorpusSmoke` (2): full `build_corpus()` with `max_man_pages=5` opens
  no socket; emits valid JSONL with required fields.
- `TestIndexBuildAndQuery` (5): build fresh sqlite-vec index from real man chunks
  with no socket; round-trip query returns `Chunk` objects; missing index
  degrades to `[]` (I9); fixture corpus.jsonl loads with required fields; fixture
  mini_index.db opens, reads meta, answers KNN (top hit = `man-mount-noexec`);
  build of fixture-equivalent index opens no socket, queries correctly.
- `TestSourceLicenses` (3): manifest constants consistent; recipe-only set is a
  subset; arch + so in recipe-only set.

Combined with P7 Step 1 (test_rag_retrieve 9 tests): `Ran 30 tests in 0.774s OK`.

## Invariants honored

- **I1** — no socket opened during build, embed, or index (test-asserted with
  `NoSocket` shim in three separate tests).
- **I2** — `iter_man_chunks` I2 test asserts every chunk text clears
  `core.agent.prompt._AI_PATTERN`; no AI/LLM/model language in any user-facing
  string in `build_corpus.py` or `LICENSES.md`.
- **I6** — no tier/product names in any new code; `k`/`max_chars` are caller
  parameters, not hardcoded constants.
- **I9** — `retrieve()` on a missing or unbuilt index returns `[]`, never raises.

## Deferred items

- **D2 (DEFERRED-TO-MOSSAD):** Full corpus embed requires mossad GPU + source
  corpora (Arch wiki dump + SO export + full man/RHEL/CVE trees).  The recipe
  (`rag/build_corpus.py`), license manifest (`rag/LICENSES.md`), engine
  (`rag/index.py` + `rag/embed.py` + `rag/retrieve.py`), and fixture mini-index
  (`rag/fixtures/mini_index.db`) all ship now and are fully tested offline.
  The firstboot recipe in `rag/LICENSES.md` describes the mossad embed command.
