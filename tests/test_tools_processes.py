"""tests/test_tools_processes.py — Unit tests for core/tools/processes.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the dev host without ps/kill/renice present or behaving identically
to Rocky Linux 9.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/tree/top/info are READ; signal/renice are WRITE.
  * Each operation produces a well-formed ToolResult.
  * READ ops get Gate.ALLOW from permissions.classify().
  * WRITE ops get Gate.CONFIRM (not DESTRUCTIVE) for a normal kill <pid>.
  * kill -1 (signal_num=-1) synthesized as "kill -1 <pid>" classifies DESTRUCTIVE.
  * Priority clamping in renice ([-20, 19]).
  * SELinux AVC hint surfaced when stderr contains AVC language.
  * Unknown op returns a non-crashing ToolResult (I9 degradation).
  * I2 filter: every op description and every ToolResult summary is clear of
    forbidden AI/LLM/model/agent terms (imported from core.agent.prompt).

Mocking strategy
----------------
  Patch ``core.tools.processes.run_subprocess`` to return controlled fixtures.
  No real process is ever launched.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

# Trigger self-registration into the module-level registry.
import core.tools.processes  # noqa: F401
from core.agent.permissions import ExecContext, Gate, OpClass, classify
from core.agent.prompt import _FORBIDDEN_AI_TERMS
from core.tools import ToolResult, registry
from core.tools.processes import PROCESSES_SPEC, _execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.processes.run_subprocess."""
    return patch("core.tools.processes.run_subprocess", return_value=return_value)


def _patch_fn(side_effect=None, return_value=None):
    """Patch with a MagicMock for call inspection."""
    m = MagicMock()
    if side_effect is not None:
        m.side_effect = side_effect
    else:
        m.return_value = return_value
    return patch("core.tools.processes.run_subprocess", m), m


# ---------------------------------------------------------------------------
# I2 helpers
# ---------------------------------------------------------------------------

import re as _re

_AI_RE = _re.compile(
    r"\b(" + "|".join(_re.escape(t) for t in _FORBIDDEN_AI_TERMS) + r")\b",
    _re.IGNORECASE,
)


def _assert_i2_clean(text: str, label: str = "") -> None:
    """Assert no I2-forbidden term appears in text."""
    m = _AI_RE.search(text)
    if m:
        raise AssertionError(
            f"I2 violation in {label!r}: found forbidden term {m.group()!r} "
            f"in: {text!r}"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration(unittest.TestCase):
    def test_processes_registered_in_registry(self):
        self.assertIsNotNone(registry.get("processes"))

    def test_spec_name(self):
        spec = registry.get("processes")
        self.assertEqual(spec.name, "processes")

    def test_all_expected_ops_present(self):
        spec = registry.get("processes")
        expected = {"list", "tree", "top", "info", "signal", "renice"}
        self.assertEqual(set(spec.ops.keys()), expected)


# ---------------------------------------------------------------------------
# Permission classes (declared in ToolSpec)
# ---------------------------------------------------------------------------

class TestPermissionClasses(unittest.TestCase):
    def test_read_ops_declared_read(self):
        for op in ("list", "tree", "top", "info"):
            with self.subTest(op=op):
                cls = registry.permission_class_for("processes", op)
                self.assertIs(cls, OpClass.READ, f"Expected READ for '{op}'")

    def test_write_ops_declared_write(self):
        for op in ("signal", "renice"):
            with self.subTest(op=op):
                cls = registry.permission_class_for("processes", op)
                self.assertIs(cls, OpClass.WRITE, f"Expected WRITE for '{op}'")


# ---------------------------------------------------------------------------
# Permission gate integration (permissions.classify on synthesized commands)
# ---------------------------------------------------------------------------

class TestPermissionGateIntegration(unittest.TestCase):
    """Verify synthesized command strings produce the correct gate."""

    def test_list_classifies_read(self):
        d = classify("ps aux")
        self.assertIs(d.gate, Gate.ALLOW)
        self.assertTrue(d.auto_ok)

    def test_tree_classifies_read(self):
        d = classify("ps -ejH")
        self.assertIs(d.gate, Gate.ALLOW)
        self.assertTrue(d.auto_ok)

    def test_top_classifies_read(self):
        d = classify("ps aux --sort=-%cpu")
        self.assertIs(d.gate, Gate.ALLOW)
        self.assertTrue(d.auto_ok)

    def test_info_classifies_read(self):
        d = classify("ps -p 1234 -o pid,ppid,user,stat,pcpu,pmem,comm,args")
        self.assertIs(d.gate, Gate.ALLOW)
        self.assertTrue(d.auto_ok)

    def test_signal_plain_kill_classifies_write(self):
        # A plain "kill <pid>" is a WRITE (CONFIRM gate), not DESTRUCTIVE.
        d = classify("kill 1234")
        self.assertIn(d.gate, (Gate.CONFIRM,))
        self.assertFalse(d.auto_ok)

    def test_signal_kill_minus1_classifies_destructive(self):
        # "kill -1 <pid>" sends to ALL processes — the classifier sees this as
        # DESTRUCTIVE.  The REPL's synthesize_command() must emit this form.
        d = classify("kill -1 1234")
        self.assertIs(d.gate, Gate.CONFIRM_TYPED)
        self.assertFalse(d.auto_ok)

    def test_signal_kill_minus1_refused_non_interactive(self):
        ctx = ExecContext(interactive=False)
        d = classify("kill -1 1234", ctx)
        self.assertIs(d.gate, Gate.REFUSE)

    def test_renice_classifies_write(self):
        d = classify("renice -5 -p 1234")
        self.assertIn(d.gate, (Gate.CONFIRM,))
        self.assertFalse(d.auto_ok)


# ---------------------------------------------------------------------------
# list operation
# ---------------------------------------------------------------------------

class TestList(unittest.TestCase):
    def test_success_summary(self):
        stdout = "USER PID ...\nroot 1 ...\nnginx 123 ...\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("list", {})
        self.assertTrue(result.ok)
        self.assertIn("process", result.summary.lower())

    def test_failure(self):
        with _patch(_fail(exit_code=1)):
            result = _execute("list", {})
        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, 1)

    def test_result_structure(self):
        with _patch(_ok(stdout="ps output")):
            result = _execute("list", {})
        self.assertIsInstance(result, ToolResult)
        self.assertIsInstance(result.stdout, str)
        self.assertIsInstance(result.stderr, str)
        self.assertIsInstance(result.summary, str)
        self.assertGreater(len(result.summary), 0)

    def test_i2_clean_summary(self):
        with _patch(_ok(stdout="ps output")):
            result = _execute("list", {})
        _assert_i2_clean(result.summary, "list summary")


