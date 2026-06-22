"""core/agent/episodic.py — Episodic past-operation recall (Phase 8, SC-P8.3).

EpisodicMemory builds and queries a local vector index over the audit JSONL
that the REPL already writes (/var/log/{tier}/audit.jsonl).  Past operations
are recalled by similarity so the loop can answer "what did we do earlier?"
AS IF KNOWN — no visible reset, no re-ask (SC-P8.3/SC-P8.4).

REUSE PROPERTY (SC-P7.3)
-------------------------
This module does NOT implement a retriever.  It imports and calls
``rag.retrieve.retrieve(query, index_path, k, max_chars)`` — the frozen
engine built in Phase 7 — pointed at a DIFFERENT index_path (the episodic
audit index) than the docs corpus index.  The difference in index_path proves
reuse-not-fork: the same engine, two index files, zero code duplication.

INDEX LIFECYCLE
---------------
The episodic index lives at a caller-supplied path (default under the same
directory as the audit log).  On each call to ``recall()``:

  1. Check the audit log's current byte-size against a stored baseline.
  2. If the size grew beyond REBUILD_DELTA_BYTES, rebuild the index from the
     full JSONL (cheap for audit logs of typical operator-session length).
  3. Query the index via the reused rag.retrieve engine.

"Cheap append" is appropriate here because audit JSONL records are tiny
(<512 B each per the audit.py _SUMMARY_MAX_BYTES constant) and the expected
corpus per session is hundreds of records, not millions.  A just-written op
is simultaneously still in the verbatim recent-window history, so eventual
consistency is acceptable (A5).

CORPUS FIELDS (A5)
------------------
Each audit JSONL record becomes one episodic chunk whose text is:
  "nl_input: {nl_input}  command: {translated_command}  result: {result}"
This is the "what did we do" corpus.  The ``tool`` and ``exit_code`` fields
are included when present to aid disambiguation.

I2 COMPLIANCE
-------------
No user-facing string (chunk text, ToolResult summary, log message) contains
the terms forbidden by core/agent/prompt.py _FORBIDDEN_AI_TERMS.  The
identifiers below are internal; operator-facing output is plain Linux language.

I9 COMPLIANCE
-------------
Every failure path — missing audit log, missing/corrupt episodic index,
backend unavailable, empty query, non-positive k — degrades to [] and never
raises out to the caller.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional

# THE FROZEN ENGINE — imported, not re-implemented (SC-P7.3).
from rag.retrieve import Chunk, retrieve
from rag import embed as _embed
from rag import index as _index

# ---------------------------------------------------------------------------
# Constants (all tunable — no tier names here, I6)
# ---------------------------------------------------------------------------

#: Default number of past-operation chunks to return per recall.
DEFAULT_K: int = 3

#: Default character budget for recalled snippets.
DEFAULT_MAX_CHARS: int = 1200

#: Minimum byte-growth in the audit log that triggers an index rebuild.
REBUILD_DELTA_BYTES: int = 4096  # ~8 typical records


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _record_to_text(rec: dict) -> str:
    """Render one audit record as a short operator-readable snippet.

    Keeps the language plain and operator-facing (I2): no AI/LLM/agent terms.
    Fields follow the audit.py _SCHEMA_KEYS contract (A5).
    """
    parts: list[str] = []
    if rec.get("nl_input"):
        parts.append(f"request: {rec['nl_input']}")
    if rec.get("translated_command"):
        parts.append(f"command: {rec['translated_command']}")
    if rec.get("tool"):
        parts.append(f"tool: {rec['tool']}")
    if rec.get("exit_code") is not None:
        parts.append(f"exit: {rec['exit_code']}")
    if rec.get("result"):
        parts.append(f"result: {rec['result']}")
    return "  ".join(parts) if parts else "(empty record)"


def _chunk_id_for(rec: dict, index: int) -> str:
    """Stable chunk_id for a record: use its timestamp if present, else index."""
    ts = rec.get("ts")
    if ts is not None:
        return f"audit:{ts}"
    return f"audit:row{index}"


def _load_audit_records(audit_path: str | Path) -> list[dict]:
    """Read all valid JSON records from the audit log; skip malformed lines (I9)."""
    p = Path(audit_path)
    if not p.exists():
        return []
    records: list[dict] = []
    with p.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def _build_episodic_index(audit_path: str | Path, index_path: str | Path) -> bool:
    """Build (or rebuild) the episodic index from the audit log.

    Returns True on success, False on any failure (I9 — caller degrades to []).
    """
    try:
        records = _load_audit_records(audit_path)
        if not records:
            return False

        chunks = [
            _index.CorpusChunk(
                chunk_id=_chunk_id_for(rec, i),
                source=f"audit:{rec.get('ts', i)}",
                license="",
                text=_record_to_text(rec),
            )
            for i, rec in enumerate(records)
        ]
        texts = [c.text for c in chunks]
        vectors = _embed.embed_texts(texts, backend="hashed", dim=_embed.DEFAULT_DIM)
        _index.build_index(
            index_path,
            chunks,
            vectors,
            dim=_embed.DEFAULT_DIM,
            embed_backend="hashed",
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class EpisodicMemory:
    """Past-operation recall via the reused rag.retrieve engine.

    Usage::

        mem = EpisodicMemory(
            audit_path="/var/log/some-tier/audit.jsonl",
            index_path="/var/log/some-tier/episodic.db",   # DIFFERENT from the docs index
        )
        snippets: list[Chunk] = mem.recall("what did we do with nginx")
        # each Chunk.text is a plain operator-readable past-operation snippet

    The caller supplies ``index_path`` explicitly; it MUST differ from the docs
    corpus index path — that difference is what proves SC-P7.3 (reuse, not fork).

    Backward-compatible degradation: if the audit log is absent, if the index
    cannot be built, or if the query is empty/k<=0, ``recall()`` returns [] (I9).
    """

    def __init__(
        self,
        audit_path: str | Path,
        index_path: str | Path,
        *,
        k: int = DEFAULT_K,
        max_chars: int = DEFAULT_MAX_CHARS,
        rebuild_delta: int = REBUILD_DELTA_BYTES,
    ) -> None:
        self._audit_path = Path(audit_path)
        self._index_path = Path(index_path)
        self._k = k
        self._max_chars = max_chars
        self._rebuild_delta = rebuild_delta
        # Byte-size of the audit log at last index build; None = not yet built.
        self._last_built_size: Optional[int] = None

    @property
    def index_path(self) -> str:
        """The episodic index path as a string (for the reuse-assertion test)."""
        return str(self._index_path)

    def _audit_size(self) -> int:
        """Current byte-size of the audit log; 0 if absent."""
        try:
            return self._audit_path.stat().st_size
        except OSError:
            return 0

    def _needs_rebuild(self) -> bool:
        """True if the index has never been built or the log grew enough."""
        if self._last_built_size is None:
            return True
        current = self._audit_size()
        return (current - self._last_built_size) >= self._rebuild_delta

    def _ensure_index(self) -> bool:
        """Build/refresh the index if needed.  Returns True if index is usable."""
        if not self._needs_rebuild() and self._index_path.exists():
            return True
        # Ensure the index directory exists.
        try:
            self._index_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        success = _build_episodic_index(self._audit_path, self._index_path)
        if success:
            self._last_built_size = self._audit_size()
        return success and self._index_path.exists()

    def recall(
        self,
        query: str,
        *,
        k: Optional[int] = None,
        max_chars: Optional[int] = None,
    ) -> List[Chunk]:
        """Return up to k past-operation snippets relevant to query.

        Uses the frozen rag.retrieve engine pointed at the episodic index_path
        (a different path from the docs corpus index — proving SC-P7.3 reuse).

        Degrades to [] on: empty/blank query, k<=0, max_chars<=0, missing audit
        log, index-build failure, backend unavailable.  Never raises (I9).
        """
        effective_k = k if k is not None else self._k
        effective_max_chars = max_chars if max_chars is not None else self._max_chars

        # Fast-path degrades (I9).
        if not query or not query.strip():
            return []
        if effective_k <= 0 or effective_max_chars <= 0:
            return []

        try:
            if not self._ensure_index():
                return []
            # THE KEY CALL: same frozen engine, different index_path (SC-P7.3).
            return retrieve(
                query=query,
                index_path=str(self._index_path),
                k=effective_k,
                max_chars=effective_max_chars,
            )
        except Exception:
            # Any unexpected error degrades gracefully (I9).
            return []
