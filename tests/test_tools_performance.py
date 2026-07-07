"""tests/test_tools_performance.py — Unit tests for core/tools/performance.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without sar, iostat, vmstat, mpstat, uptime, or
sysstat present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * All 6 operations are present: sar, iostat, vmstat, mpstat, uptime, load.
  * Permission classes: all ops are READ.
  * Command vectors: assert exact argv passed to run_subprocess per op.
  * Exit-code mapping: exit 0 -> ok=True, success summary; nonzero -> ok=False.
  * I2-clean summaries: no AI/LLM/model/agent/agentic/neural/language model.
  * SELinux AVC hint surfaces on AVC-bearing stderr; absent on clean stderr.
  * execute() NEVER raises for unknown op or exit 127 (missing binary).
  * ToolResult structure: 4-key as_dict(), non-None exit_code, str fields.
  * DEFERRED-TO-MOSSAD: live execution tests at the tail.

Mocking strategy
----------------
  Patch ``core.tools.performance.run_subprocess`` (the binding in the
  performance module's namespace, NOT the core.tools package level).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Side-effect import registers the tool in the module-level registry.
import core.tools.performance  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.performance import PERFORMANCE_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch run_subprocess in the performance module namespace."""
    return patch("core.tools.performance.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_performance_registered(self) -> None:
        assert registry.get("performance") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("performance")
        assert spec is not None
        assert spec.name == "performance"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("performance")
        assert spec is not None
        expected = {"sar", "iostat", "vmstat", "mpstat", "uptime", "load"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# 2. Permission classes — all READ
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["sar", "iostat", "vmstat", "mpstat", "uptime", "load"])
    def test_all_ops_are_read(self, op: str) -> None:
        cls = registry.permission_class_for("performance", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# 3. Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_sar_default_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Linux..."))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("sar", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "sar"
        assert "-u" in cmd
        assert "1" in cmd  # default interval
        assert cmd.count("1") >= 1  # interval and/or count

    def test_sar_custom_interval_count(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Linux..."))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("sar", {"interval": 3, "count": 5})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "sar"
        assert "3" in cmd
        assert "5" in cmd

    def test_iostat_default_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Linux..."))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("iostat", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "iostat"
        assert "-x" in cmd

    def test_iostat_custom_interval_count(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Device"))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("iostat", {"interval": 2, "count": 4})
        cmd = mock_fn.call_args[0][0]
        assert "2" in cmd
        assert "4" in cmd

    def test_vmstat_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="procs"))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("vmstat", {"interval": 2, "count": 3})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "vmstat"
        assert "2" in cmd
        assert "3" in cmd

    def test_vmstat_default_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="procs"))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("vmstat", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "vmstat"
        # Default interval=1, count=1
        assert "1" in cmd

    def test_mpstat_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Linux"))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("mpstat", {"interval": 1, "count": 2})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "mpstat"
        assert "-P" in cmd
        assert "ALL" in cmd

    def test_uptime_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout=" 12:00 up 1 day"))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("uptime", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["uptime"]

    def test_load_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="0.15 0.22 0.18 1/312 58423\n"))
        with patch("core.tools.performance.run_subprocess", mock_fn):
            _execute("load", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["cat", "/proc/loadavg"]


# ---------------------------------------------------------------------------
# 4. Exit-code mapping — success and failure
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_exit_0_is_ok(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="output")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_nonzero_exit_is_not_ok(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1

    def test_exit_127_missing_binary(self) -> None:
        """exit 127 (command not found) degrades to well-formed ToolResult."""
        with _patch(_fail(exit_code=127, stderr="sar: command not found")):
            result = _execute("sar", {})
        assert not result.ok
        assert result.exit_code == 127
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
    ])
    def test_failure_summary_mentions_exit_code(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=2, stderr="fail")):
            result = _execute(op, args)
        assert "2" in result.summary


