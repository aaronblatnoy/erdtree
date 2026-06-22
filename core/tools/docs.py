"""core/tools/docs.py — local reference passage retrieval tool.

Supported operations
--------------------
  retrieve (READ) — look up relevant reference passages from the local corpus
                    index. No gate friction: this is a pure read; the loop
                    chooses to call it; an empty result is a valid answer.

Design rules (load-bearing invariants)
---------------------------------------
  I1  No network. docs.py opens NO socket. All retrieval is against a local
      on-disk index (sqlite-vec, single file). The corpus embed is offline.
  I2  NO AI/LLM/model/agent/inference/retrieval/embedding language in any
      user-facing string. The ToolResult.summary is EXACTLY:
          "Retrieved N reference passages."
      ("reference passages" is plain operator language.)
  I3  READ op — the classifier returns Gate.ALLOW with no friction; this tool
      needs NO permission gate and calls permissions ZERO times itself.
  I4  The REPL writes the audit record; this module does not.
  I6  ZERO tier/product names. k/max_chars defaults are read from OPAQUE env
      vars (ERDTREE_RETRIEVAL_K / ERDTREE_RETRIEVAL_MAXCHARS) via os.environ.
  I9  If the index path is absent, unreadable, or the rag backend is not
      installed, the tool registers and returns an empty-but-valid ToolResult
      — NEVER crashes build_repl. The loop simply gets no chunks and continues.

Shape (mirrors core/tools/services.py exactly):
  per-op functions -> ToolResult (via rag.retrieve, NOT run_subprocess — a
  pure-Python read, no subprocess)
  _DISPATCH table
  ToolSpec with per-op permission_class
  self-registration via registry.register(DOCS_SPEC)

Note on run_subprocess
  This tool does NOT call run_subprocess. The retrieve operation is a pure
  Python read against a local sqlite file — there is no shell command to
  synthesize. synthesize_command() in repl.py emits a read-shaped sentinel
  ("man -k <query>") so the classifier returns Gate.ALLOW with no friction.
  This is consistent with the plan: synthesize_command's docs branch renders
  a clearly-read shape (folded into the P6.8 repl.py pass).
"""

from __future__ import annotations

import os
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
)

# ---------------------------------------------------------------------------
# Per-tier retrieval budget (opaque env knobs — I6, no tier names)
# ---------------------------------------------------------------------------

_DEFAULT_K = 3
_DEFAULT_MAX_CHARS = 2000

_RETRIEVAL_K: int = int(os.environ.get("ERDTREE_RETRIEVAL_K", _DEFAULT_K) or _DEFAULT_K)
_RETRIEVAL_MAXCHARS: int = int(
    os.environ.get("ERDTREE_RETRIEVAL_MAXCHARS", _DEFAULT_MAX_CHARS)
    or _DEFAULT_MAX_CHARS
)

# ---------------------------------------------------------------------------
# Corpus index path (opaque env knob — I6)
# ---------------------------------------------------------------------------

_INDEX_PATH: str = os.environ.get("ERDTREE_CORPUS_INDEX", "").strip()

# ---------------------------------------------------------------------------
# Attempt to import the retrieval engine at module load time.
# If the rag backend (sqlite-vec) is absent or the index is missing, the tool
# registers in a DEGRADED mode that returns empty-but-valid results (I9).
# ---------------------------------------------------------------------------

_RETRIEVE_AVAILABLE = False
_retrieve_fn = None  # type: ignore[assignment]
_Chunk = None  # type: ignore[assignment]

try:
    from rag.retrieve import Chunk as _Chunk, retrieve as _retrieve_fn  # type: ignore[assignment]
    _RETRIEVE_AVAILABLE = True
except Exception:  # pragma: no cover — sqlite-vec absent or rag broken
    pass


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_retrieve(args: dict[str, Any]) -> ToolResult:
    """Retrieve relevant reference passages for a query from the local corpus.

    Returns at most k passages within max_chars. On any failure (missing index,
    absent backend, empty query) returns an empty-but-valid ToolResult (I9).
    No AI/LLM/model language in the summary (I2).
    """
    query: str = args.get("query", "")
    raw_k = args.get("k")
    k: int = int(raw_k) if raw_k is not None else _RETRIEVAL_K
    k = max(1, k)  # clamp: non-positive k degrades to 1 (retrieve handles k>0)

    if not _RETRIEVE_AVAILABLE or not _INDEX_PATH:
        return ToolResult(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Retrieved 0 reference passages.",
        )

    try:
        chunks = _retrieve_fn(query, _INDEX_PATH, k, _RETRIEVAL_MAXCHARS)
    except Exception:  # noqa: BLE001 — any failure degrades cleanly (I9)
        return ToolResult(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Retrieved 0 reference passages.",
        )

    if not chunks:
        return ToolResult(
            exit_code=0,
            stdout="",
            stderr="",
            summary="Retrieved 0 reference passages.",
        )

    # Join passages: each chunk separated by a blank line; source in a header.
    parts: list[str] = []
    for c in chunks:
        header = f"[{c.source}]" if c.source else ""
        parts.append(f"{header}\n{c.text}".strip())
    stdout = "\n\n".join(parts)

    # I2-clean summary — "reference passages" is operator language, not AI jargon.
    summary = f"Retrieved {len(chunks)} reference passages."

    return ToolResult(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "retrieve": _op_retrieve,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a docs operation and return a structured ToolResult.

    The caller (REPL / router) is responsible for:
      1. Resolving the permission gate (ALLOW — this is READ; no friction).
      2. Writing the audit record.

    This function runs retrieval, constructs a ToolResult, and returns.
    It NEVER writes to the audit log itself.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for docs tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

DOCS_SPEC = ToolSpec(
    name="docs",
    description=(
        "Look up relevant passages from the local Linux reference corpus. "
        "Use this when you need to check a flag, option, or behaviour before "
        "constructing a command."
    ),
    ops={
        "retrieve": OpSpec(
            op_name="retrieve",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="query",
                    type=str,
                    required=True,
                    description=(
                        "Plain-language question or topic to look up "
                        "(e.g. 'noexec mount flag behaviour')."
                    ),
                ),
                ArgSpec(
                    name="k",
                    type=int,
                    required=False,
                    description=(
                        "Maximum number of passages to return "
                        f"(default {_DEFAULT_K})."
                    ),
                    default=_DEFAULT_K,
                ),
            ],
            description=(
                "Retrieve relevant reference passages for a query. "
                "Returns at most k passages within the configured character budget."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(DOCS_SPEC)
