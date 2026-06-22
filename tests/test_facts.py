"""
tests/test_facts.py

Stdlib unittest tests for core/context/facts.py (P8: per-host facts preamble)
and the backward-compatible optional-prepend thread in core/agent/context.py.

Invariants verified:
  I2  Preamble text clears the _FORBIDDEN_AI_TERMS filter (no AI/model/agent
      language).  The filter is IMPORTED from core.agent.prompt, not re-listed.
  I5  Facts preamble augments (prepends to) the snapshot text; it does NOT
      replace it.
  I9  Absent file -> empty preamble, no exception, no user-visible output.

Run:
    python3 -m unittest tests.test_facts -v
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from core.context.facts import FactsLoader, load_facts
from core.agent.prompt import _FORBIDDEN_AI_TERMS, _AI_PATTERN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _passes_i2(text: str) -> bool:
    """Return True if text contains no I2-forbidden terms (whole-word match)."""
    return _AI_PATTERN.search(text) is None


# ---------------------------------------------------------------------------
# FactsLoader unit tests
# ---------------------------------------------------------------------------

class TestFactsLoaderNoPath(unittest.TestCase):
    """FactsLoader with no path configured."""

    def test_none_path_returns_empty(self):
        loader = FactsLoader(path=None)
        self.assertEqual(loader.load(), "")

    def test_empty_string_path_returns_empty(self):
        loader = FactsLoader(path="")
        self.assertEqual(loader.load(), "")

    def test_path_property_is_none_when_not_set(self):
        loader = FactsLoader()
        self.assertIsNone(loader.path)


class TestFactsLoaderAbsentFile(unittest.TestCase):
    """FactsLoader when the file does not exist."""

    def test_absent_file_returns_empty_string(self, tmp_path=None):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            nonexistent = os.path.join(d, "no_such_file.txt")
            loader = FactsLoader(path=nonexistent)
            result = loader.load()
            self.assertEqual(result, "")

    def test_absent_file_does_not_raise(self):
        loader = FactsLoader(path="/this/path/does/not/exist/facts.txt")
        # Must not raise (I9)
        try:
            result = loader.load()
        except Exception as exc:
            self.fail(f"FactsLoader.load() raised unexpectedly: {exc}")
        self.assertEqual(result, "")


class TestFactsLoaderPresentFile(unittest.TestCase):
    """FactsLoader when the file exists and contains text."""

    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.TemporaryDirectory()
        self._dir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _write_facts(self, content: str) -> Path:
        p = self._dir / "facts.txt"
        p.write_text(content, encoding="utf-8")
        return p

    def test_preamble_returned_when_file_present(self):
        p = self._write_facts("hostname: prod-web-01\nrole: nginx front-end")
        loader = FactsLoader(path=str(p))
        result = loader.load()
        self.assertIn("hostname: prod-web-01", result)
        self.assertIn("role: nginx front-end", result)

    def test_empty_file_returns_empty_string(self):
        p = self._write_facts("")
        loader = FactsLoader(path=str(p))
        self.assertEqual(loader.load(), "")

    def test_whitespace_only_file_returns_empty_string(self):
        p = self._write_facts("   \n\t\n  ")
        loader = FactsLoader(path=str(p))
        self.assertEqual(loader.load(), "")

    def test_text_is_stripped(self):
        p = self._write_facts("  some facts text  \n\n")
        loader = FactsLoader(path=str(p))
        result = loader.load()
        self.assertEqual(result, "some facts text")

    def test_path_property_matches_supplied_path(self):
        p = self._write_facts("x: 1")
        loader = FactsLoader(path=str(p))
        self.assertEqual(loader.path, p)

    def test_i2_filter_passes_on_clean_text(self):
        """I2: operator-authored facts text must not contain forbidden AI terms."""
        p = self._write_facts(
            "hostname: prod-web-01\n"
            "role: nginx front-end\n"
            "datacenter: us-east-1\n"
            "owner: ops-team\n"
        )
        loader = FactsLoader(path=str(p))
        result = loader.load()
        self.assertTrue(
            _passes_i2(result),
            f"Loaded facts text contains I2-forbidden term: {result!r}",
        )

    def test_load_facts_convenience_function(self):
        """load_facts() is equivalent to FactsLoader(path).load()."""
        p = self._write_facts("env: staging")
        result = load_facts(path=str(p))
        self.assertEqual(result, "env: staging")


class TestFactsLoaderI2Filter(unittest.TestCase):
    """Validate that the I2 pattern rejects forbidden terms."""

    def test_forbidden_terms_imported_from_prompt(self):
        """The filter is imported from core.agent.prompt, not re-listed."""
        self.assertIsInstance(_FORBIDDEN_AI_TERMS, frozenset)
        self.assertIn("llm", _FORBIDDEN_AI_TERMS)
        self.assertIn("agent", _FORBIDDEN_AI_TERMS)

    def test_ai_term_detected_in_dirty_text(self):
        """Ensure the I2 filter would catch forbidden terms if present."""
        dirty = "this system uses an llm for processing"
        self.assertFalse(_passes_i2(dirty))

    def test_clean_operator_text_passes(self):
        clean = "hostname: web-01\nrole: database\nenv: production"
        self.assertTrue(_passes_i2(clean))


# ---------------------------------------------------------------------------
# TurnContext optional-prepend thread (core/agent/context.py)
# ---------------------------------------------------------------------------

class TestTurnContextFactsPrepend(unittest.TestCase):
    """Test the backward-compatible facts preamble thread in TurnContext."""

    def _make_cache(self, snapshot_text: str = "OS: Rocky Linux 9"):
        """Build a SnapshotCache that returns a fake snapshot with known text."""
        from unittest.mock import MagicMock
        from core.context.cache import SnapshotCache

        mock_snap = MagicMock()
        mock_snap.to_prompt_text.return_value = snapshot_text

        mock_cache = MagicMock(spec=SnapshotCache)
        mock_cache.get.return_value = mock_snap
        mock_cache.invalidate.return_value = None
        return mock_cache

    def test_no_facts_source_output_unchanged(self):
        """Without a facts source, snapshot_text() is byte-identical to pre-P8."""
        from core.agent.context import TurnContext

        cache = self._make_cache("OS: Rocky Linux 9\nKernel: 5.14")
        ctx = TurnContext(cache=cache)  # no facts= kwarg
        result = ctx.snapshot_text()
        # Must not contain any preamble prefix, must equal the snapshot text
        self.assertEqual(result, "OS: Rocky Linux 9\nKernel: 5.14")

    def test_facts_preamble_prepended_when_present(self, tmp_path=None):
        """When a facts source is supplied and file exists, preamble is prepended."""
        import tempfile
        from core.agent.context import TurnContext

        with tempfile.TemporaryDirectory() as d:
            facts_file = Path(d) / "facts.txt"
            facts_file.write_text("hostname: prod-web-01", encoding="utf-8")

            loader = FactsLoader(path=str(facts_file))
            cache = self._make_cache("OS: Rocky Linux 9")
            ctx = TurnContext(cache=cache, facts=loader)
            result = ctx.snapshot_text()

        # Preamble must appear first
        self.assertTrue(result.startswith("hostname: prod-web-01"))
        # Snapshot text must follow
        self.assertIn("OS: Rocky Linux 9", result)

    def test_absent_facts_file_output_unchanged(self):
        """Absent facts file -> output is byte-identical to no-facts path (I9)."""
        from core.agent.context import TurnContext

        loader = FactsLoader(path="/does/not/exist/facts.txt")
        cache = self._make_cache("OS: Rocky Linux 9")

        ctx_no_facts = TurnContext(cache=self._make_cache("OS: Rocky Linux 9"))
        ctx_with_loader = TurnContext(cache=cache, facts=loader)

        self.assertEqual(ctx_no_facts.snapshot_text(), ctx_with_loader.snapshot_text())

    def test_empty_facts_file_output_unchanged(self):
        """Empty facts file -> output is byte-identical to no-facts path."""
        import tempfile
        from core.agent.context import TurnContext

        with tempfile.TemporaryDirectory() as d:
            facts_file = Path(d) / "empty_facts.txt"
            facts_file.write_text("", encoding="utf-8")

            loader = FactsLoader(path=str(facts_file))
            cache1 = self._make_cache("OS: Rocky Linux 9")
            cache2 = self._make_cache("OS: Rocky Linux 9")

            ctx_no_facts = TurnContext(cache=cache1)
            ctx_with_loader = TurnContext(cache=cache2, facts=loader)

            self.assertEqual(ctx_no_facts.snapshot_text(), ctx_with_loader.snapshot_text())

    def test_facts_preamble_augments_not_replaces_snapshot(self):
        """I5: preamble augments (prepends); snapshot text is still present."""
        import tempfile
        from core.agent.context import TurnContext

        snapshot_content = "OS: Rocky Linux 9\nServices: nginx running"

        with tempfile.TemporaryDirectory() as d:
            facts_file = Path(d) / "facts.txt"
            facts_file.write_text("env: production", encoding="utf-8")

            loader = FactsLoader(path=str(facts_file))
            cache = self._make_cache(snapshot_content)
            ctx = TurnContext(cache=cache, facts=loader)
            result = ctx.snapshot_text()

        self.assertIn("env: production", result)
        self.assertIn("OS: Rocky Linux 9", result)
        self.assertIn("Services: nginx running", result)

    def test_i2_clean_preamble_passes_filter(self):
        """I2: preamble text injected into snapshot_text must clear the filter."""
        import tempfile
        from core.agent.context import TurnContext

        clean_facts = (
            "hostname: prod-db-01\n"
            "role: primary database\n"
            "datacenter: us-east-1\n"
            "owner: dba-team\n"
        )
        with tempfile.TemporaryDirectory() as d:
            facts_file = Path(d) / "facts.txt"
            facts_file.write_text(clean_facts, encoding="utf-8")

            loader = FactsLoader(path=str(facts_file))
            cache = self._make_cache("OS: Rocky Linux 9")
            ctx = TurnContext(cache=cache, facts=loader)
            result = ctx.snapshot_text()

        self.assertTrue(
            _passes_i2(result),
            f"snapshot_text() with facts contains I2-forbidden term: {result!r}",
        )

    def test_snapshot_collection_failure_with_facts_still_returns_preamble(self):
        """I9 + I5: even when snapshot collection fails, facts preamble is prepended."""
        import tempfile
        from unittest.mock import MagicMock
        from core.agent.context import TurnContext
        from core.context.cache import SnapshotCache

        # Cache that raises on get()
        mock_cache = MagicMock(spec=SnapshotCache)
        mock_cache.get.side_effect = RuntimeError("collection failed")

        with tempfile.TemporaryDirectory() as d:
            facts_file = Path(d) / "facts.txt"
            facts_file.write_text("role: critical-host", encoding="utf-8")

            loader = FactsLoader(path=str(facts_file))
            ctx = TurnContext(cache=mock_cache, facts=loader)
            result = ctx.snapshot_text()

        # Must not raise; must contain facts preamble prepended to fallback
        self.assertIn("role: critical-host", result)


if __name__ == "__main__":
    unittest.main()