# ---------------------------------------------------------------------------
# 5. I2-clean summaries — no AI language
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent/agentic/neural/language model in summaries."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )

    def test_toolspec_description_no_ai_language(self) -> None:
        desc = PERFORMANCE_SPEC.description
        for word in self._FORBIDDEN:
            assert word not in desc, (
                f"I2 violation: '{word}' in ToolSpec description: {desc!r}"
            )

    @pytest.mark.parametrize("op", ["sar", "iostat", "vmstat", "mpstat", "uptime", "load"])
    def test_opspec_description_no_ai_language(self, op: str) -> None:
        desc = PERFORMANCE_SPEC.ops[op].description
        for word in self._FORBIDDEN:
            assert word not in desc, (
                f"I2 violation: '{word}' in OpSpec description for '{op}': {desc!r}"
            )


# ---------------------------------------------------------------------------
# 6. SELinux hint
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "AVC avc: denied { read } for pid=1234 "
        "comm=\"sar\" name=\"sar\" scontext=system_u:system_r:init_t:s0 "
        "tcontext=system_u:object_r:sysctl_t:s0 tclass=file permissive=0"
    )

    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary or "ausearch" in result.summary
        ), f"SELinux hint missing for op={op!r}: {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="sysstat: command not found")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"Spurious SELinux hint for op={op!r}: {result.summary!r}"
        )


# ---------------------------------------------------------------------------
# 7. execute() NEVER raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary

    def test_exit_127_does_not_raise(self) -> None:
        with _patch(_fail(exit_code=127, stderr="sar: command not found")):
            result = _execute("sar", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_all_ops_exit_127_degrade_gracefully(self) -> None:
        for op in ("sar", "iostat", "vmstat", "mpstat", "uptime", "load"):
            with _patch(_fail(exit_code=127, stderr=f"{op}: command not found")):
                result = _execute(op, {})
            assert isinstance(result, ToolResult), f"op={op!r} raised instead of degrading"
            assert result.exit_code == 127

    def test_missing_optional_args_no_raise(self) -> None:
        """Optional args default safely — no KeyError or TypeError."""
        for op in ("sar", "iostat", "vmstat", "mpstat", "uptime", "load"):
            with _patch(_ok(stdout="output")):
                result = _execute(op, {})
            assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# 8. ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("sar",    {}),
        ("iostat", {}),
        ("vmstat", {}),
        ("mpstat", {}),
        ("uptime", {}),
        ("load",   {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# 9. Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_sar(self) -> None:
        with _patch(_ok(stdout="Linux...")):
            result = registry.dispatch("performance", "sar", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_load(self) -> None:
        with _patch(_ok(stdout="0.15 0.22 0.18 1/312 58423\n")):
            result = registry.dispatch("performance", "load", {})
        assert result.ok

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("performance", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real uptime binary on Rocky Linux 9")
def test_live_uptime() -> None:
    """Live: uptime returns a populated ToolResult with load averages."""
    result = _execute("uptime", {})
    assert result.exit_code == 0
    assert "load average" in result.stdout.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires sysstat installed on Rocky Linux 9")
def test_live_sar() -> None:
    """Live: sar -u 1 1 returns CPU utilization data."""
    result = _execute("sar", {"interval": 1, "count": 1})
    assert result.exit_code == 0
    assert len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires sysstat installed on Rocky Linux 9")
def test_live_iostat() -> None:
    """Live: iostat -x 1 1 returns disk I/O data."""
    result = _execute("iostat", {"interval": 1, "count": 1})
    assert result.exit_code == 0
    assert "Device" in result.stdout or "avg-cpu" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires procps-ng installed on Rocky Linux 9")
def test_live_vmstat() -> None:
    """Live: vmstat 1 1 returns memory and I/O stats."""
    result = _execute("vmstat", {"interval": 1, "count": 1})
    assert result.exit_code == 0
    assert "procs" in result.stdout.lower() or len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires sysstat installed on Rocky Linux 9")
def test_live_mpstat() -> None:
    """Live: mpstat -P ALL 1 1 returns per-CPU stats."""
    result = _execute("mpstat", {"interval": 1, "count": 1})
    assert result.exit_code == 0
    assert len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires /proc/loadavg on a Linux host")
def test_live_load() -> None:
    """Live: cat /proc/loadavg returns load averages."""
    result = _execute("load", {})
    assert result.exit_code == 0
    parts = result.stdout.strip().split()
    assert len(parts) >= 3  # load1, load5, load15, ...
