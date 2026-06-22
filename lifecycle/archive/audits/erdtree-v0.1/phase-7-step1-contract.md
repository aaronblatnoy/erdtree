# Phase 7 — Step 1 evidence: the index/engine CONTRACT

Date: 2026-06-21 · Host: Linux (Arch), Python 3.14.6, sqlite 3.53.2 · CPU-only, no GPU

## Outcome

- **Backend chosen by measurement: `sqlite-vec` 0.1.9.** faiss (the documented
  fallback) is NOT used — sqlite-vec passed the fixture footprint/latency budget.
  `escalate = false` (neither backend blew the budget; only one was needed).
- **Frozen signature:** `rag.retrieve(query, index_path, k, max_chars) -> list[Chunk]`
  with `index_path` a parameter (SC-P7.3 reuse by P8 episodic). `Chunk` =
  `{chunk_id, source, license, text, score}`.
- **Reranker:** lean lexical+score blend, NO second large model (I8).
- Decision doc written: `docs/decisions/0003-vector-index.md`.

## Files touched (only these, per the brief)

- `rag/__init__.py` — lazy re-export of the frozen `retrieve` / `Chunk`.
- `rag/embed.py` — offline CPU embedder: stdlib hashed (fixtures/tests) +
  pinned sentence-transformer (prod, mossad-only). No socket.
- `rag/index.py` — sqlite-vec build + query; the authoritative on-disk format.
- `rag/retrieve.py` — the frozen reusable engine (embed→KNN→lexical rerank→trim).
- `rag/requirements.txt` — pinned `sqlite-vec==0.1.9` + prod embedder
  (`sentence-transformers==3.0.1`, `torch==2.3.1`); core agent imports none.
- `rag/fixtures/corpus.jsonl` — 12 operator-doc chunks (mount/firewalld/systemd/
  dnf/lvm/selinux/journalctl/mkfs/ssh), each with a per-source license label.
- `rag/fixtures/build_fixture_index.py` — offline builder → `mini_index.db`.
- `rag/fixtures/mini_index.db` — prebuilt mini-index for offline tests.
- `tests/test_rag_retrieve.py` — the Step-1 contract gate (9 tests).
- `docs/decisions/0003-vector-index.md` — the decision record.

Did NOT touch `repl.py` or `main.py` (per brief).

## sqlite-vec verified loadable (I1 backend check)

```
sqlite-vec OK, vec_version = v0.1.9
vec0.so = 159816 bytes (156.1 KiB)
```

## Measured footprint (fixture + synthetic sizes; dim 256, float32)

| n chunks | on-disk |
|---------:|--------:|
| 12 (fixture) | 1.05 MiB (fixed vec0 page reservation) |
| 1 000 | 1.14 MiB |
| 5 000 | 5.57 MiB |

Linear fit: fixed ≈ 40 KiB, **marginal ≈ 1 159 B/chunk**.
Extrapolated: 1 M chunks ≈ **1.16 GB**, 3 M ≈ **3.48 GB** SSD — inside the
~3–5 GB budget. (Naive per-chunk extrapolation off the 12-chunk fixture
overstates by ~80× because the fixture is dominated by the one-time shadow-page
reservation, not per-vector cost.)

## Measured RAM + latency at query (fixture, warm)

- process RSS ≈ **22 MiB**; Python peak alloc/query ≈ 21 KiB (≪ 1–2 GB budget).
- end-to-end `retrieve()` ≈ **0.63 ms/query** (mean of 200).
- KNN-only (persistent conn, overfetch 15) ≈ **0.215 ms/query**.

Real-corpus latency on 8 GB cards is DEFERRED-TO-MOSSAD (D3).

## Test run (offline, no socket, no GPU)

```
$ python3 -m unittest tests.test_rag_retrieve -v
Ran 9 tests in 0.013s
OK
```

Covers: signature returns Chunks; factual query top-ranks the right chunk;
max_chars budget respected; unrelated query lower score; missing index → [] (I9);
bad args → [] (I9); **index_path is a real parameter — a second index searchable
(SC-P7.3)**; **fixture build opens no socket (I1)**; **summary + every chunk text
clear the canonical I2 filter** (`core.agent.prompt._AI_PATTERN`).

Existing suites unaffected: `python3 -m unittest tests.test_dispatch
tests.test_deadman` → 27 tests OK.

## Invariants honored

- I1 — offline build, no socket (test-asserted); backend is a local file.
- I2 — sanctioned docs summary "Retrieved N reference passages." + all chunk
  text clear `_AI_PATTERN`; AI/index jargon confined to source comments.
- I6 — engine reads no tier name; budgets (k/max_chars) are caller params.
- I9 — every failure path (missing index, absent backend, bad args) → empty
  `list[Chunk]`, never an exception out to the loop.
