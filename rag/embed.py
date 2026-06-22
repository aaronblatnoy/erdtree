"""rag/embed.py — offline, CPU-only passage/query embedding (I1).

The embedding step is performed ONCE at corpus-build time and never at runtime
over a network — this module opens no socket. Two embedders coexist behind a
single ``embed_texts(texts, dim) -> list[list[float]]`` signature so the index
format and the retrieve engine are embedder-agnostic:

  * The DEFAULT fixture/test embedder is a pure-stdlib hashed bag-of-words
    projection (no downloaded weights, deterministic, runs on any CPU on this
    Linux build host with no GPU). It is sufficient for the tiny fixture corpus
    used by test_rag_retrieve and for the Step-1 footprint/latency measurement.

  * The PRODUCTION embedder is a pinned local sentence-transformer (see
    rag/requirements.txt). It is loaded only when ``backend="st"`` is requested
    and the corpus build runs on the GPU host (DEFERRED-TO-MOSSAD). It is never
    imported by the core agent at runtime and is not required for tests.

Both return L2-normalised float vectors so cosine similarity reduces to a dot
product / the sqlite-vec ``vec_distance_cosine`` ordering.

No AI/LLM/model/inference/embedding language appears in any USER-FACING string
(I2) — those terms are confined to source comments and internal identifiers,
never to a ToolResult.summary, prompt, or banner.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import List, Sequence

#: Vector width used by the fixture/test embedder. The index stores whatever
#: width it was built with (recorded in the index meta table); the retrieve
#: engine reads the width back rather than assuming this constant — so swapping
#: in the production embedder (e.g. 384-d) needs no code change.
DEFAULT_DIM = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _hash_bucket(token: str, dim: int) -> int:
    h = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(h, "little") % dim


def _l2_normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def embed_texts_hashed(texts: Sequence[str], dim: int = DEFAULT_DIM) -> List[List[float]]:
    """Deterministic, offline, stdlib-only hashed bag-of-words embedding.

    Each token is hashed into one of ``dim`` buckets and contributes a unit
    weight (with a mild sublinear term-frequency damp); the resulting vector is
    L2-normalised. Tokens that co-occur produce overlapping vectors, giving the
    fixture corpus enough lexical signal for a precision-first retrieve test
    while requiring zero downloaded weights and no GPU.
    """
    out: List[List[float]] = []
    for text in texts:
        vec = [0.0] * dim
        counts: dict[int, int] = {}
        for tok in _tokenize(text):
            b = _hash_bucket(tok, dim)
            counts[b] = counts.get(b, 0) + 1
        for b, c in counts.items():
            vec[b] = 1.0 + math.log(c)  # sublinear tf
        out.append(_l2_normalize(vec))
    return out


def embed_texts_sentence_transformer(
    texts: Sequence[str], model_name: str
) -> List[List[float]]:  # pragma: no cover - DEFERRED-TO-MOSSAD (GPU corpus build)
    """Production embedder. Loaded lazily; never imported by the core agent.

    Requires the pinned sentence-transformers + torch from rag/requirements.txt.
    Runs offline once the weights are cached locally (no network at embed time).
    """
    from sentence_transformers import SentenceTransformer  # local-only import

    st = SentenceTransformer(model_name)
    vecs = st.encode(list(texts), normalize_embeddings=True, convert_to_numpy=True)
    return [list(map(float, row)) for row in vecs]


def embed_texts(
    texts: Sequence[str],
    *,
    backend: str = "hashed",
    dim: int = DEFAULT_DIM,
    model_name: str = "",
) -> List[List[float]]:
    """Single entry point the index/build path calls.

    backend="hashed" (default): stdlib fixture embedder, dim-configurable.
    backend="st":               production sentence-transformer (mossad only).

    The query path MUST use the same backend/dim the index was built with; the
    index meta table records both so retrieve.py can pick correctly.
    """
    if backend == "hashed":
        return embed_texts_hashed(texts, dim=dim)
    if backend == "st":
        if not model_name:
            raise ValueError("backend='st' requires model_name")
        return embed_texts_sentence_transformer(texts, model_name)
    raise ValueError(f"unknown embed backend: {backend!r}")
