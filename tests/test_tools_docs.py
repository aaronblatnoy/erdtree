"""tests/test_tools_docs.py — Unit tests for core/tools/docs.py.

Contract assertions
-------------------
  * The docs tool implements the frozen ToolSpec interface and self-registers
    into the module-level registry singleton.
  * ToolSpec name is "docs"; the single op is "retrieve" with READ permission.
  * The tool description + op description + every ToolResult.summary produced
    by the tool are clean against the canonical I2 forbidden-term filter
    (imported from core.agent.prompt._AI_PATTERN — never re-listed here).
  * The tool degrades cleanly (empty-but-valid ToolResult, exit_code=0) when:
      - the index path is absent / unreadable
      - the rag backend (sqlite_vec) is not installed
      - the query is empty
  * When the rag backend IS available and a fixture index exists, a relevant
    query returns non-empty results and the summary matches the canonical form.
  * The summary for N chunks is exactly "Retrieved N reference passages." (I2).
  * Registering the tool a second time raises ValueError (dedup guard).

Runs with `python3 -m unittest tests.test_tools_docs` (no pytest required).
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

# Trigger self-registration.
import core.tools.docs  # noqa: F401
from core.agent.permissions import Gate, OpClass, classify, ExecContext
from core.agent.prompt import _AI_PATTERN, _FORBIDDEN_AI_TERMS
from core.tools import ToolResult, registry
from core.tools.docs import DOCS_SPEC, _execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summary_for_n(n: int) -> str:
    return f"Retrieved {n} reference passages."


# ---------------------------------------------------------------------------
# Registration tests
# ---------------------------------------------------------------------------

class TestDocsRegistration(unittest.TestCase):
    """docs tool is present in the module-level registry after import."""

    def test_registered_in_registry(self) -> None:
        self.assertIsNotNone(registry.get("docs"))

    def test_spec_name(self) -> None:
        spec = registry.get("docs")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.name, "docs")

    def test_retrieve_op_present(self) -> None:
        spec = registry.get("docs")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertIn("retrieve", spec.ops)

    def test_retrieve_permission_class_is_read(self) -> None:
        """READ — no gate friction on a retrieval (I3)."""
        spec = registry.get("docs")
        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.ops["retrieve"].permission_class, OpClass.READ)

    def test_double_register_raises(self) -> None:
        """Registry dedup guard: registering the same name twice is an error."""
        with self.assertRaises(ValueError):
            registry.register(DOCS_SPEC)


# ---------------------------------------------------------------------------
# I2 filter tests (forbidden-term scan on all user-facing strings)
# ---------------------------------------------------------------------------

class TestI2ForbiddenTerms(unittest.TestCase):
    """Every user-facing string the docs tool emits clears the I2 filter."""

    def _assert_clean(self, text: str, label: str) -> None:
        hit = _AI_PATTERN.search(text.lower())
        self.assertIsNone(
            hit,
            f"I2 violation in {label!r}: found forbidden term {hit.group()!r}"
            if hit else ""
        )

    def test_tool_description_clean(self) -> None:
        self._assert_clean(DOCS_SPEC.description, "DOCS_SPEC.description")

    def test_retrieve_op_description_clean(self) -> None:
        self._assert_clean(
            DOCS_SPEC.ops["retrieve"].description,
            "retrieve op description",
        )

    def test_retrieve_arg_descriptions_clean(self) -> None:
        for arg in DOCS_SPEC.ops["retrieve"].args:
            self._assert_clean(arg.description, f"arg '{arg.name}' description")

    def test_summary_zero_clean(self) -> None:
        self._assert_clean(_summary_for_n(0), "summary(0)")

    def test_summary_three_clean(self) -> None:
        self._assert_clean(_summary_for_n(3), "summary(3)")

    def test_forbidden_terms_not_in_description(self) -> None:
        """Belt-and-suspenders: check each forbidden term individually."""
        desc_lower = DOCS_SPEC.description.lower()
        for term in _FORBIDDEN_AI_TERMS:
            self.assertNotIn(
                term,
                desc_lower,
                f"Forbidden term {term!r} found in DOCS_SPEC.description",
            )


# ---------------------------------------------------------------------------
# Degradation tests (I9)
# ---------------------------------------------------------------------------

class TestDegradation(unittest.TestCase):
    """The tool returns empty-but-valid ToolResult under all failure modes."""

    def _empty_valid(self, result: ToolResult) -> None:
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(result.summary, "Retrieved 0 reference passages.")

    def test_degrades_when_index_path_absent(self) -> None:
        """ERDTREE_CORPUS_INDEX unset -> 0 passages, no error (I9)."""
        # The module reads _INDEX_PATH at import time; patch at the module level.
        with patch("core.tools.docs._INDEX_PATH", ""):
            result = _execute("retrieve", {"query": "noexec mount"})
        self._empty_valid(result)

    def test_degrades_when_index_file_missing(self) -> None:
        """A non-existent index path -> 0 passages, no error (I9)."""
        with patch("core.tools.docs._INDEX_PATH", "/no/such/index.db"):
            # Even with a path set, if retrieve returns [] (missing file), the
            # tool should return the canonical empty result.
            with patch("core.tools.docs._RETRIEVE_AVAILABLE", True):
                from unittest.mock import MagicMock
                with patch("core.tools.docs._retrieve_fn", return_value=[]):
                    result = _execute("retrieve", {"query": "noexec mount"})
        self._empty_valid(result)

    def test_degrades_when_retrieve_raises(self) -> None:
        """If rag.retrieve raises unexpectedly, return empty-but-valid (I9)."""
        with patch("core.tools.docs._INDEX_PATH", "/some/index.db"):
            with patch("core.tools.docs._RETRIEVE_AVAILABLE", True):
                def _boom(*a, **k):  # noqa: ANN001
                    raise RuntimeError("backend exploded")
                with patch("core.tools.docs._retrieve_fn", side_effect=_boom):
                    result = _execute("retrieve", {"query": "nosuid"})
        self._empty_valid(result)

    def test_degrades_when_backend_unavailable(self) -> None:
        """_RETRIEVE_AVAILABLE=False -> 0 passages (sqlite-vec absent) (I9)."""
        with patch("core.tools.docs._RETRIEVE_AVAILABLE", False):
            with patch("core.tools.docs._INDEX_PATH", "/some/index.db"):
                result = _execute("retrieve", {"query": "firewall"})
        self._empty_valid(result)

    def test_unknown_op_returns_error_result(self) -> None:
        """An unregistered op returns a non-OK ToolResult without raising."""
        result = _execute("nonexistent_op", {})
        self.assertEqual(result.exit_code, 1)
        self.assertIn("nonexistent_op", result.summary)


# ---------------------------------------------------------------------------
# Gate / classifier integration (the tool is READ -> Gate.ALLOW)
# ---------------------------------------------------------------------------

class TestGateClassification(unittest.TestCase):
    """synthesize_command produces a read-shaped command; classify -> ALLOW."""

    def test_docs_retrieve_classifies_as_allow(self) -> None:
        """The synthesized command for docs.retrieve must be Gate.ALLOW.

        synthesize_command() in repl.py emits a read-shaped string for docs
        (e.g. "man -k <query>"). We test the classifier directly with that
        shape so the test stays independent of repl.py edits (P6.8).
        """
        # Simulate what synthesize_command produces for docs.retrieve:
        # a pure-read shell form (man page lookup).
        read_command = "man -k noexec"
        decision = classify(read_command, ExecContext(interactive=True))
        self.assertEqual(
            decision.gate,
            Gate.ALLOW,
            f"Expected ALLOW for '{read_command}', got {decision.gate}",
        )


# ---------------------------------------------------------------------------
# Functional tests (with live fixture index, if available)
# ---------------------------------------------------------------------------

class TestDocsWithFixture(unittest.TestCase):
    """Run the docs tool against the fixture index when sqlite-vec is available."""

    @classmethod
    def setUpClass(cls) -> None:
        """Locate the fixture index; skip class if not buildable."""
        import pathlib
        fixture_index = (
            pathlib.Path(__file__).resolve().parents[1]
            / "rag" / "fixtures" / "mini_index.db"
        )
        cls.fixture_index = str(fixture_index)
        # Try to ensure the fixture is built.
        cls.skip_reason: str = ""
        try:
            if not fixture_index.exists():
                from rag.fixtures.build_fixture_index import build
                build()
        except Exception as exc:  # noqa: BLE001
            cls.skip_reason = f"fixture unavailable: {exc}"

    def _skip_if_unavailable(self) -> None:
        if self.skip_reason:
            self.skipTest(self.skip_reason)
        if not core.tools.docs._RETRIEVE_AVAILABLE:
            self.skipTest("rag backend (sqlite-vec) not installed")

    def test_relevant_query_returns_chunks(self) -> None:
        self._skip_if_unavailable()
        with patch("core.tools.docs._RETRIEVE_AVAILABLE", True):
            with patch("core.tools.docs._INDEX_PATH", self.fixture_index):
                with patch("core.tools.docs._retrieve_fn", core.tools.docs._retrieve_fn):
                    result = _execute(
                        "retrieve",
                        {"query": "what does the noexec mount flag do", "k": 3},
                    )
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.stdout, "expected non-empty stdout for relevant query")
        self.assertNotEqual(result.summary, "Retrieved 0 reference passages.")

    def test_summary_canonical_form(self) -> None:
        """Summary is exactly 'Retrieved N reference passages.' (I2)."""
        self._skip_if_unavailable()
        with patch("core.tools.docs._RETRIEVE_AVAILABLE", True):
            with patch("core.tools.docs._INDEX_PATH", self.fixture_index):
                with patch("core.tools.docs._retrieve_fn", core.tools.docs._retrieve_fn):
                    result = _execute(
                        "retrieve",
                        {"query": "noexec mount flag", "k": 2},
                    )
        # Summary must match "Retrieved N reference passages." exactly.
        import re
        self.assertRegex(
            result.summary,
            r"^Retrieved \d+ reference passages\.$",
            "summary must match canonical form",
        )
        # And must clear the I2 filter.
        self.assertIsNone(_AI_PATTERN.search(result.summary.lower()))

    def test_i2_clean_on_returned_stdout(self) -> None:
        """Corpus passages do not contain AI/LLM/model language (I2)."""
        self._skip_if_unavailable()
        with patch("core.tools.docs._RETRIEVE_AVAILABLE", True):
            with patch("core.tools.docs._INDEX_PATH", self.fixture_index):
                with patch("core.tools.docs._retrieve_fn", core.tools.docs._retrieve_fn):
                    result = _execute(
                        "retrieve",
                        {"query": "firewall panic lockout", "k": 3},
                    )
        if result.stdout:
            self.assertIsNone(_AI_PATTERN.search(result.stdout.lower()))


# ---------------------------------------------------------------------------
# index_path reuse property (SC-P7.3) via the mock path
# ---------------------------------------------------------------------------

class TestIndexPathIsParameter(unittest.TestCase):
    """The retrieve function is called with the configured index_path, not a global."""

    def test_retrieve_called_with_index_path(self) -> None:
        """_execute passes _INDEX_PATH as the index_path argument to _retrieve_fn."""
        captured: list[tuple] = []

        def _spy(query, index_path, k, max_chars):  # noqa: ANN001
            captured.append((query, index_path, k, max_chars))
            return []

        with patch("core.tools.docs._RETRIEVE_AVAILABLE", True):
            with patch("core.tools.docs._INDEX_PATH", "/custom/path/corpus.db"):
                with patch("core.tools.docs._retrieve_fn", _spy):
                    _execute("retrieve", {"query": "noexec", "k": 2})

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0][1], "/custom/path/corpus.db")


if __name__ == "__main__":
    unittest.main()
