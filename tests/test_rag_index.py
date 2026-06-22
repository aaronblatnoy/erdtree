"""test_rag_index — Phase 7 sibling (a): corpus + index build (offline, no socket).

Tests the full rag/build_corpus.py -> rag/index.py pipeline:

  1. ``build_corpus()`` in smoke-test mode (max_man_pages=5) runs on this host
     with NO network socket opened (I1 egress guard).
  2. The resulting :class:`~rag.build_corpus.RawChunk` records can be embedded
     (hashed backend) and indexed into a temporary sqlite-vec database that
     round-trips a KNN query.
  3. The full ``retrieve()`` contract works against a freshly built index (not
     just the prebuilt fixture mini_index.db).
  4. The fixture corpus.jsonl loads cleanly and its chunks match the prebuilt
     mini_index.db (verifying the fixture is consistent with the index code).
  5. I2 invariant: no chunk text or source label from build_corpus contains
     any term from the canonical ``_AI_PATTERN`` filter.

Run with: ``python3 -m unittest tests.test_rag_index``
"""

from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# sys.path: ensure the project root is on the path when running directly.
# ---------------------------------------------------------------------------
import sys
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from rag import embed as _embed
from rag import index as _index
from rag.build_corpus import (
    RawChunk,
    _chunk_text,
    _clean_man_text,
    iter_man_chunks,
    build_corpus,
    SOURCE_LICENSES,
    RECIPE_ONLY_SOURCES,
)
from rag.retrieve import retrieve, Chunk

FIXTURE_DIR = _ROOT / "rag" / "fixtures"
FIXTURE_CORPUS = FIXTURE_DIR / "corpus.jsonl"
FIXTURE_INDEX = FIXTURE_DIR / "mini_index.db"

MAN_DIR = "/usr/share/man"


# ---------------------------------------------------------------------------
# No-socket shim (I1 egress guard)
# ---------------------------------------------------------------------------


class NoSocket:
    """Context manager that makes any socket.socket() call raise (I1 guard)."""

    def __enter__(self):
        self._orig = socket.socket

        def _blocked(*a, **k):  # noqa: ANN001
            raise AssertionError("network socket opened during offline path (I1 violation)")

        socket.socket = _blocked  # type: ignore[assignment]
        return self

    def __exit__(self, *_exc):  # noqa: ANN001
        socket.socket = self._orig


# ---------------------------------------------------------------------------
# Helper: build a tiny fresh index from caller-supplied chunks
# ---------------------------------------------------------------------------


def _build_temp_index(chunks: list[RawChunk], tmpdir: str) -> str:
    """Embed + index ``chunks`` (hashed backend) into a new .db in ``tmpdir``."""
    vecs = _embed.embed_texts(
        [c.text for c in chunks],
        backend="hashed",
        dim=_embed.DEFAULT_DIM,
    )
    corpus_chunks = [
        _index.CorpusChunk(
            chunk_id=c.chunk_id,
            source=c.source,
            license=c.license,
            text=c.text,
        )
        for c in chunks
    ]
    idx_path = os.path.join(tmpdir, "fresh.db")
    _index.build_index(
        idx_path,
        corpus_chunks,
        vecs,
        dim=_embed.DEFAULT_DIM,
        embed_backend="hashed",
    )
    return idx_path


# ===========================================================================
# Tests
# ===========================================================================


class TestChunkerHelpers(unittest.TestCase):
    """Unit tests for the text-processing helpers in build_corpus."""

    def test_chunk_text_basic(self) -> None:
        text = " ".join(["word"] * 200)
        chunks = _chunk_text(text, chunk_size=100, overlap=20)
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertGreater(len(c), 0)

    def test_chunk_text_empty(self) -> None:
        self.assertEqual(_chunk_text(""), [])
        self.assertEqual(_chunk_text("   "), [])

    def test_chunk_text_short_fits_in_one(self) -> None:
        text = "The noexec flag prevents execution of binaries on the filesystem."
        chunks = _chunk_text(text, chunk_size=400)
        self.assertEqual(len(chunks), 1)
        self.assertIn("noexec", chunks[0])

    def test_clean_man_text_strips_ansi(self) -> None:
        raw = "\x1b[1mmount\x1b[0m(8)  Mount a filesystem.\n\x1b[4mDESCRIPTION\x1b[0m\n"
        cleaned = _clean_man_text(raw)
        self.assertNotIn("\x1b", cleaned)
        self.assertIn("mount", cleaned)

    def test_clean_man_text_strips_backspace_overstrike(self) -> None:
        # Old nroff bold: char + backspace + char (e.g. "b\x08b")
        raw = "b\x08bold text"
        cleaned = _clean_man_text(raw)
        self.assertNotIn("\x08", cleaned)


