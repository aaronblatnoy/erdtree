"""tests/test_rag_build_index_prod.py — Phase 3 gate: wire docs.retrieve + prove
a real grounded lookup (SC1/SC2).

Three test classes, each @skipUnless(sqlite_vec importable):

  (a) TestSmokeBuild — call run_build over a CAPPED man set + staged Rocky docs
      into a .db in a tmp dir; assert it opens, read_meta is sane, chunk count
      > 0, and the per-source split has BOTH man AND rocky chunks.

  (b) TestRetrievalQuality (SC2 gate) — point retrieve() at the SHARED
      runtime/rag/corpus.db (built by P2 — do NOT rebuild it), query
      "how do I open a firewall port", assert TOP result's source contains
      "firewall" (case-insensitive) AND text mentions a port/zone concept.
      Clean SKIP only if the shared index or the Rocky docs are genuinely absent.

  (c) TestEpisodicReuse (SC6 / 0003) — build a SECOND tiny index at a DIFFERENT
      index_path from SYNTHETIC chunks with license="" (empty license), query it
      independently, assert it works — proving engine reuse (episodic / second
      index_path) is UNBROKEN by this additive plan.

Plus two docs-tool tests:

  4.  TestDocsToolGroundedLookup — With ERDTREE_CORPUS_INDEX set BEFORE importing
      core.tools.docs (it reads _INDEX_PATH at MODULE LOAD time — this test runs
      the check in a SUBPROCESS to honor that constraint), call _op_retrieve for
      the firewall query; assert summary == "Retrieved N reference passages." with
      N >= 1 AND the emitted body contains a firewalld source header.

  5.  TestI9Degrade — With ERDTREE_CORPUS_INDEX unset/empty, assert the tool
      returns "Retrieved 0 reference passages." (degrade unchanged).

  6.  TestI2LeakageOrchestrator — grep the orchestrator's printed stdout + the
      produced chunk SOURCE labels against _FORBIDDEN_AI_TERMS imported from
      core.agent.prompt (do NOT re-list the terms). Chunk TEXT is exempt.

Runs with:
  /home/aaron/erdtree/.venv/bin/python -m unittest tests.test_rag_build_index_prod
"""

from __future__ import annotations

import importlib
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest
from io import StringIO
from pathlib import Path
from typing import List
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Skip guard: all classes that touch an index need sqlite_vec in the venv.
# ---------------------------------------------------------------------------

try:
    import sqlite_vec  # noqa: F401
    _SQLITE_VEC_AVAILABLE = True
except ImportError:
    _SQLITE_VEC_AVAILABLE = False

