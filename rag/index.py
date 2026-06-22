"""rag/index.py — local vector index: build + query (FROZEN format, Step 1).

BACKEND DECISION (P7 Step 1, measured on this Linux build host)
---------------------------------------------------------------
Chosen backend: **sqlite-vec** (single-file, server-less, ISO-friendly, and
reusable by P8 episodic memory over the audit log). faiss is the documented
fallback and is NOT used — sqlite-vec passed the fixture footprint/latency
budget comfortably. See docs/decisions/0003-vector-index.md for the measured
numbers; this module is the authoritative on-disk format.

Why sqlite-vec over faiss (summary; full rationale in 0003):
  * One file. The whole index is a single .db — trivial to drop into an ISO and
    to point P8 episodic at a SECOND .db (the audit-log index) with no new code.
  * Server-less. No daemon, no mmap-of-multiple-sidecar-files, no C++ build step
    on the target box; the loadable extension is a ~160 KiB vec0.so.
  * The chunk text + metadata live in the SAME sqlite file as the vectors, so a
    search returns the passage directly — no parallel id->text store to keep in
    sync (faiss stores only vectors + an int id; you must bolt on your own
    doc store, which is exactly the kind of drift P8 reuse would suffer from).

ON-DISK FORMAT (frozen)
-----------------------
A single sqlite database file with three objects:

  meta(key TEXT PRIMARY KEY, value TEXT)
      Records 'dim', 'embed_backend', 'embed_model', 'schema_version'. The
      retrieve engine reads 'dim' + 'embed_backend' back so it embeds the QUERY
      with the same width/backend the index was built with (dimension-agnostic
      contract — swapping the production embedder needs no code change).

  chunks(rowid INTEGER PRIMARY KEY, chunk_id TEXT, source TEXT,
         license TEXT, text TEXT)
      The passage store. rowid is the join key to the vector table.

  vec_chunks  -- a vec0 virtual table:  USING vec0(embedding float[<dim>])
      One row per chunk, rowid-aligned with chunks. Cosine distance ordering
      via the KNN ``embedding MATCH ? ... ORDER BY distance LIMIT ?`` form.

QUERY API (the engine in retrieve.py calls these — not user-facing)
  open_index(index_path) -> sqlite3.Connection (extension loaded, read-only-ish)
  read_meta(conn) -> dict
  knn(conn, query_vec, overfetch) -> list[Hit]   (rowid, score, fields)

No network, no model, no AI/LLM/agent language in any user-facing string (I1/I2).
This module's strings are internal (SQL + log/debug); nothing here reaches a
ToolResult.summary.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

SCHEMA_VERSION = "1"

# ---------------------------------------------------------------------------
# Extension loading
# ---------------------------------------------------------------------------


def _load_vec_extension(conn: sqlite3.Connection) -> None:
    """Load the sqlite-vec loadable extension into a connection.

    Raises a RuntimeError (NOT an opaque sqlite error) if the extension or the
    enable_load_extension capability is unavailable, so callers can degrade to
    an 'index unavailable' ToolResult (I9) rather than crash.
    """
    try:
        import sqlite_vec  # local import; rag-only dependency
    except ImportError as exc:  # pragma: no cover - exercised when dep absent
        raise RuntimeError("sqlite-vec backend not installed") from exc
    if not hasattr(conn, "enable_load_extension"):
        raise RuntimeError("sqlite3 build lacks enable_load_extension")
    conn.enable_load_extension(True)
    try:
        sqlite_vec.load(conn)
    finally:
        conn.enable_load_extension(False)


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CorpusChunk:
    """One normalised corpus chunk fed to the index builder."""

    chunk_id: str
    source: str
    license: str
    text: str


def _vec_json(vec: Sequence[float]) -> str:
    # sqlite-vec accepts a JSON array of floats for the float[] column.
    return json.dumps([float(x) for x in vec])


def build_index(
    index_path: str | Path,
    chunks: Sequence[CorpusChunk],
    vectors: Sequence[Sequence[float]],
    *,
    dim: int,
    embed_backend: str,
    embed_model: str = "",
) -> None:
    """Build (or overwrite) a single-file sqlite-vec index at index_path.

    Pure local file I/O — no network. The caller supplies vectors already
    produced by rag.embed (offline). chunks[i] aligns with vectors[i].
    """
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors must be the same length")

    path = Path(index_path)
    if path.exists():
        path.unlink()
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    try:
        _load_vec_extension(conn)
        conn.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)")
        conn.executemany(
            "INSERT INTO meta(key, value) VALUES (?, ?)",
            [
                ("schema_version", SCHEMA_VERSION),
                ("dim", str(dim)),
                ("embed_backend", embed_backend),
                ("embed_model", embed_model),
            ],
        )
        conn.execute(
            "CREATE TABLE chunks("
            "rowid INTEGER PRIMARY KEY, chunk_id TEXT, source TEXT, "
            "license TEXT, text TEXT)"
        )
        conn.execute(
            f"CREATE VIRTUAL TABLE vec_chunks USING vec0(embedding float[{dim}])"
        )
        for i, (chunk, vec) in enumerate(zip(chunks, vectors), start=1):
            if len(vec) != dim:
                raise ValueError(
                    f"vector {i} has width {len(vec)}, expected {dim}"
                )
            conn.execute(
                "INSERT INTO chunks(rowid, chunk_id, source, license, text) "
                "VALUES (?, ?, ?, ?, ?)",
                (i, chunk.chunk_id, chunk.source, chunk.license, chunk.text),
            )
            conn.execute(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                (i, _vec_json(vec)),
            )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hit:
    """One KNN hit: a chunk plus its similarity score (higher == closer)."""

    rowid: int
    score: float
    chunk_id: str
    source: str
    license: str
    text: str


def open_index(index_path: str | Path) -> sqlite3.Connection:
    """Open an existing index file with the vec extension loaded.

    Raises FileNotFoundError if the file is absent and RuntimeError if the
    backend cannot be loaded — callers (retrieve.py) translate either into a
    degraded, empty-but-valid result (I9).
    """
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(str(path))
    conn = sqlite3.connect(str(path))
    _load_vec_extension(conn)
    return conn


def read_meta(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM meta").fetchall()
    return {k: v for k, v in rows}


def knn(
    conn: sqlite3.Connection,
    query_vec: Sequence[float],
    overfetch: int,
) -> List[Hit]:
    """K-nearest-neighbour search; returns up to ``overfetch`` Hits.

    Uses sqlite-vec cosine distance. Score is ``1 - distance`` so that a higher
    score means a closer match (the retrieve engine reranks on top of this).
    """
    rows = conn.execute(
        """
        SELECT v.rowid, vec_distance_cosine(v.embedding, ?) AS distance,
               c.chunk_id, c.source, c.license, c.text
        FROM vec_chunks v
        JOIN chunks c ON c.rowid = v.rowid
        ORDER BY distance
        LIMIT ?
        """,
        (_vec_json(query_vec), int(overfetch)),
    ).fetchall()
    return [
        Hit(
            rowid=r[0],
            score=1.0 - float(r[1]),
            chunk_id=r[2],
            source=r[3],
            license=r[4],
            text=r[5],
        )
        for r in rows
    ]
