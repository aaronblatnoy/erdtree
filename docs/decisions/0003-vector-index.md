# 0003 — Local Vector Index Backend (FROZEN CONTRACT)

- Status: ACCEPTED — **FROZEN**
- Date: 2026-06-21
- Phase: 7, Step 1 (the index/engine contract)
- Read by: `core/tools/docs.py` (P7), `core/agent/episodic.py` (P8 — reuses the
  SAME engine with a different `index_path`)
- Gates: plan §10 Q1 (sqlite-vec vs faiss), Q2 (reranker), §5 (the reusable
  `rag.retrieve` signature)
- Scope: framework-level, local-only, single-machine. No network at runtime
  (I1). No AI/LLM/model language in any user-facing string (I2).

## Decision

**Backend: `sqlite-vec`** (single-file, server-less). faiss is the documented
fallback and is **not used** — sqlite-vec passed the measured fixture
footprint/latency budget comfortably (numbers below), and it is the strongly
preferred option because it is reusable by P8 episodic memory with zero new
code (just a second `index_path`).

Why sqlite-vec over faiss:

- **One file.** The entire index — vectors **and** the passage text/metadata —
  lives in a single `.db`. Trivial to drop into an ISO; trivial to point P8
  episodic at a *second* `.db` (the audit-log index) with no new code. faiss
  stores only vectors + an integer id, forcing a parallel id→text doc store you
  must keep in sync — exactly the drift the P8 reuse requirement would suffer.
- **Server-less.** No daemon, no C++ build on the target box, no
  mmap-of-multiple-sidecar-files. The loadable extension is a ~156 KiB
  `vec0.so`. Verified loadable on this Linux build host (Arch, Python 3.14,
  sqlite 3.53.2) via `conn.enable_load_extension(True); sqlite_vec.load(conn)`.
- **ISO-friendly + reusable.** Both the SC-P7.1 corpus index and the SC-P8.3
  episodic index are the same on-disk format and the same query path.

## Measured footprint + latency (fixture, this Linux host, CPU-only, no GPU)

Measured with the pure-stdlib hashed embedder (`rag/embed.py`, `dim=256`,
float32 → 1024 raw bytes/vector) over the 12-chunk fixture and over synthetic
indexes at 100 / 1 000 / 5 000 chunks to separate fixed overhead from the
marginal per-chunk slope.

| Index size | On-disk | Per-chunk (incl. text+overhead) |
|-----------:|--------:|--------------------------------:|
| 12 (fixture) | 1.05 MiB | (dominated by fixed overhead) |
| 100 | 1.06 MiB | — |
| 1 000 | 1.14 MiB | ~1 200 B |
| 5 000 | 5.57 MiB | ~1 167 B |

Linear fit: **fixed overhead ≈ 40 KiB**, **marginal ≈ 1 159 bytes/chunk**
(≈ the 1 024-byte float32 vector + small text/metadata). The ~1 MiB seen on the
tiny fixture is a one-time `vec0` shadow-table page reservation, **not** a
per-vector cost — extrapolating the fixture's bytes/chunk naively is wrong.

Extrapolated to a realistic corpus (dim 256):

- 1 000 000 chunks ≈ **1.16 GB** SSD
- 3 000 000 chunks ≈ **3.48 GB** SSD

Both inside the plan's **~3–5 GB SSD** budget. A production ~384-d embedder
scales the vector portion ~1.5×, still inside budget at the 1–2 M-chunk scale.

**RAM at query:** process RSS ≈ **22 MiB**; Python-side peak alloc during a
query ≈ 21 KiB. Far under the **~1–2 GB** budget (sqlite-vec mmaps the file and
does not load the whole index into RAM).

**Query latency (fixture, warm):**

- End-to-end `retrieve()` (open + embed query + KNN + rerank + trim):
  **~0.63 ms/query** (mean of 200).
- KNN-only on a persistent connection (overfetch 15): **~0.215 ms/query**.

Comfortably under any interactive budget (I8). Real-corpus latency on 8 GB
cards is DEFERRED-TO-MOSSAD (D3); the contract + fixture numbers stand here.

**Backend extension footprint:** `vec0.so` = 156 KiB on disk; zero runtime
network.

### Verdict

sqlite-vec is **CHOSEN**; faiss is **NOT** invoked. `escalate = false` — only
one backend was measured because it passed; the budget was not blown, so the
fallback was not needed.

## Reranker posture (Q2 — I8)

**Lean lexical + score rerank. NO second large model ships.** A cross-encoder
reranker would compete with the primary responder for VRAM / KV-cache on the
8 GB-card target — the I8 footprint risk the plan calls out. Instead
`rag.retrieve` overfetches ~`k*5` candidates via sqlite-vec cosine KNN and
reranks by blending the vector score with a cheap pure-Python lexical
token-overlap signal (`final = 0.65*vector + 0.35*lexical`). Precision-first for
short factual operator queries (the v0.1 use case), zero model footprint, runs
on CPU for tests. A small cross-encoder can be slotted in later *behind the same
function boundary* without changing the frozen signature or any caller.

## Frozen signature (the contract P7 docs + P8 episodic both bind to)

```python
# rag/retrieve.py
def retrieve(query: str, index_path: str, k: int, max_chars: int) -> list[Chunk]: ...

@dataclass(frozen=True)
class Chunk:
    chunk_id: str   # stable id of the source chunk within its index
    source: str     # provenance ('man:mount(8)'; for P8, an audit ts label)
    license: str    # per-source redistribution label ('' for episodic)
    text: str       # the passage (already within the per-call max_chars budget)
    score: float    # final rerank score (higher == more relevant)
```

`index_path` is a **parameter, not a global**: the docs tool passes the corpus
index; P8 `EpisodicMemory` passes the audit-log index — the **same engine, a
different `index_path`, no code change** (SC-P7.3). Verified by
`tests/test_rag_retrieve.py::test_index_path_is_a_parameter_reuse_property`.

Degradation (I9): a missing/unreadable index, an absent backend, an empty query,
or a non-positive `k`/`max_chars` all return `[]` — an empty-but-valid result,
never an exception out to the loop.

## On-disk format (frozen; authoritative copy in `rag/index.py`)

A single sqlite file with three objects:

- `meta(key, value)` — `schema_version`, `dim`, `embed_backend`, `embed_model`.
  The retrieve engine reads `dim` + `embed_backend` back, so it embeds the query
  with the same width/backend the index was built with → dimension-agnostic;
  swapping in the production embedder needs **no code change**.
- `chunks(rowid, chunk_id, source, license, text)` — the passage store.
- `vec_chunks USING vec0(embedding float[<dim>])` — rowid-aligned vectors; KNN
  via `ORDER BY vec_distance_cosine(embedding, ?) LIMIT ?`.

## Freeze statement

The backend (sqlite-vec), the on-disk format, the `retrieve(query, index_path,
k, max_chars) -> list[Chunk]` signature, the `Chunk` shape, and the lexical
rerank posture are **FROZEN** for v0.1. `core/tools/docs.py` (P7) and
`core/agent/episodic.py` (P8) bind to them unchanged. Any change requires a new
superseding decision doc; it cannot be edited in place.
