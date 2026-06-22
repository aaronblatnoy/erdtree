"""rag/build_index_prod.py — production corpus orchestrator.

Runs the full pipeline in one command:
  build_corpus(man + rocky docs) -> embed_texts -> build_index -> corpus.db

This module is ADDITIVE: it calls the frozen rag.build_corpus, rag.embed, and
rag.index APIs unchanged.  It does NOT reimplement chunking, embedding, or
indexing.  See rag/fixtures/build_fixture_index.py for the fixture analog (this
generalises it from a hardcoded JSONL to a live build_corpus run).

No network is opened at build or runtime (I1).  No AI/LLM/model/inference/
embedding/retrieval language appears in any operator-facing string (I2).

Backend default: "hashed" (pure-stdlib, offline, deterministic).
Backend "st" (sentence-transformer) is present but lazily guarded;
that path is DEFERRED-TO-MOSSAD and is never imported on this host.

Usage (CLI)
-----------
  .venv/bin/python -m rag.build_index_prod \\
      --man-dir /usr/share/man \\
      --rocky-dir <repo>/runtime/rag/sources/rocky-docs \\
      --output-index <repo>/runtime/rag/corpus.db \\
      --output-jsonl <repo>/runtime/rag/corpus.jsonl \\
      --max-man-pages 60

  Output: "Built reference index: N passages, X.X MB."
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from rag.build_corpus import build_corpus, write_license_manifest, RawChunk
from rag.embed import embed_texts, DEFAULT_DIM
from rag.index import build_index, CorpusChunk

# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------

#: Absolute path to the repo root's rag/LICENSES.md (written by every prod build).
_LICENSES_PATH = Path(__file__).resolve().parent / "LICENSES.md"


@dataclass
class BuildReport:
    """Summary of a completed corpus build run."""

    chunk_count: int
    source_counts: Dict[str, int]   # {"man": N, "rocky": M}
    index_bytes: int
    elapsed_seconds: float
    output_index: Path
    output_jsonl: Path


# ---------------------------------------------------------------------------
# Core orchestrator
# ---------------------------------------------------------------------------


def run_build(
    *,
    man_dirs: Sequence[str | Path] = ("/usr/share/man",),
    rocky_doc_dirs: Sequence[str | Path] = ("/var/lib/erdtree/rocky-docs",),
    output_index: str | Path,
    output_jsonl: str | Path,
    embed_backend: str = "hashed",
    embed_model: str = "",
    dim: int = DEFAULT_DIM,
    max_man_pages: Optional[int] = None,
    max_rocky_files: Optional[int] = None,
) -> BuildReport:
    """Run the full corpus -> index pipeline and return a BuildReport.

    Calls the FROZEN functions unchanged:
      build_corpus()  ->  embed_texts()  ->  build_index()

    Converts RawChunk 1:1 to CorpusChunk (identical 4-field shape).
    Writes rag/LICENSES.md via write_license_manifest (existing function).
    Writes additive meta keys (built_at, source_counts) that retrieve ignores.

    Parameters
    ----------
    man_dirs:       Man-page root directories (default /usr/share/man).
    rocky_doc_dirs: Staged Rocky/RHEL doc directories.
    output_index:   Destination corpus.db path.
    output_jsonl:   Destination corpus.jsonl path (written by build_corpus).
    embed_backend:  "hashed" (default, offline) or "st" (mossad-only, lazy).
    embed_model:    Required when backend="st"; ignored for "hashed".
    dim:            Vector width (256 default; must match the chosen backend).
    max_man_pages:  Cap on man pages rendered (None = no cap).
    max_rocky_files: Cap on Rocky doc files read (None = no cap).

    Returns
    -------
    BuildReport with chunk count, per-source split, index size, and elapsed time.

    Notes
    -----
    No network is opened (I1).  Arch/SO/CVE source dirs default to
    nonexistent paths so those RECIPE_ONLY sources produce zero chunks here.
    build_index unlinks an existing index file before writing (overwrite-safe).
    """
    t0 = time.monotonic()

    # -----------------------------------------------------------------------
    # Step 1: build corpus (man + rocky docs; arch/so/cve at nonexistent defaults)
    # -----------------------------------------------------------------------
    raw_chunks: List[RawChunk] = build_corpus(
        man_dirs=man_dirs,
        rhel_doc_dirs=rocky_doc_dirs,
        # Leave arch/so/cve at their nonexistent defaults so RECIPE_ONLY stays empty.
        arch_wiki_dir="/var/lib/erdtree/arch-wiki-dump",
        so_dir="/var/lib/erdtree/so-sysadmin",
        cve_dir="/var/lib/erdtree/cve-corpus",
        output_jsonl=output_jsonl,
        max_man_pages=max_man_pages,
        max_rhel_files=max_rocky_files,
    )

    # -----------------------------------------------------------------------
    # Step 2: embed (same backend the index will record; query path reads it back)
    # -----------------------------------------------------------------------
    texts = [c.text for c in raw_chunks]
    vectors = embed_texts(texts, backend=embed_backend, dim=dim, model_name=embed_model)

    # -----------------------------------------------------------------------
    # Step 3: convert RawChunk -> CorpusChunk (identical 4-field shape, 1:1)
    # -----------------------------------------------------------------------
    corpus_chunks: List[CorpusChunk] = [
        CorpusChunk(
            chunk_id=rc.chunk_id,
            source=rc.source,
            license=rc.license,
            text=rc.text,
        )
        for rc in raw_chunks
    ]

    # -----------------------------------------------------------------------
    # Step 4: build the index (overwrites existing file cleanly)
    # -----------------------------------------------------------------------
    build_index(
        output_index,
        corpus_chunks,
        vectors,
        dim=dim,
        embed_backend=embed_backend,
        embed_model=embed_model,
    )

    # -----------------------------------------------------------------------
    # Step 5: write additive meta (built_at, source_counts) — 0003-safe
    # retrieve.read_meta ignores unknown keys; these are for operator provenance.
    # -----------------------------------------------------------------------
    import sqlite3

    idx_path = Path(output_index)
    conn = sqlite3.connect(str(idx_path))
    try:
        built_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        man_count = sum(1 for rc in raw_chunks if rc.source.startswith("man:"))
        rocky_count = sum(1 for rc in raw_chunks if rc.source.startswith("Rocky/RHEL"))
        source_counts_str = f"man={man_count},rocky={rocky_count}"
        conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
                     ("built_at", built_at))
        conn.execute("INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
                     ("source_counts", source_counts_str))
        conn.commit()
    finally:
        conn.close()

    # -----------------------------------------------------------------------
    # Step 6: regenerate rag/LICENSES.md
    # -----------------------------------------------------------------------
    write_license_manifest(_LICENSES_PATH)

    elapsed = time.monotonic() - t0
    index_bytes = idx_path.stat().st_size

    return BuildReport(
        chunk_count=len(corpus_chunks),
        source_counts={"man": man_count, "rocky": rocky_count},
        index_bytes=index_bytes,
        elapsed_seconds=elapsed,
        output_index=idx_path,
        output_jsonl=Path(output_jsonl),
    )


# ---------------------------------------------------------------------------
# I2-clean summary printer
# ---------------------------------------------------------------------------


def _format_summary(report: BuildReport) -> str:
    """Return the I2-clean one-line operator summary.

    No AI/LLM/model/inference/embedding/retrieval terms — operator-facing only.
    """
    mb = report.index_bytes / (1024 * 1024)
    return f"Built reference index: {report.chunk_count} passages, {mb:.1f} MB."


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="Build the corpus reference index from local documentation sources.",
    )
    parser.add_argument(
        "--man-dir",
        action="append",
        dest="man_dirs",
        metavar="DIR",
        help="Man-pages root directory (can repeat; default /usr/share/man).",
    )
    parser.add_argument(
        "--rocky-dir",
        action="append",
        dest="rocky_dirs",
        metavar="DIR",
        help="Staged Rocky/RHEL docs directory (can repeat).",
    )
    parser.add_argument(
        "--output-index",
        default=str(
            Path(__file__).resolve().parent.parent / "runtime" / "rag" / "corpus.db"
        ),
        help="Destination index file (default: <repo>/runtime/rag/corpus.db).",
    )
    parser.add_argument(
        "--output-jsonl",
        default=str(
            Path(__file__).resolve().parent.parent / "runtime" / "rag" / "corpus.jsonl"
        ),
        help="Destination corpus JSONL (default: <repo>/runtime/rag/corpus.jsonl).",
    )
    parser.add_argument(
        "--backend",
        default="hashed",
        choices=["hashed", "st"],
        help='Embedding backend: "hashed" (default, offline) or "st" (mossad-only).',
    )
    parser.add_argument(
        "--embed-model",
        default="",
        help="Sentence-transformer model name (required when --backend=st).",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=DEFAULT_DIM,
        help=f"Vector dimension (default {DEFAULT_DIM}).",
    )
    parser.add_argument(
        "--max-man-pages",
        type=int,
        default=None,
        help="Cap on man pages rendered (omit for no cap).",
    )
    parser.add_argument(
        "--max-rocky-files",
        type=int,
        default=None,
        help="Cap on Rocky doc files read (omit for no cap).",
    )
    args = parser.parse_args()

    man_dirs = args.man_dirs or ["/usr/share/man"]
    rocky_dirs = args.rocky_dirs or ["/var/lib/erdtree/rocky-docs"]

    try:
        report = run_build(
            man_dirs=man_dirs,
            rocky_doc_dirs=rocky_dirs,
            output_index=args.output_index,
            output_jsonl=args.output_jsonl,
            embed_backend=args.backend,
            embed_model=args.embed_model,
            dim=args.dim,
            max_man_pages=args.max_man_pages,
            max_rocky_files=args.max_rocky_files,
        )
    except RuntimeError as exc:
        if "sqlite-vec backend not installed" in str(exc):
            print(
                "ERROR: sqlite-vec is not available in this Python interpreter.\n"
                "Re-run under the project venv: "
                "/home/aaron/erdtree/.venv/bin/python -m rag.build_index_prod",
                file=sys.stderr,
            )
            sys.exit(1)
        raise

    print(_format_summary(report))