# ---------------------------------------------------------------------------
# tree operation
# ---------------------------------------------------------------------------

class TestTree(unittest.TestCase):
    def test_success_summary(self):
        with _patch(_ok(stdout="PID PPID ...\n1 0 ...\n2 1 ...\n")):
            result = _execute("tree", {})
        self.assertTrue(result.ok)
        self.assertIn("tree", result.summary.lower())

    def test_failure(self):
        with _patch(_fail(exit_code=1)):
            result = _execute("tree", {})
        self.assertFalse(result.ok)

    def test_i2_clean_summary(self):
        with _patch(_ok(stdout="output")):
            result = _execute("tree", {})
        _assert_i2_clean(result.summary, "tree summary")


# ---------------------------------------------------------------------------
# top operation
# ---------------------------------------------------------------------------

class TestTop(unittest.TestCase):
    def test_success_summary(self):
        with _patch(_ok(stdout="USER PID %CPU ...\nroot 1 99.9 ...\n")):
            result = _execute("top", {})
        self.assertTrue(result.ok)
        self.assertIn("process", result.summary.lower())

    def test_failure(self):
        with _patch(_fail(exit_code=1)):
            result = _execute("top", {})
        self.assertFalse(result.ok)

    def test_i2_clean_summary(self):
        with _patch(_ok(stdout="output")):
            result = _execute("top", {})
        _assert_i2_clean(result.summary, "top summary")


# ---------------------------------------------------------------------------
# info operation
# ---------------------------------------------------------------------------

class TestInfo(unittest.TestCase):
    def test_success_summary(self):
        with _patch(_ok(stdout="PID PPID USER ...\n1234 1 nginx ...\n")):
            result = _execute("info", {"pid": 1234})
        self.assertTrue(result.ok)
        self.assertIn("1234", result.summary)

    def test_not_found(self):
        with _patch(_fail(exit_code=1, stderr="no process")):
            result = _execute("info", {"pid": 99999})
        self.assertFalse(result.ok)
        self.assertIn("99999", result.summary)

    def test_pid_in_command(self):
        mock_fn = MagicMock(return_value=_ok(stdout="PID ...\n5678 ...\n"))
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("info", {"pid": 5678})
        call_args = mock_fn.call_args[0][0]
        self.assertIn("5678", call_args)

    def test_i2_clean_summary(self):
        with _patch(_ok(stdout="output")):
            result = _execute("info", {"pid": 1})
        _assert_i2_clean(result.summary, "info summary")


# ---------------------------------------------------------------------------
# signal operation
# ---------------------------------------------------------------------------