class TestIterManChunks(unittest.TestCase):
    """Tests for the man-page iterator (uses the real /usr/share/man)."""

    @unittest.skipUnless(
        os.path.isdir(MAN_DIR),
        f"man directory {MAN_DIR} not present on this host",
    )
    def test_yields_rawchunks_no_socket(self) -> None:
        """iter_man_chunks yields RawChunk objects without opening a socket."""
        with NoSocket():
            chunks = list(iter_man_chunks([MAN_DIR], max_pages=5))
        # Expect at least one chunk from the first 5 pages.
        self.assertGreater(len(chunks), 0)
        for c in chunks:
            self.assertIsInstance(c, RawChunk)

    @unittest.skipUnless(
        os.path.isdir(MAN_DIR),
        f"man directory {MAN_DIR} not present on this host",
    )
    def test_chunk_text_length_bounds(self) -> None:
        """Every chunk from real man pages is within sensible length bounds."""
        chunks = list(iter_man_chunks([MAN_DIR], max_pages=5))
        for c in chunks:
            self.assertGreaterEqual(len(c.text), 60, f"chunk {c.chunk_id} too short")
            # No hard upper bound (could be up to ~600 chars from _chunk_text defaults).
            self.assertLessEqual(len(c.text), 800, f"chunk {c.chunk_id} suspiciously long")

    @unittest.skipUnless(
        os.path.isdir(MAN_DIR),
        f"man directory {MAN_DIR} not present on this host",
    )
    def test_i2_clean_no_forbidden_terms_in_chunks(self) -> None:
        """I2: chunk text from man pages must not contain forbidden AI terms."""
        from core.agent.prompt import _AI_PATTERN

        chunks = list(iter_man_chunks([MAN_DIR], max_pages=5))
        for c in chunks:
            self.assertIsNone(
                _AI_PATTERN.search(c.text.lower()),
                f"I2 violation in chunk {c.chunk_id}: {c.text[:120]!r}",
            )

    @unittest.skipUnless(
        os.path.isdir(MAN_DIR),
        f"man directory {MAN_DIR} not present on this host",
    )
    def test_license_field_populated(self) -> None:
        chunks = list(iter_man_chunks([MAN_DIR], max_pages=3))
        for c in chunks:
            self.assertIsInstance(c.license, str)
            self.assertGreater(len(c.license), 0, f"empty license on {c.chunk_id}")

    def test_skips_nonexistent_dir(self) -> None:
        chunks = list(iter_man_chunks(["/no/such/dir/ever"], max_pages=10))
        self.assertEqual(chunks, [])


class TestBuildCorpusSmoke(unittest.TestCase):
    """Smoke-test build_corpus() with max_man_pages=5 — fully offline, no socket."""

    def test_build_corpus_no_socket(self) -> None:
        """Full build_corpus pipeline opens no socket (I1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_jsonl = os.path.join(tmpdir, "corpus.jsonl")
            with NoSocket():
                chunks = build_corpus(
                    man_dirs=[MAN_DIR] if os.path.isdir(MAN_DIR) else [],
                    rhel_doc_dirs=[],
                    arch_wiki_dir="/no/such/arch",
                    so_dir="/no/such/so",
                    cve_dir="/no/such/cve",
                    output_jsonl=out_jsonl,
                    max_man_pages=5,
                )
            # If man dir present we expect some chunks; if absent, empty is fine.
            self.assertIsInstance(chunks, list)
            for c in chunks:
                self.assertIsInstance(c, RawChunk)

    @unittest.skipUnless(
        os.path.isdir(MAN_DIR),
        f"man directory {MAN_DIR} not present on this host",
    )
    def test_build_corpus_emits_jsonl(self) -> None:
        """build_corpus emits a valid JSONL file with required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_jsonl = os.path.join(tmpdir, "corpus.jsonl")
            chunks = build_corpus(
                man_dirs=[MAN_DIR],
                rhel_doc_dirs=[],
                arch_wiki_dir="/no/such/arch",
                so_dir="/no/such/so",
                cve_dir="/no/such/cve",
                output_jsonl=out_jsonl,
                max_man_pages=5,
            )
            self.assertTrue(os.path.exists(out_jsonl))
            with open(out_jsonl, "r", encoding="utf-8") as fh:
                lines = [json.loads(ln) for ln in fh if ln.strip()]
            self.assertEqual(len(lines), len(chunks))
            required = {"chunk_id", "source", "license", "text"}
            for rec in lines:
                self.assertTrue(required <= set(rec.keys()), f"missing fields: {rec}")