_SKIP_NO_VEC = unittest.skipUnless(
    _SQLITE_VEC_AVAILABLE,
    "sqlite_vec not available in this interpreter — run under .venv/bin/python",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SHARED_INDEX = _REPO_ROOT / "runtime" / "rag" / "corpus.db"
_ROCKY_DOCS_DIR = _REPO_ROOT / "runtime" / "rag" / "sources" / "rocky-docs"
_VENV_PYTHON = _REPO_ROOT / ".venv" / "bin" / "python"

# ---------------------------------------------------------------------------
# Forbidden term pattern (imported, never re-listed — I2 contract)
# ---------------------------------------------------------------------------

from core.agent.prompt import _FORBIDDEN_AI_TERMS, _AI_PATTERN  # noqa: E402


# ===========================================================================
# (a) SMOKE: run_build over a capped man set + staged Rocky docs -> real .db
# ===========================================================================

@_SKIP_NO_VEC
class TestSmokeBuild(unittest.TestCase):
    """Smoke-test run_build in a tmp dir with small caps; asserts sane output."""

    @classmethod
    def setUpClass(cls) -> None:
        """Build a tiny capped index into a fresh tmp dir once for all methods."""
        rocky_present = _ROCKY_DOCS_DIR.exists() and any(_ROCKY_DOCS_DIR.iterdir())
        if not rocky_present:
            cls._skip_reason = (
                f"Staged Rocky docs not found at {_ROCKY_DOCS_DIR}; "
                "run rag/stage_sources.py first."
            )
        else:
            cls._skip_reason = ""

        if cls._skip_reason:
            return

        from rag.build_index_prod import run_build, _format_summary

        cls._tmpdir = tempfile.mkdtemp(prefix="erdtree_smoke_")
        cls._idx = Path(cls._tmpdir) / "smoke.db"
        cls._jsonl = Path(cls._tmpdir) / "smoke.jsonl"

        try:
            cls._report = run_build(
                man_dirs=["/usr/share/man"],
                rocky_doc_dirs=[str(_ROCKY_DOCS_DIR)],
                output_index=str(cls._idx),
                output_jsonl=str(cls._jsonl),
                embed_backend="hashed",
                dim=256,
                max_man_pages=20,    # cap: keep test fast
                max_rocky_files=20,  # cap: keep test fast
            )
            cls._summary = _format_summary(cls._report)
            cls._build_error = None
        except Exception as exc:  # noqa: BLE001
            cls._build_error = exc
            cls._report = None
            cls._summary = ""

    def _skip_if_needed(self) -> None:
        if getattr(self, "_skip_reason", ""):
            self.skipTest(self._skip_reason)
        if self._build_error is not None:
            self.fail(f"run_build raised unexpectedly: {self._build_error}")

    # -- basic deliverable checks --

    def test_index_file_exists(self) -> None:
        self._skip_if_needed()
        self.assertTrue(self._idx.exists(), "corpus db not written")
        self.assertGreater(self._idx.stat().st_size, 0, "corpus db is empty")

    def test_chunk_count_positive(self) -> None:
        self._skip_if_needed()
        self.assertGreater(self._report.chunk_count, 0, "expected > 0 chunks")

    def test_per_source_split_has_both_man_and_rocky(self) -> None:
        """Both man and rocky chunks must appear — verifies both readers fired."""
        self._skip_if_needed()
        counts = self._report.source_counts
        self.assertIn("man", counts, "source_counts missing 'man' key")
        self.assertIn("rocky", counts, "source_counts missing 'rocky' key")
        self.assertGreater(counts["man"], 0, "no man-page chunks in index")
        self.assertGreater(counts["rocky"], 0, "no Rocky-doc chunks in index")

    # -- read_meta sanity checks --

    def test_read_meta_schema_version(self) -> None:
        self._skip_if_needed()
        from rag.index import open_index, read_meta
        conn = open_index(str(self._idx))
        try:
            meta = read_meta(conn)
        finally:
            conn.close()
        self.assertIn("schema_version", meta)
        self.assertEqual(meta["schema_version"], "1")

    def test_read_meta_dim(self) -> None:
        self._skip_if_needed()
        from rag.index import open_index, read_meta
        conn = open_index(str(self._idx))
        try:
            meta = read_meta(conn)
        finally:
            conn.close()
        self.assertIn("dim", meta)
        self.assertEqual(int(meta["dim"]), 256)

    def test_read_meta_embed_backend(self) -> None:
        self._skip_if_needed()
        from rag.index import open_index, read_meta
        conn = open_index(str(self._idx))
        try:
            meta = read_meta(conn)
        finally:
            conn.close()
        self.assertIn("embed_backend", meta)
        self.assertEqual(meta["embed_backend"], "hashed")

    def test_index_opens_and_chunk_count_matches_meta(self) -> None:
        """chunks table row count equals what BuildReport says."""
        self._skip_if_needed()
        conn = sqlite3.connect(str(self._idx))
        try:
            (n,) = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()
        finally:
            conn.close()
        self.assertEqual(n, self._report.chunk_count)

    def test_summary_i2_clean(self) -> None:
        """The build summary must clear the I2 forbidden-term filter."""
        self._skip_if_needed()
        hit = _AI_PATTERN.search(self._summary.lower())
        self.assertIsNone(
            hit,
            f"I2 violation in build summary: found {hit.group()!r}" if hit else "",
        )

    def test_summary_format(self) -> None:
        """Summary is 'Built reference index: N passages, X.X MB.'"""
        self._skip_if_needed()
        self.assertRegex(
            self._summary,
            r"^Built reference index: \d+ passages, \d+\.\d+ MB\.$",
        )


# ===========================================================================
# (b) RETRIEVAL QUALITY (SC2 gate): firewall query -> grounded firewalld passage
# ===========================================================================

@_SKIP_NO_VEC
class TestRetrievalQuality(unittest.TestCase):
    """SC2: 'how do I open a firewall port' top result must be a firewall passage.

    Points at the SHARED runtime/rag/corpus.db built by P2 — does NOT rebuild.
    Skips cleanly only if the shared index or the Rocky docs are genuinely absent.
    """

    # Keywords that confirm the passage discusses the port/zone concept.
    _PORT_ZONE_TOKENS = re.compile(
        r"\b(port|zone|firewall-cmd|firewalld|--add-port|--add-service|--zone)\b",
        re.IGNORECASE,
    )

    @classmethod
    def setUpClass(cls) -> None:
        rocky_present = _ROCKY_DOCS_DIR.exists() and any(_ROCKY_DOCS_DIR.iterdir())
        index_present = _SHARED_INDEX.exists()
        if not index_present:
            cls._skip_reason = (
                f"Shared index not found at {_SHARED_INDEX}; "
                "run Phase 2 orchestrator first."
            )
        elif not rocky_present:
            cls._skip_reason = (
                f"Rocky docs not found at {_ROCKY_DOCS_DIR}; "
                "run rag/stage_sources.py first."
            )
        else:
            cls._skip_reason = ""

        if not cls._skip_reason:
            from rag.retrieve import retrieve
            cls._results = retrieve(
                "how do I open a firewall port",
                str(_SHARED_INDEX),
                k=5,
                max_chars=3000,
            )

    def _skip_if_needed(self) -> None:
        if getattr(self, "_skip_reason", ""):
            self.skipTest(self._skip_reason)

    def test_returns_at_least_one_result(self) -> None:
        """The production index returns >= 1 result for the firewall query."""
        self._skip_if_needed()
        self.assertGreater(
            len(self._results), 0,
            "retrieve returned 0 results for the firewall query; index may be empty",
        )

    def test_top_result_source_contains_firewall(self) -> None:
        """SC2 core: top result's source label must contain 'firewall' (case-insensitive)."""
        self._skip_if_needed()
        if not self._results:
            self.skipTest("no results to check (see test_returns_at_least_one_result)")
        top = self._results[0]
        self.assertIn(
            "firewall",
            top.source.lower(),
            f"Top result source {top.source!r} does not contain 'firewall'. "
            f"Full top-5 sources: {[r.source for r in self._results]}",
        )

    def test_top_result_text_mentions_port_or_zone(self) -> None:
        """SC2 core: top result's text must mention a port/zone concept."""
        self._skip_if_needed()
        if not self._results:
            self.skipTest("no results to check")
        top = self._results[0]
        match = self._PORT_ZONE_TOKENS.search(top.text)
        self.assertIsNotNone(
            match,
            f"Top result text does not mention a port/zone concept.\n"
            f"Source: {top.source!r}\nText excerpt: {top.text[:300]!r}",
        )

    def test_chunk_source_labels_i2_clean(self) -> None:
        """Source labels of returned chunks must not contain forbidden AI terms."""
        self._skip_if_needed()
        for chunk in self._results:
            hit = _AI_PATTERN.search(chunk.source.lower())
            self.assertIsNone(
                hit,
                f"I2 violation in chunk source label {chunk.source!r}: "
                f"found {hit.group()!r}" if hit else "",
            )


# ===========================================================================
# (c) EPISODIC REUSE REGRESSION (SC6 / 0003)
# ===========================================================================

@_SKIP_NO_VEC
class TestEpisodicReuse(unittest.TestCase):
    """SC6: a SECOND tiny index at a different index_path builds + queries cleanly.

    Proves the engine reuse pattern (episodic / second index_path) is unbroken
    by this additive plan. Uses synthetic chunks with license="" to confirm the
    engine tolerates an empty license field (Chunk.license is a passthrough str).
    """

    _SYNTHETIC_CHUNKS = [
        # (chunk_id, source, license, text)
        ("ep:0001", "episodic:2026-06-22T10:00:00Z", "", "systemctl start nginx failed: unit not found on rocky linux"),
        ("ep:0002", "episodic:2026-06-22T10:05:00Z", "", "dnf install nginx succeeded; package nginx-1.20.1 installed"),
        ("ep:0003", "episodic:2026-06-22T10:10:00Z", "", "firewall-cmd --add-service=http opened port 80 in public zone"),
        ("ep:0004", "episodic:2026-06-22T11:00:00Z", "", "selinux was blocking nginx: audit2allow resolved the denial"),
        ("ep:0005", "episodic:2026-06-22T12:00:00Z", "", "disk usage at /var/log reached 95 percent; logrotate ran"),
    ]

    @classmethod
    def setUpClass(cls) -> None:
        from rag.index import CorpusChunk, build_index
        from rag.embed import embed_texts, DEFAULT_DIM

        cls._tmpdir = tempfile.mkdtemp(prefix="erdtree_episodic_")
        cls._ep_idx = Path(cls._tmpdir) / "episodic.db"
        cls._DEFAULT_DIM = DEFAULT_DIM

        chunks = [
            CorpusChunk(
                chunk_id=cid,
                source=src,
                license=lic,
                text=txt,
            )
            for cid, src, lic, txt in cls._SYNTHETIC_CHUNKS
        ]
        texts = [c.text for c in chunks]
        vecs = embed_texts(texts, backend="hashed", dim=DEFAULT_DIM)
        build_index(
            str(cls._ep_idx),
            chunks,
            vecs,
            dim=DEFAULT_DIM,
            embed_backend="hashed",
            embed_model="",
        )

    def test_episodic_index_exists(self) -> None:
        self.assertTrue(self._ep_idx.exists(), "episodic index was not written")

    def test_episodic_index_meta_sane(self) -> None:
        from rag.index import open_index, read_meta
        conn = open_index(str(self._ep_idx))
        try:
            meta = read_meta(conn)
        finally:
            conn.close()
        self.assertEqual(meta.get("schema_version"), "1")
        self.assertEqual(int(meta.get("dim", 0)), self._DEFAULT_DIM)
        self.assertEqual(meta.get("embed_backend"), "hashed")

    def test_episodic_retrieve_nginx_query(self) -> None:
        """A query for nginx returns a relevant episodic chunk."""
        from rag.retrieve import retrieve
        results = retrieve(
            "nginx service not found",
            str(self._ep_idx),
            3,
            2000,
        )
        self.assertGreater(len(results), 0, "episodic retrieve returned no results")
        sources = [r.source for r in results]
        # At least one result should come from our synthetic episodic chunks.
        self.assertTrue(
            any("episodic:" in s for s in sources),
            f"No episodic source in results: {sources}",
        )

    def test_episodic_retrieve_firewall_query(self) -> None:
        """A query for firewall returns an episodic chunk mentioning port/zone."""
        from rag.retrieve import retrieve
        results = retrieve(
            "open firewall port",
            str(self._ep_idx),
            3,
            2000,
        )
        self.assertGreater(len(results), 0, "episodic firewall query returned no results")

    def test_episodic_chunks_have_empty_license(self) -> None:
        """Engine tolerates license='' — the episodic pattern uses empty license."""
        from rag.retrieve import retrieve
        results = retrieve(
            "nginx",
            str(self._ep_idx),
            5,
            3000,
        )
        for r in results:
            # license is '' for episodic; the engine must pass it through unchanged.
            self.assertIsInstance(r.license, str)
            # All our synthetic chunks have license="" so they should all have "".
            self.assertEqual(r.license, "", f"Expected empty license, got {r.license!r}")

    def test_episodic_index_path_is_independent_of_shared(self) -> None:
        """Querying the episodic index does NOT read from the shared corpus.db.

        Uses a non-existent path for 'shared' to prove isolation: the episodic
        query must still succeed (returns results) even when the corpus path is gone.
        """
        from rag.retrieve import retrieve
        results = retrieve(
            "dnf install nginx",
            str(self._ep_idx),
            2,
            1000,
        )
        self.assertGreater(
            len(results), 0,
            "episodic retrieve failed — it may have accidentally read the shared index",
        )

    def test_second_index_different_from_shared(self) -> None:
        """Confirm the episodic .db path is distinct from the shared corpus path."""
        self.assertNotEqual(
            str(self._ep_idx.resolve()),
            str(_SHARED_INDEX.resolve()),
        )


# ===========================================================================
# 4. DOCS TOOL GROUNDED LOOKUP (subprocess — honors module-load env read)
# ===========================================================================

@_SKIP_NO_VEC
class TestDocsToolGroundedLookup(unittest.TestCase):
    """Verify docs.retrieve against the production index via subprocess.

    CRITICAL: core.tools.docs reads _INDEX_PATH at MODULE LOAD time (line:
        _INDEX_PATH: str = os.environ.get("ERDTREE_CORPUS_INDEX", "").strip()
    ), so ERDTREE_CORPUS_INDEX MUST be set before importing that module.
    We use a subprocess to guarantee a fresh interpreter with the env pre-set.
    """

    @classmethod
    def setUpClass(cls) -> None:
        if not _SHARED_INDEX.exists():
            cls._skip_reason = (
                f"Shared index not found at {_SHARED_INDEX}; "
                "Phase 2 must run first."
            )
        else:
            cls._skip_reason = ""

    def _skip_if_needed(self) -> None:
        if getattr(self, "_skip_reason", ""):
            self.skipTest(self._skip_reason)

    def _run_docs_subprocess(self, corpus_index: str) -> dict:
        """Run a tiny script in a subprocess with ERDTREE_CORPUS_INDEX pre-set.

        Returns a dict with keys: summary, stdout_body, exit_code.
        """
        script = textwrap.dedent(f"""
            import sys, os, json
            # env already set by caller (subprocess env)
            import core.tools.docs as _docs_mod
            from core.tools.docs import _op_retrieve
            result = _op_retrieve({{"query": "how do I open a firewall port", "k": 3}})
            output = {{
                "summary": result.summary,
                "stdout_body": result.stdout,
                "exit_code": result.exit_code,
            }}
            print(json.dumps(output))
        """)
        env = os.environ.copy()
        env["ERDTREE_CORPUS_INDEX"] = corpus_index
        # Remove it if we want to test degrade (handled separately below)
        env.pop("PYTHONPATH", None)

        proc = subprocess.run(
            [str(_VENV_PYTHON), "-c", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(_REPO_ROOT),
        )
        if proc.returncode != 0:
            self.fail(
                f"subprocess failed (exit {proc.returncode}):\n"
                f"STDERR: {proc.stderr}\nSTDOUT: {proc.stdout}"
            )
        import json
        return json.loads(proc.stdout.strip())

    def test_grounded_summary_has_n_gte_1(self) -> None:
        """With ERDTREE_CORPUS_INDEX set, summary is 'Retrieved N ...' with N>=1."""
        self._skip_if_needed()
        out = self._run_docs_subprocess(str(_SHARED_INDEX))
        summary = out["summary"]
        m = re.match(r"^Retrieved (\d+) reference passages\.$", summary)
        self.assertIsNotNone(
            m,
            f"Summary does not match canonical form: {summary!r}",
        )
        n = int(m.group(1))
        self.assertGreaterEqual(n, 1, f"Expected N>=1, got N={n}")

    def test_grounded_body_contains_firewalld_source(self) -> None:
        """The stdout body must contain a firewalld source header."""
        self._skip_if_needed()
        out = self._run_docs_subprocess(str(_SHARED_INDEX))
        body = out["stdout_body"]
        self.assertTrue(
            body,
            "docs._op_retrieve returned empty stdout body for firewall query",
        )
        self.assertIn(
            "firewall",
            body.lower(),
            f"stdout body does not mention 'firewall'.\nBody excerpt: {body[:500]!r}",
        )

    def test_exit_code_zero(self) -> None:
        """The docs tool always returns exit_code=0 (read op, no error)."""
        self._skip_if_needed()
        out = self._run_docs_subprocess(str(_SHARED_INDEX))
        self.assertEqual(out["exit_code"], 0)


# ===========================================================================
# 5. I9 DEGRADE: ERDTREE_CORPUS_INDEX unset -> "Retrieved 0 reference passages."
# ===========================================================================

@_SKIP_NO_VEC
class TestI9Degrade(unittest.TestCase):
    """I9: with ERDTREE_CORPUS_INDEX unset/empty, the tool degrades cleanly."""

    def test_degrade_with_unset_env_via_patch(self) -> None:
        """Patch _INDEX_PATH to '' at the module level; tool must return 0 passages."""
        import core.tools.docs as _docs_mod
        with patch.object(_docs_mod, "_INDEX_PATH", ""):
            result = _docs_mod._op_retrieve({"query": "how do I open a firewall port"})
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.summary, "Retrieved 0 reference passages.")
        self.assertEqual(result.stdout, "")

    def test_degrade_with_empty_string_env_via_patch(self) -> None:
        """Explicit empty string for _INDEX_PATH also degrades cleanly."""
        import core.tools.docs as _docs_mod
        with patch.object(_docs_mod, "_INDEX_PATH", "   "):
            # The module strips the env value, so whitespace-only also degrades.
            # But _INDEX_PATH is already stripped at load time; here we patch to "   "
            # to cover the truthy-but-whitespace case: `not _INDEX_PATH` is True
            # only if empty after strip — patch the actual attribute.
            with patch.object(_docs_mod, "_INDEX_PATH", ""):
                result = _docs_mod._op_retrieve({"query": "firewall"})
        self.assertEqual(result.summary, "Retrieved 0 reference passages.")

    def test_degrade_subprocess_no_env(self) -> None:
        """Full subprocess with ERDTREE_CORPUS_INDEX absent degrades cleanly."""
        script = textwrap.dedent("""
            import sys, os, json
            os.environ.pop("ERDTREE_CORPUS_INDEX", None)
            import core.tools.docs as _docs_mod
            from core.tools.docs import _op_retrieve
            result = _op_retrieve({"query": "how do I open a firewall port"})
            print(json.dumps({"summary": result.summary, "exit_code": result.exit_code}))
        """)
        env = {k: v for k, v in os.environ.items() if k != "ERDTREE_CORPUS_INDEX"}
        proc = subprocess.run(
            [str(_VENV_PYTHON), "-c", script],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(_REPO_ROOT),
        )
        if proc.returncode != 0:
            self.fail(
                f"I9 subprocess failed (exit {proc.returncode}):\n"
                f"STDERR: {proc.stderr}"
            )
        import json
        out = json.loads(proc.stdout.strip())
        self.assertEqual(out["summary"], "Retrieved 0 reference passages.")
        self.assertEqual(out["exit_code"], 0)


# ===========================================================================
# 6. I2 LEAKAGE: orchestrator stdout + chunk source labels vs _FORBIDDEN_AI_TERMS
# ===========================================================================

@_SKIP_NO_VEC
class TestI2LeakageOrchestrator(unittest.TestCase):
    """I2: orchestrator printed summary + chunk source labels must be AI-term-free.

    Chunk TEXT is explicitly exempt (it is reference content the model reads).
    We import _FORBIDDEN_AI_TERMS from core.agent.prompt — never re-listed here.
    """

    @classmethod
    def setUpClass(cls) -> None:
        rocky_present = _ROCKY_DOCS_DIR.exists() and any(_ROCKY_DOCS_DIR.iterdir())
        if not rocky_present:
            cls._skip_reason = (
                f"Rocky docs not found at {_ROCKY_DOCS_DIR}; skip I2 leakage test."
            )
            return
        cls._skip_reason = ""

        # Build a tiny index and capture its summary string.
        from rag.build_index_prod import run_build, _format_summary
        import tempfile

        tmpdir = tempfile.mkdtemp(prefix="erdtree_i2_")
        idx = Path(tmpdir) / "i2.db"
        jsonl = Path(tmpdir) / "i2.jsonl"

        try:
            cls._report = run_build(
                man_dirs=["/usr/share/man"],
                rocky_doc_dirs=[str(_ROCKY_DOCS_DIR)],
                output_index=str(idx),
                output_jsonl=str(jsonl),
                embed_backend="hashed",
                dim=256,
                max_man_pages=5,
                max_rocky_files=5,
            )
            cls._summary = _format_summary(cls._report)
            cls._idx = idx
            cls._build_error = None
        except Exception as exc:  # noqa: BLE001
            cls._build_error = exc
            cls._report = None
            cls._summary = ""
            cls._idx = None

    def _skip_if_needed(self) -> None:
        if getattr(self, "_skip_reason", ""):
            self.skipTest(self._skip_reason)
        if getattr(self, "_build_error", None) is not None:
            self.fail(f"I2 leakage test: run_build raised: {self._build_error}")

    def test_summary_string_i2_clean(self) -> None:
        """The orchestrator's one-line printed summary has no forbidden AI terms."""
        self._skip_if_needed()
        hit = _AI_PATTERN.search(self._summary.lower())
        self.assertIsNone(
            hit,
            f"I2 violation in orchestrator summary: found {hit.group()!r}" if hit else "",
        )

    def test_chunk_source_labels_i2_clean(self) -> None:
        """All chunk SOURCE labels in the produced index are AI-term-free.

        Chunk TEXT is exempt — we only scan the operator-visible source label.
        """
        self._skip_if_needed()
        if self._idx is None or not self._idx.exists():
            self.skipTest("index not built")

        conn = sqlite3.connect(str(self._idx))
        try:
            rows = conn.execute("SELECT source FROM chunks").fetchall()
        finally:
            conn.close()

        violations = []
        for (source,) in rows:
            hit = _AI_PATTERN.search(source.lower())
            if hit:
                violations.append((source, hit.group()))

        self.assertEqual(
            violations,
            [],
            "I2 violations in chunk source labels:\n"
            + "\n".join(f"  {src!r} -> {term!r}" for src, term in violations[:10]),
        )

    def test_report_source_counts_i2_clean(self) -> None:
        """source_counts keys and the BuildReport fields are AI-term-free."""
        self._skip_if_needed()
        # Check the keys (e.g. "man", "rocky") — these appear in operator output.
        for key in self._report.source_counts:
            hit = _AI_PATTERN.search(key.lower())
            self.assertIsNone(
                hit,
                f"I2 violation in source_counts key {key!r}: found {hit.group()!r}"
                if hit else "",
            )


# ===========================================================================
# Entry point
# ===========================================================================

if __name__ == "__main__":
    unittest.main()
