"""rag — local, offline retrieval engine (corpus + embed + index + retrieve).

This package is OPTIONAL to the core agent: when its dependency (the sqlite-vec
backend in rag/requirements.txt) or a built index is absent, the docs tool that
wraps it degrades to an empty-but-valid result (I9) and the core loop is
unaffected — the core agent has ZERO new runtime deps when rag/ is unused.

The single frozen contract every consumer binds to (SC-P7.3):

    from rag.retrieve import retrieve, Chunk
    retrieve(query, index_path, k, max_chars) -> list[Chunk]

``index_path`` is a parameter so P8 episodic memory reuses THIS engine pointed
at the audit-log index — no second retriever is built.

Backend: sqlite-vec (single-file, server-less). See rag/index.py and
docs/decisions/0003-vector-index.md for the measured Step-1 decision.

No network at runtime; the corpus embed is offline (I1). No AI/LLM/model
language in any user-facing string (I2).
"""

from __future__ import annotations

__all__ = ["retrieve", "Chunk"]


def __getattr__(name: str):  # lazy re-export so importing rag is cheap/dep-free
    if name in ("retrieve", "Chunk"):
        from rag.retrieve import Chunk, retrieve

        return {"retrieve": retrieve, "Chunk": Chunk}[name]
    raise AttributeError(name)