class TestIndexBuildAndQuery(unittest.TestCase):
    """The full build -> embed -> index -> query pipeline — fully offline."""

    @unittest.skipUnless(
        os.path.isdir(MAN_DIR),
        f"man directory {MAN_DIR} not present on this host",
    )
    def test_build_index_from_corpus_no_socket(self) -> None:
        """Build a fresh sqlite-vec index from real man-page chunks with no socket."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_jsonl = os.path.join(tmpdir, "corpus.jsonl")
            with NoSocket():
                chunks = build_corpus(
                    man_dirs=[MAN_DIR],
                    rhel_doc_dirs=[],
                    arch_wiki_dir="/no/such",
                    so_dir="/no/such",
                    cve_dir="/no/such",
                    output_jsonl=out_jsonl,
                    max_man_pages=5,
                )
                if not chunks:
                    self.skipTest("no chunks produced (groff unavailable?)")
                idx_path = _build_temp_index(chunks, tmpdir)
            self.assertTrue(os.path.exists(idx_path))
            self.assertGreater(os.path.getsize(idx_path), 0)

    @unittest.skipUnless(
        os.path.isdir(MAN_DIR),
        f"man directory {MAN_DIR} not present on this host",
    )
    def test_index_roundtrip_query(self) -> None:
        """A query against a freshly built index returns Chunks (offline)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_jsonl = os.path.join(tmpdir, "corpus.jsonl")
            chunks = build_corpus(
                man_dirs=[MAN_DIR],
                rhel_doc_dirs=[],
                arch_wiki_dir="/no/such",
                so_dir="/no/such",
                cve_dir="/no/such",
                output_jsonl=out_jsonl,
                max_man_pages=5,
            )
            if not chunks:
                self.skipTest("no chunks produced (groff unavailable?)")
            idx_path = _build_temp_index(chunks, tmpdir)
            results = retrieve("mount filesystem options", idx_path, k=3, max_chars=1500)
            self.assertIsInstance(results, list)
            for r in results:
                self.assertIsInstance(r, Chunk)
                self.assertGreater(len(r.text), 0)

    def test_index_missing_degrades_to_empty(self) -> None:
        """retrieve() on a missing fresh-built index degrades to [] (I9)."""
        result = retrieve("anything", "/no/such/fresh.db", k=3, max_chars=500)
        self.assertEqual(result, [])

    def test_fixture_corpus_loads(self) -> None:
        """The fixture corpus.jsonl loads cleanly with required fields."""
        self.assertTrue(FIXTURE_CORPUS.exists(), f"fixture missing: {FIXTURE_CORPUS}")
        with FIXTURE_CORPUS.open("r", encoding="utf-8") as fh:
            records = [json.loads(ln) for ln in fh if ln.strip()]
        self.assertGreater(len(records), 0)
        required = {"chunk_id", "source", "license", "text"}
        for rec in records:
            self.assertTrue(required <= set(rec.keys()), f"missing fields: {rec}")

    def test_fixture_index_exists_and_is_queryable(self) -> None:
        """The prebuilt mini_index.db opens, reads meta, and answers a KNN query."""
        self.assertTrue(FIXTURE_INDEX.exists(), f"fixture index missing: {FIXTURE_INDEX}")
        conn = _index.open_index(str(FIXTURE_INDEX))
        try:
            meta = _index.read_meta(conn)
            self.assertIn("dim", meta)
            self.assertIn("embed_backend", meta)
            dim = int(meta["dim"])
            # Build a query vector and fire a KNN.
            qvec = _embed.embed_texts(["mount filesystem noexec"], backend="hashed", dim=dim)[0]
            hits = _index.knn(conn, qvec, overfetch=5)
            self.assertGreater(len(hits), 0)
            self.assertEqual(hits[0].chunk_id, "man-mount-noexec")
        finally:
            conn.close()

    def test_fixture_index_build_no_socket(self) -> None:
        """Building an index identical to the fixture opens no socket (I1)."""
        with FIXTURE_CORPUS.open("r", encoding="utf-8") as fh:
            records = [json.loads(ln) for ln in fh if ln.strip()]
        raw_chunks = [
            RawChunk(
                chunk_id=r["chunk_id"],
                source=r["source"],
                license=r["license"],
                text=r["text"],
            )
            for r in records
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            with NoSocket():
                idx_path = _build_temp_index(raw_chunks, tmpdir)
            self.assertTrue(os.path.exists(idx_path))
            # Query it without a socket too.
            with NoSocket():
                results = retrieve("noexec mount option", idx_path, k=2, max_chars=800)
            self.assertTrue(results, "expected hits from fixture-equivalent index")
            self.assertEqual(results[0].chunk_id, "man-mount-noexec")


class TestSourceLicenses(unittest.TestCase):
    """Verify the license manifest constants are coherent."""

    def test_all_sources_have_licenses(self) -> None:
        expected = {"man", "rhel", "arch", "so", "cve"}
        self.assertEqual(set(SOURCE_LICENSES.keys()), expected)

    def test_recipe_only_sources_are_subset(self) -> None:
        self.assertTrue(RECIPE_ONLY_SOURCES <= set(SOURCE_LICENSES.keys()))

    def test_recipe_only_contains_arch_and_so(self) -> None:
        self.assertIn("arch", RECIPE_ONLY_SOURCES)
        self.assertIn("so", RECIPE_ONLY_SOURCES)


if __name__ == "__main__":
    unittest.main()