class TestSignal(unittest.TestCase):
    def test_default_sigterm_success(self):
        with _patch(_ok()):
            result = _execute("signal", {"pid": 1234})
        self.assertTrue(result.ok)
        self.assertIn("1234", result.summary)

    def test_sigkill_success(self):
        with _patch(_ok()):
            result = _execute("signal", {"pid": 1234, "signal_num": 9})
        self.assertTrue(result.ok)
        # Summary should mention the signal or pid.
        self.assertIn("1234", result.summary)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="no such process")):
            result = _execute("signal", {"pid": 99999})
        self.assertFalse(result.ok)
        self.assertIn("99999", result.summary)

    def test_command_vector_default(self):
        """Default signal: subprocess sees ['kill', '<pid>']."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("signal", {"pid": 42})
        argv = mock_fn.call_args[0][0]
        self.assertEqual(argv[0], "kill")
        self.assertIn("42", argv)

    def test_command_vector_explicit_signal(self):
        """Explicit signal_num: subprocess sees ['kill', '-9', '<pid>']."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("signal", {"pid": 42, "signal_num": 9})
        argv = mock_fn.call_args[0][0]
        self.assertIn("-9", argv)
        self.assertIn("42", argv)

    def test_signal_minus1_command_vector(self):
        """signal_num=-1: subprocess sees ['kill', '-1', '<pid>'].

        The REPL must synthesize "kill -1 <pid>" so the classifier sees the
        -1 and escalates to DESTRUCTIVE.  This test verifies the tool shells
        out the matching argv, so the synthesized string is faithful.
        """
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("signal", {"pid": 1, "signal_num": -1})
        argv = mock_fn.call_args[0][0]
        self.assertIn("-1", argv)

    def test_i2_clean_summary(self):
        with _patch(_ok()):
            result = _execute("signal", {"pid": 1})
        _assert_i2_clean(result.summary, "signal summary")


# ---------------------------------------------------------------------------
# renice operation
# ---------------------------------------------------------------------------

class TestRenice(unittest.TestCase):
    def test_success(self):
        with _patch(_ok(stdout="1234: old priority 0, new priority -5")):
            result = _execute("renice", {"pid": 1234, "priority": -5})
        self.assertTrue(result.ok)
        self.assertIn("1234", result.summary)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="no such process")):
            result = _execute("renice", {"pid": 99999, "priority": 5})
        self.assertFalse(result.ok)
        self.assertIn("99999", result.summary)

    def test_priority_clamped_high(self):
        """Priority above 19 is clamped to 19."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("renice", {"pid": 1, "priority": 99})
        argv = mock_fn.call_args[0][0]
        self.assertIn("19", argv)
        self.assertNotIn("99", argv)

    def test_priority_clamped_low(self):
        """Priority below -20 is clamped to -20."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("renice", {"pid": 1, "priority": -999})
        argv = mock_fn.call_args[0][0]
        self.assertIn("-20", argv)

    def test_priority_in_range_unchanged(self):
        """A valid priority in [-20, 19] is passed through unchanged."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("renice", {"pid": 1, "priority": -10})
        argv = mock_fn.call_args[0][0]
        self.assertIn("-10", argv)

    def test_command_vector_shape(self):
        """renice argv must be ['renice', '<priority>', '-p', '<pid>']."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.processes.run_subprocess", mock_fn):
            _execute("renice", {"pid": 567, "priority": 5})
        argv = mock_fn.call_args[0][0]
        self.assertEqual(argv[0], "renice")
        self.assertIn("-p", argv)
        self.assertIn("567", argv)
        self.assertIn("5", argv)

    def test_i2_clean_summary(self):
        with _patch(_ok()):
            result = _execute("renice", {"pid": 1, "priority": 0})
        _assert_i2_clean(result.summary, "renice summary")


# ---------------------------------------------------------------------------
# Unknown operation (I9: graceful degradation)
# ---------------------------------------------------------------------------

class TestUnknownOp(unittest.TestCase):
    def test_unknown_op_returns_tool_result(self):
        """An unknown op must NOT raise; it must return a valid ToolResult."""
        result = _execute("nonexistent_op", {})
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("nonexistent_op", result.summary)

    def test_unknown_op_summary_i2_clean(self):
        result = _execute("no_such_op", {})
        _assert_i2_clean(result.summary, "unknown op summary")


# ---------------------------------------------------------------------------
# SELinux hint
# ---------------------------------------------------------------------------

