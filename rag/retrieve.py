"""rag/retrieve.py — THE REUSABLE RETRIEVAL ENGINE (frozen signature, Step 1).

FROZEN CONTRACT (SC-P7.3 — bound by core/tools/docs.py AND P8 episodic):

    retrieve(query, index_path, k, max_chars) -> list[Chunk]

  * query      (str)  the natural-language lookup.
  * index_path (str)  the on-disk index file. This is a PARAMETER, not a global:
                      the docs tool passes the corpus index; P8 EpisodicMemory
                      passes the audit-log index — the SAME engine, a DIFFERENT
                      index_path, NO code change. This is the whole point of the
                      reusable-engine requirement.
  * k          (int)  number of tight chunks to return (per-tier budget knob).
  * max_chars  (int)  hard cap on total returned text (per-tier budget knob).

  -> list[Chunk]      at most k chunks, total text <= max_chars, precision-first
                      (ranked best-first). On a missing/unreadable index, returns
                      [] — an empty-but-valid result, never an exception (I9).

PIPELINE:  embed query (offline, same backend/dim the index was built with)
           -> ANN overfetch (~k * OVERFETCH_FACTOR via sqlite-vec cosine KNN)
           -> rerank (lexical-overlap + vector-score blend — see RERANKER below)
           -> trim to k chunks within max_chars.

RERANKER POSTURE (P7 Step 1 decision — I8):
  LEAN LEXICAL+SCORE rerank. We deliberately ship NO second large cross-encoder:
  on the 8 GB-card target a reranker model would compete with the primary
  responder for VRAM/KV-cache (the I8 footprint risk the plan calls out). The
  rerank here blends the index cosine score with a cheap lexical token-overlap
  signal computed in pure Python. This is precision-first for short factual
  operator queries (the v0.1 use case) and adds no model footprint. A small
  cross-encoder can be slotted in later behind this same function boundary
  without touching the frozen signature or any caller.

No network at runtime; this module opens no socket (I1). No AI/LLM/model/
inference/embedding/retrieval language in any user-facing string (I2) — the
identifiers below are internal; the docs tool produces the operator-facing
summary ("Retrieved N reference passages.").
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from rag import embed as _embed
from rag import index as _index

#: ANN overfetch multiplier — pull ~k*FACTOR candidates so the lexical rerank
#: has room to reorder before we trim to k. Precision over recall.
OVERFETCH_FACTOR = 5
#: Floor on the candidate pool so tiny k still gives the reranker something.
OVERFETCH_FLOOR = 10
#: Blend weight: final = (1-ALPHA)*vector_score + ALPHA*lexical_overlap.
RERANK_LEXICAL_ALPHA = 0.35

_TOKEN_RE = re.compile(r"[a-z0-9]+")


# ---------------------------------------------------------------------------
# Frozen return shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Chunk:
    """One retrieved passage. The frozen unit core/tools/docs.py joins and P8
    episodic recall renders. Fields are stable across both index_path uses.

    chunk_id:  stable id of the source chunk within its index.
    source:    provenance label (e.g. 'man:mount(8)', or an audit ts for P8).
    license:   per-source redistribution label (corpus chunks); '' for episodic.
    text:      the passage text (already within the per-call max_chars budget
               when returned as part of the list).
    score:     final rerank score (higher == more relevant); for ordering/debug.
    """

    chunk_id: str
    source: str
    license: str
    text: str
    score: float


# ---------------------------------------------------------------------------
# Lexical rerank helper (no model footprint — I8)
# ---------------------------------------------------------------------------


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _lexical_overlap(query_tokens: set[str], text: str) -> float:
    """Jaccard-ish overlap of query tokens present in the candidate text."""
    if not query_tokens:
        return 0.0
    cand = _tokens(text)
    if not cand:
        return 0.0
    hits = len(query_tokens & cand)
    return hits / len(query_tokens)


# ---------------------------------------------------------------------------
# THE FROZEN ENGINE
# ---------------------------------------------------------------------------


def retrieve(query: str, index_path: str, k: int, max_chars: int) -> List[Chunk]:
    """Retrieve up to k tight, reranked chunks for query within max_chars.

    See module docstring for the frozen contract. Degrades to [] on any
    missing/unreadable index or empty query (I9) — never raises out to the loop.
    """
    if not query or not query.strip() or k <= 0 or max_chars <= 0:
        return []

    try:
        conn = _index.open_index(index_path)
    except (FileNotFoundError, RuntimeError):
        # Index absent or backend unavailable -> empty-but-valid (I9).
        return []

    try:
        meta = _index.read_meta(conn)
        dim = int(meta.get("dim", _embed.DEFAULT_DIM))
        backend = meta.get("embed_backend", "hashed")
        model = meta.get("embed_model", "")

        # Embed the query with the SAME backend/dim the index was built with.
        (qvec,) = _embed.embed_texts(
            [query], backend=backend, dim=dim, model_name=model
        )

        overfetch = max(k * OVERFETCH_FACTOR, OVERFETCH_FLOOR)
        hits = _index.knn(conn, qvec, overfetch)
    finally:
        conn.close()

    if not hits:
        return []

    # Rerank: blend vector score with lexical overlap (lean, no model — I8).
    qtokens = _tokens(query)
    reranked: List[tuple[float, _index.Hit]] = []
    for h in hits:
        lex = _lexical_overlap(qtokens, h.text)
        final = (1.0 - RERANK_LEXICAL_ALPHA) * h.score + RERANK_LEXICAL_ALPHA * lex
        reranked.append((final, h))
    reranked.sort(key=lambda pair: pair[0], reverse=True)

    # Trim to k chunks within the max_chars budget (precision-first).
    out: List[Chunk] = []
    used = 0
    for final, h in reranked:
        if len(out) >= k:
            break
        text = h.text
        if used + len(text) > max_chars:
            remaining = max_chars - used
            if remaining <= 0:
                break
            text = text[:remaining]
        out.append(
            Chunk(
                chunk_id=h.chunk_id,
                source=h.source,
                license=h.license,
                text=text,
                score=final,
            )
        )
        used += len(text)
    return out
