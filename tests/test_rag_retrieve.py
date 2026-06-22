"""test_rag_retrieve — Phase 7 Step 1 contract gate (offline, no GPU, no socket).

Asserts the frozen rag.retrieve(query, index_path, k, max_chars) -> [Chunk]
contract against the tiny fixture index:
  * a factual query returns tight, relevant chunks within max_chars;
  * an unrelated query returns low/empty signal rather than noise;
  * a missing/unreadable index degrades to [] (I9), never raises;
  * index_path is a real parameter (a second index_path is searchable) — the
    reuse property P8 episodic depends on (SC-P7.3);
  * the fixture index BUILD opens NO network socket (I1);
  * the Chunk text + the docs-style summary clear the I2 forbidden-term filter.

Runs with `python3 -m unittest tests.test_rag_retrieve` (pytest optional).
"""

from __future__ import annotations

import os
import socket
import tempfile
import unittest
from pathlib import Path

from rag import embed as _embed
from rag import index as _index
from rag.fixtures.build_fixture_index import build as build_fixture
from rag.retrieve import Chunk, retrieve

FIXTURE_INDEX = str(Path(__file__).resolve().parents[1] / "rag" / "fixtures" / "mini_index.db")


def _ensure_fixture() -> str:
    if not os.path.exists(FIXTURE_INDEX):
        build_fixture()
    return FIXTURE_INDEX


class NoSocket:
    """Context manager that makes any socket creation raise (I1 egress guard)."""

    def __enter__(self):
        self._orig = socket.socket

        def _blocked(*a, **k):  # noqa: ANN001
            raise AssertionError("network socket opened during offline path (I1)")

        socket.socket = _blocked  # type: ignore[assignment]
        return self

    def __exit__(self, *exc):  # noqa: ANN001
        socket.socket = self._orig


class TestRetrieveContract(unittest.TestCase):
    def setUp(self) -> None:
        self.index = _ensure_fixture()

    def test_signature_returns_chunks(self) -> None:
        res = retrieve("what does the noexec mount flag do", self.index, k=3, max_chars=1200)
        self.assertIsInstance(res, list)
        self.assertTrue(all(isinstance(c, Chunk) for c in res))
        self.assertLessEqual(len(res), 3)

    def test_factual_query_is_relevant_and_top_ranked(self) -> None:
        res = retrieve("what does the noexec mount flag do", self.index, k=3, max_chars=1200)
        self.assertTrue(res, "factual query returned nothing")
        # The noexec chunk should be the top hit.
        self.assertEqual(res[0].chunk_id, "man-mount-noexec")

    def test_max_chars_budget_respected(self) -> None:
        res = retrieve("mount option filesystem", self.index, k=5, max_chars=120)
        total = sum(len(c.text) for c in res)
        self.assertLessEqual(total, 120)

    def test_unrelated_query_low_signal(self) -> None:
        rel = retrieve("noexec mount nosuid filesystem", self.index, k=3, max_chars=1200)
        unrel = retrieve("how do I bake sourdough bread", self.index, k=3, max_chars=1200)
        # Relevant top score strictly beats unrelated top score.
        self.assertTrue(rel)
        if unrel:
            self.assertGreater(rel[0].score, unrel[0].score)

    def test_missing_index_degrades_to_empty(self) -> None:
        self.assertEqual(retrieve("anything", "/no/such/index.db", k=3, max_chars=500), [])

    def test_bad_args_degrade_to_empty(self) -> None:
        self.assertEqual(retrieve("", self.index, k=3, max_chars=500), [])
        self.assertEqual(retrieve("x", self.index, k=0, max_chars=500), [])
        self.assertEqual(retrieve("x", self.index, k=3, max_chars=0), [])

    def test_index_path_is_a_parameter_reuse_property(self) -> None:
        """SC-P7.3: a SECOND index_path is searchable with the SAME engine."""
        chunks = [
            _index.CorpusChunk("ep-1", "audit:2026-06-01", "", "restarted nginx.service after a config reload"),
            _index.CorpusChunk("ep-2", "audit:2026-06-02", "", "formatted /dev/sdb1 with mkfs.ext4 during disk setup"),
        ]
        vecs = _embed.embed_texts([c.text for c in chunks], backend="hashed", dim=_embed.DEFAULT_DIM)
        with tempfile.TemporaryDirectory() as d:
            second = os.path.join(d, "episodic.db")
            _index.build_index(second, chunks, vecs, dim=_embed.DEFAULT_DIM, embed_backend="hashed")
            res = retrieve("what did we do with nginx", second, k=1, max_chars=500)
            self.assertTrue(res)
            self.assertEqual(res[0].chunk_id, "ep-1")
            # Same engine, different index_path: corpus index unaffected.
            self.assertNotEqual(second, self.index)

    def test_fixture_build_opens_no_socket(self) -> None:
        """I1: building the fixture index opens no network socket."""
        with tempfile.TemporaryDirectory() as d:
            with NoSocket():
                chunks = [_index.CorpusChunk("a", "s", "l", "noexec mount option")]
                vecs = _embed.embed_texts([c.text for c in chunks], backend="hashed", dim=_embed.DEFAULT_DIM)
                _index.build_index(os.path.join(d, "x.db"), chunks, vecs, dim=_embed.DEFAULT_DIM, embed_backend="hashed")
                retrieve("noexec", os.path.join(d, "x.db"), k=1, max_chars=200)

    def test_i2_clean_on_chunks_and_summary(self) -> None:
        res = retrieve("firewall panic lockout", self.index, k=3, max_chars=1200)
        summary = f"Retrieved {len(res)} reference passages."
        from core.agent.prompt import _AI_PATTERN

        # Sanctioned docs summary clears the canonical I2 filter.
        self.assertIsNone(_AI_PATTERN.search(summary.lower()))
        # And every returned passage's text clears it too.
        for c in res:
            self.assertIsNone(_AI_PATTERN.search(c.text.lower()), c.chunk_id)


if __name__ == "__main__":
    unittest.main()
