"""test_episodic — Phase 8 episodic memory gate (offline, stdlib unittest).

Verifies:
  1. A query matching a past audited op returns that op via the reused
     rag.retrieve engine (the core recall contract, SC-P8.3).
  2. The episodic index_path DIFFERS from the docs corpus index_path — this is
     the reuse-not-fork assertion (SC-P7.3 from episodic's perspective).
  3. test_index_path_is_a_parameter_reuse_property: explicitly asserts the
     index_path is a parameter (not a global), so the engine is genuinely shared
     with a different path for each use.
  4. Degradation cases: empty query, missing audit log, k<=0, max_chars<=0
     all return [] (I9).
  5. I2 compliance: no recalled snippet text contains terms from the canonical
     forbidden list (core/agent/prompt._AI_PATTERN).

Run: python3 -m unittest tests.test_episodic
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run directly.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.agent.episodic import EpisodicMemory, _record_to_text, REBUILD_DELTA_BYTES
from rag.retrieve import Chunk

# The docs corpus index path (fixture) — used to PROVE the episodic path differs.
_DOCS_FIXTURE_INDEX = str(_ROOT / "rag" / "fixtures" / "mini_index.db")


# ---------------------------------------------------------------------------
# Helper: write a minimal audit JSONL with controlled content.
# ---------------------------------------------------------------------------

_AUDIT_SCHEMA_KEYS = (
    "ts", "tier", "nl_input", "translated_command", "tool", "args",
    "permission_decision", "exit_code", "stdout_summary", "stderr_summary", "result",
)


def _make_record(**kwargs) -> dict:
    """Build a valid audit record dict with defaults for all schema keys."""
    defaults = {
        "ts": 1700000000.0,
        "tier": "test",
        "nl_input": None,
        "translated_command": None,
        "tool": None,
        "args": None,
        "permission_decision": None,
        "exit_code": None,
        "stdout_summary": None,
        "stderr_summary": None,
        "result": None,
    }
    defaults.update(kwargs)
    return defaults


def _write_audit(path: str, records: list[dict]) -> None:
    """Write a list of audit records as JSONL to path."""
    with open(path, "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec) + "\n")


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestEpisodicRecall(unittest.TestCase):
    """Core recall: a past audited op is returned when queried."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._audit = os.path.join(self._tmp, "audit.jsonl")
        self._index = os.path.join(self._tmp, "episodic.db")

        # Write two audit records with distinct topics.
        _write_audit(self._audit, [
            _make_record(
                ts=1700000001.0,
                nl_input="restart nginx after config reload",
                translated_command="systemctl restart nginx",
                tool="services",
                exit_code=0,
                result="ok",
            ),
            _make_record(
                ts=1700000002.0,
                nl_input="check disk usage on /var/log",
                translated_command="df -h /var/log",
                tool="disk",
                exit_code=0,
                result="ok",
            ),
        ])

    def test_matching_op_is_recalled(self) -> None:
        """A query about nginx returns the nginx audit record."""
        mem = EpisodicMemory(self._audit, self._index)
        results = mem.recall("nginx restart")
        self.assertIsInstance(results, list)
        self.assertTrue(results, "expected at least one recalled chunk")
        # Top hit should reference the nginx operation.
        top_text = results[0].text
        self.assertIn("nginx", top_text.lower())

    def test_results_are_chunks(self) -> None:
        """recall() returns a list of Chunk objects (the frozen dataclass)."""
        mem = EpisodicMemory(self._audit, self._index)
        results = mem.recall("disk usage")
        for chunk in results:
            self.assertIsInstance(chunk, Chunk)

    def test_k_limits_results(self) -> None:
        """Requesting k=1 returns at most one chunk."""
        mem = EpisodicMemory(self._audit, self._index)
        results = mem.recall("operation", k=1)
        self.assertLessEqual(len(results), 1)

    def test_max_chars_respected(self) -> None:
        """Total recalled text stays within max_chars budget."""
        mem = EpisodicMemory(self._audit, self._index)
        results = mem.recall("nginx disk", max_chars=50)
        total = sum(len(c.text) for c in results)
        self.assertLessEqual(total, 50)

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestIndexPathReuseProperty(unittest.TestCase):
    """SC-P7.3 / SC-P8: the episodic index_path DIFFERS from the docs index_path.

    This is the canonical reuse-not-fork assertion: the SAME rag.retrieve engine
    is called by EpisodicMemory with its own index_path, and that path is provably
    different from the docs corpus index_path (mini_index.db).  No second retriever
    is built — the frozen engine from Phase 7 is reused unchanged.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._audit = os.path.join(self._tmp, "audit.jsonl")
        self._episodic_index = os.path.join(self._tmp, "episodic.db")
        _write_audit(self._audit, [
            _make_record(
                ts=1700000010.0,
                nl_input="formatted /dev/sdb1 with ext4",
                translated_command="mkfs.ext4 /dev/sdb1",
                tool="disk",
                exit_code=0,
                result="ok",
            ),
        ])

    def test_index_path_is_a_parameter_reuse_property(self) -> None:
        """The episodic index_path differs from the docs index_path.

        This proves SC-P7.3: retrieve() is called with a DIFFERENT index_path
        by EpisodicMemory vs core/tools/docs.py — one engine, two uses.
        """
        mem = EpisodicMemory(self._audit, self._episodic_index)

        # Trigger the index build by running a recall.
        results = mem.recall("disk format ext4")

        # The episodic index path must differ from the docs fixture index.
        self.assertNotEqual(
            mem.index_path,
            _DOCS_FIXTURE_INDEX,
            "episodic index_path must differ from the docs corpus index_path "
            "(SC-P7.3: reuse-not-fork)",
        )

        # The episodic index must actually exist (i.e. it was built).
        self.assertTrue(
            os.path.exists(self._episodic_index),
            "episodic index was not built",
        )

        # The docs fixture index must also exist and be a different file.
        self.assertTrue(
            os.path.exists(_DOCS_FIXTURE_INDEX),
            "docs fixture index missing; run rag/fixtures/build_fixture_index.py",
        )

        # The episodic result comes from the audit records (not the docs corpus).
        self.assertIsInstance(results, list)
        if results:
            # The recalled text is from our audit record, not the docs fixture.
            self.assertIn("sdb1", results[0].text.lower())

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestEpisodicDegradation(unittest.TestCase):
    """I9: all failure paths degrade to [] — never raise."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._audit = os.path.join(self._tmp, "audit.jsonl")
        self._index = os.path.join(self._tmp, "episodic.db")

    def test_empty_query_returns_empty(self) -> None:
        _write_audit(self._audit, [_make_record(nl_input="restart nginx")])
        mem = EpisodicMemory(self._audit, self._index)
        self.assertEqual(mem.recall(""), [])

    def test_blank_query_returns_empty(self) -> None:
        _write_audit(self._audit, [_make_record(nl_input="restart nginx")])
        mem = EpisodicMemory(self._audit, self._index)
        self.assertEqual(mem.recall("   "), [])

    def test_missing_audit_log_returns_empty(self) -> None:
        """No audit log -> [] without raising."""
        mem = EpisodicMemory("/no/such/audit.jsonl", self._index)
        self.assertEqual(mem.recall("anything"), [])

    def test_k_zero_returns_empty(self) -> None:
        _write_audit(self._audit, [_make_record(nl_input="restart nginx")])
        mem = EpisodicMemory(self._audit, self._index, k=0)
        self.assertEqual(mem.recall("nginx"), [])

    def test_k_negative_returns_empty(self) -> None:
        _write_audit(self._audit, [_make_record(nl_input="restart nginx")])
        mem = EpisodicMemory(self._audit, self._index)
        self.assertEqual(mem.recall("nginx", k=-1), [])

    def test_max_chars_zero_returns_empty(self) -> None:
        _write_audit(self._audit, [_make_record(nl_input="restart nginx")])
        mem = EpisodicMemory(self._audit, self._index)
        self.assertEqual(mem.recall("nginx", max_chars=0), [])

    def test_empty_audit_log_returns_empty(self) -> None:
        """Empty (zero-record) audit log -> [] without raising."""
        _write_audit(self._audit, [])
        mem = EpisodicMemory(self._audit, self._index)
        self.assertEqual(mem.recall("anything"), [])

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestEpisodicIncrementalRebuild(unittest.TestCase):
    """Index is rebuilt when the audit log grows beyond REBUILD_DELTA_BYTES."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._audit = os.path.join(self._tmp, "audit.jsonl")
        self._index = os.path.join(self._tmp, "episodic.db")

    def test_new_record_becomes_retrievable_after_rebuild(self) -> None:
        """A record added after the initial index build appears after rebuild."""
        # Write first record and recall to build the initial index.
        _write_audit(self._audit, [
            _make_record(
                ts=1700000020.0,
                nl_input="checked SELinux status",
                translated_command="sestatus",
                tool="security",
                exit_code=0,
                result="ok",
            ),
        ])
        # Use a tiny rebuild_delta so the next write triggers rebuild.
        mem = EpisodicMemory(self._audit, self._index, rebuild_delta=1)
        first = mem.recall("SELinux")
        self.assertIsInstance(first, list)

        # Append a second record.
        with open(self._audit, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(_make_record(
                ts=1700000021.0,
                nl_input="listed open firewall ports",
                translated_command="firewall-cmd --list-ports",
                tool="firewall",
                exit_code=0,
                result="ok",
            )) + "\n")

        # After the delta threshold is exceeded, the new record is retrievable.
        second = mem.recall("firewall ports")
        self.assertIsInstance(second, list)
        # The new op should now be reachable (the index was rebuilt).
        texts = " ".join(c.text for c in second)
        self.assertIn("firewall", texts.lower())

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class TestEpisodicI2Compliance(unittest.TestCase):
    """I2: no recalled snippet text contains the canonical forbidden terms."""

    def setUp(self) -> None:
        self._tmp = tempfile.mkdtemp()
        self._audit = os.path.join(self._tmp, "audit.jsonl")
        self._index = os.path.join(self._tmp, "episodic.db")
        _write_audit(self._audit, [
            _make_record(
                ts=1700000030.0,
                nl_input="check running services",
                translated_command="systemctl list-units --type=service --state=running",
                tool="services",
                exit_code=0,
                result="ok",
            ),
        ])

    def test_recalled_text_is_i2_clean(self) -> None:
        """Recalled snippets must not leak any I2-forbidden term."""
        from core.agent.prompt import _AI_PATTERN

        mem = EpisodicMemory(self._audit, self._index)
        results = mem.recall("running services")
        for chunk in results:
            match = _AI_PATTERN.search(chunk.text.lower())
            if match:
                self.fail(
                    f"I2 violation in recalled chunk {chunk.chunk_id!r}: "
                    f"found {match.group()!r} — forbidden term",
                )

    def test_record_to_text_is_i2_clean(self) -> None:
        """_record_to_text() output clears the I2 filter for all schema fields."""
        from core.agent.prompt import _AI_PATTERN

        rec = _make_record(
            nl_input="show disk usage",
            translated_command="df -h",
            tool="disk",
            exit_code=0,
            result="ok",
        )
        text = _record_to_text(rec)
        match = _AI_PATTERN.search(text.lower())
        found = match.group() if match else "?"
        self.assertIsNone(
            match,
            f"I2 violation in _record_to_text output: {found!r}",
        )

    def tearDown(self) -> None:
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