class TestSELinuxHint(unittest.TestCase):
    def test_avc_in_stderr_surfaces_hint(self):
        avc_stderr = (
            "AVC avc: denied { signal } for pid=1234 "
            "comm=\"kill\" scontext=unconfined_u:unconfined_r:unconfined_t"
        )
        with _patch(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute("signal", {"pid": 1234})
        self.assertTrue(
            "SELinux" in result.summary or "ausearch" in result.summary,
            f"Expected SELinux hint in summary: {result.summary!r}",
        )

    def test_clean_stderr_no_hint(self):
        with _patch(_fail(exit_code=1, stderr="no such process")):
            result = _execute("signal", {"pid": 99999})
        self.assertNotIn("ausearch", result.summary)


# ---------------------------------------------------------------------------
# I2 filter: ToolSpec descriptions
# ---------------------------------------------------------------------------

class TestI2Filter(unittest.TestCase):
    """Every description in the ToolSpec must be clean of I2-forbidden terms."""

    def test_tool_description_i2_clean(self):
        _assert_i2_clean(PROCESSES_SPEC.description, "PROCESSES_SPEC.description")

    def test_all_op_descriptions_i2_clean(self):
        for op_name, op_spec in PROCESSES_SPEC.ops.items():
            with self.subTest(op=op_name):
                _assert_i2_clean(op_spec.description, f"op '{op_name}' description")

    def test_all_arg_descriptions_i2_clean(self):
        for op_name, op_spec in PROCESSES_SPEC.ops.items():
            for arg in op_spec.args:
                with self.subTest(op=op_name, arg=arg.name):
                    _assert_i2_clean(arg.description, f"op '{op_name}' arg '{arg.name}' description")

    def test_all_summaries_i2_clean(self):
        """Run every op and check the summary is I2-clean."""
        cases = [
            ("list", {}),
            ("tree", {}),
            ("top", {}),
            ("info", {"pid": 1}),
            ("signal", {"pid": 1}),
            ("signal", {"pid": 1, "signal_num": 9}),
            ("renice", {"pid": 1, "priority": 5}),
        ]
        for op, args in cases:
            with self.subTest(op=op, args=args):
                with _patch(_ok()):
                    result = _execute(op, args)
                _assert_i2_clean(result.summary, f"op '{op}' success summary")

    def test_failure_summaries_i2_clean(self):
        cases = [
            ("list", {}),
            ("signal", {"pid": 1}),
            ("renice", {"pid": 1, "priority": 5}),
        ]
        for op, args in cases:
            with self.subTest(op=op):
                with _patch(_fail(exit_code=1)):
                    result = _execute(op, args)
                _assert_i2_clean(result.summary, f"op '{op}' failure summary")


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure(unittest.TestCase):
    _CASES = [
        ("list", {}),
        ("tree", {}),
        ("top", {}),
        ("info", {"pid": 1}),
        ("signal", {"pid": 1}),
        ("renice", {"pid": 1, "priority": 5}),
    ]

    def test_all_ops_return_tool_result(self):
        for op, args in self._CASES:
            with self.subTest(op=op):
                with _patch(_ok(stdout=f"{op} output")):
                    result = _execute(op, args)
                self.assertIsInstance(result, ToolResult)
                self.assertIsNotNone(result.exit_code)
                self.assertIsInstance(result.stdout, str)
                self.assertIsInstance(result.stderr, str)
                self.assertIsInstance(result.summary, str)
                self.assertGreater(len(result.summary), 0)

    def test_as_dict_has_required_keys(self):
        for op, args in self._CASES:
            with self.subTest(op=op):
                with _patch(_ok()):
                    result = _execute(op, args)
                d = result.as_dict()
                self.assertEqual(
                    set(d.keys()), {"exit_code", "stdout", "stderr", "summary"}
                )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch(unittest.TestCase):
    def test_dispatch_list(self):
        with _patch(_ok(stdout="ps output")):
            result = registry.dispatch("processes", "list", {})
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.exit_code, 0)

    def test_dispatch_info(self):
        with _patch(_ok(stdout="PID ...\n42 ...\n")):
            result = registry.dispatch("processes", "info", {"pid": 42})
        self.assertTrue(result.ok)

    def test_dispatch_signal(self):
        with _patch(_ok()):
            result = registry.dispatch("processes", "signal", {"pid": 42})
        self.assertTrue(result.ok)

    def test_dispatch_renice(self):
        with _patch(_ok()):
            result = registry.dispatch("processes", "renice", {"pid": 42, "priority": 5})
        self.assertTrue(result.ok)

    def test_dispatch_info_missing_pid_raises(self):
        with self.assertRaises(TypeError):
            registry.dispatch("processes", "info", {})

    def test_dispatch_renice_missing_priority_raises(self):
        with self.assertRaises(TypeError):
            registry.dispatch("processes", "renice", {"pid": 1})

    def test_dispatch_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            registry.dispatch("processes", "nonexistent", {"pid": 1})


if __name__ == "__main__":
    unittest.main()
