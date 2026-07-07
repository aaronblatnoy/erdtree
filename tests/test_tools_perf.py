"""tests/test_tools_perf.py — Unit tests for core/tools/perf.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without perf present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: stat/top are READ; record is WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful I2-clean summary.
  * Failed exit (nonzero) -> ok=False, failure summary.
  * Command vector correctness for each op.
  * SELinux AVC hint surfaces when stderr contains AVC language.
  * execute() NEVER raises, including unknown ops and exit 127.
  * I2: no AI/LLM/model/agent language in any summary.
  * DEFERRED-TO-MOSSAD: live execution tests.

Mocking strategy
----------------
  We patch ``core.tools.perf.run_subprocess`` (the function in the perf
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import core.tools.perf  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.perf import PERF_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.perf.run_subprocess."""
    return patch("core.tools.perf.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_perf_registered_in_module_registry(self) -> None:
        assert registry.get("perf") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("perf")
        assert spec is not None
        assert spec.name == "perf"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("perf")
        assert spec is not None
        expected = {"stat", "top", "record"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["stat", "top"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("perf", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["record"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("perf", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vector tests
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_stat_basic_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stderr="perf stat output"))
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("stat", {"command": "sleep 1"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "perf"
        assert argv[1] == "stat"
        assert "sleep" in argv
        assert "1" in argv

    def test_stat_with_events(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("stat", {"command": "ls", "events": "cycles,instructions"})
        argv = mock_fn.call_args[0][0]
        assert "-e" in argv
        e_idx = argv.index("-e")
        assert argv[e_idx + 1] == "cycles,instructions"

    def test_stat_with_repeats(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("stat", {"command": "ls", "repeats": 3})
        argv = mock_fn.call_args[0][0]
        assert "-r" in argv
        r_idx = argv.index("-r")
        assert argv[r_idx + 1] == "3"

    def test_top_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="# Overhead"))
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("top", {"duration": 5})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "perf"
        assert argv[1] == "top"
        assert "--stdio" in argv
        assert "-d" in argv
        d_idx = argv.index("-d")
        assert argv[d_idx + 1] == "5"

    def test_top_with_sort(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="# Overhead"))
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("top", {"duration": 10, "sort": "cpu"})
        argv = mock_fn.call_args[0][0]
        assert "--sort" in argv
        s_idx = argv.index("--sort")
        assert argv[s_idx + 1] == "cpu"

    def test_record_basic_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stderr="perf record: Captured"))
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("record", {"command": "ls -la", "output": "perf.data"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "perf"
        assert argv[1] == "record"
        assert "-o" in argv
        o_idx = argv.index("-o")
        assert argv[o_idx + 1] == "perf.data"
        assert "ls" in argv

    def test_record_with_pid(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("record", {"pid": 1234, "output": "out.data", "duration": 10})
        argv = mock_fn.call_args[0][0]
        assert "-p" in argv
        p_idx = argv.index("-p")
        assert argv[p_idx + 1] == "1234"

    def test_record_with_events(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("record", {"command": "sleep 1", "events": "cache-misses", "output": "perf.data"})
        argv = mock_fn.call_args[0][0]
        assert "-e" in argv
        e_idx = argv.index("-e")
        assert argv[e_idx + 1] == "cache-misses"

    def test_record_custom_output_path(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.perf.run_subprocess", mock_fn):
            _execute("record", {"command": "make", "output": "/tmp/build.perf.data"})
        argv = mock_fn.call_args[0][0]
        o_idx = argv.index("-o")
        assert argv[o_idx + 1] == "/tmp/build.perf.data"


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_stat_success(self) -> None:
        with _patch_run(_ok_result(stderr="perf stat output\n 1,000 cycles")):
            result = _execute("stat", {"command": "sleep 1"})
        assert result.ok
        assert result.exit_code == 0
        assert "completed" in result.summary.lower()

    def test_stat_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="perf_event_open failed")):
            result = _execute("stat", {"command": "sleep 1"})
        assert not result.ok
        assert result.exit_code == 1
        assert "sleep 1" in result.summary
        assert "exit 1" in result.summary

    def test_stat_missing_binary(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="perf: command not found")):
            result = _execute("stat", {"command": "ls"})
        assert not result.ok
        assert result.exit_code == 127

    def test_top_success(self) -> None:
        with _patch_run(_ok_result(stdout="# Overhead  Command")):
            result = _execute("top", {"duration": 5})
        assert result.ok
        assert "perf top" in result.summary.lower() or "profiling" in result.summary.lower()

    def test_top_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Operation not permitted")):
            result = _execute("top", {"duration": 5})
        assert not result.ok
        assert "exit 1" in result.summary

    def test_record_success(self) -> None:
        with _patch_run(_ok_result(stderr="[ perf record: Captured and wrote 0.024 MB perf.data ]")):
            result = _execute("record", {"command": "sleep 1", "output": "perf.data"})
        assert result.ok
        assert "perf.data" in result.summary
        assert "written" in result.summary.lower() or "completed" in result.summary.lower()

    def test_record_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Permission denied")):
            result = _execute("record", {"command": "sleep 1", "output": "perf.data"})
        assert not result.ok
        assert "perf.data" in result.summary
        assert "exit 1" in result.summary


# ---------------------------------------------------------------------------
# I2: No AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("stat",   {"command": "sleep 1"}),
        ("top",    {"duration": 5}),
        ("record", {"command": "sleep 1", "output": "perf.data"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="output", stderr="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("stat",   {"command": "sleep 1"}),
        ("top",    {"duration": 5}),
        ("record", {"command": "sleep 1", "output": "perf.data"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("stat",   {"command": "sleep 1"}),
        ("top",    {"duration": 5}),
        ("record", {"command": "sleep 1", "output": "perf.data"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"perf\" scontext=user_u:user_r:user_t"
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="perf_event_open failed")):
            result = _execute("stat", {"command": "sleep 1"})
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# I9: execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_well_formed_result(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert "nonexistent_op" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="perf: command not found")):
            result = _execute("stat", {"command": "ls"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert len(result.summary) > 0

    def test_no_exception_on_timeout_exit_124(self) -> None:
        with _patch_run(_fail_result(exit_code=124, stderr="Timeout")):
            result = _execute("top", {"duration": 10})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124

    def test_no_exception_on_oserror_exit_1(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="OSError")):
            result = _execute("record", {"command": "ls", "output": "out.data"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("stat",   {"command": "sleep 1"}),
        ("top",    {"duration": 5}),
        ("record", {"command": "sleep 1", "output": "perf.data"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout=f"{op} output", stderr="counter data")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("stat",   {"command": "ls"}),
        ("top",    {"duration": 5}),
        ("record", {"command": "ls", "output": "perf.data"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_stat(self) -> None:
        with _patch_run(_ok_result(stderr="perf stat output")):
            result = registry.dispatch("perf", "stat", {"command": "sleep 1"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_top(self) -> None:
        with _patch_run(_ok_result(stdout="# Overhead")):
            result = registry.dispatch("perf", "top", {"duration": 5})
        assert result.ok

    def test_dispatch_record(self) -> None:
        with _patch_run(_ok_result(stderr="[ perf record: Captured")):
            result = registry.dispatch("perf", "record", {"command": "sleep 1", "output": "perf.data"})
        assert result.ok

    def test_dispatch_stat_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'command'"):
            registry.dispatch("perf", "stat", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("perf", "nonexistent_op", {"command": "ls"})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires perf binary on Rocky Linux 9")
def test_live_stat_sleep() -> None:
    """Live: perf stat on sleep 1 returns a populated ToolResult."""
    result = _execute("stat", {"command": "sleep 1"})
    assert result.exit_code in (0, 1)
    assert len(result.stderr) > 0  # perf stat outputs to stderr


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires perf binary on Rocky Linux 9")
def test_live_top_brief() -> None:
    """Live: perf top --stdio for 3 seconds returns profiling data."""
    result = _execute("top", {"duration": 3})
    assert result.exit_code in (0, 1)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires perf binary and write access on Rocky Linux 9")
def test_live_record_requires_privileges() -> None:
    """Live: perf record may require elevated privileges.

    This test verifies that the write permission gate (CONFIRM) is honored
    before calling execute() — a Phase 4 router responsibility.
    """
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "test.perf.data")
        result = _execute("record", {"command": "sleep 1", "output": out})
        assert result.exit_code is not None
