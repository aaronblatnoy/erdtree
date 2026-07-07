"""tests/test_tools_tuned.py — Unit tests for core/tools/tuned.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without tuned-adm present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/active/recommend are READ; profile/off are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary.
  * Command vectors: each op passes the correct argv list to run_subprocess.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() never raises (I9): unknown op and exit-127 both yield ToolResult.
  * I2-clean summaries: no forbidden AI/LLM/model/agent language.
  * DEFERRED-TO-MOSSAD: live execution against real tuned-adm on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.tuned.run_subprocess`` (the function in the tuned
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.tuned  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.tuned import TUNED_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.tuned.run_subprocess."""
    return patch("core.tools.tuned.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_tuned_registered_in_module_registry(self) -> None:
        assert registry.get("tuned") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("tuned")
        assert spec is not None
        assert spec.name == "tuned"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("tuned")
        assert spec is not None
        expected = {"list", "active", "recommend", "profile", "off"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list", "active", "recommend"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("tuned", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["profile", "off"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("tuned", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — assert the exact argv passed to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_list_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Available profiles:\n"))
        with patch("core.tools.tuned.run_subprocess", mock_fn):
            _execute("list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tuned-adm", "list"]

    def test_active_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Current active profile: balanced\n"))
        with patch("core.tools.tuned.run_subprocess", mock_fn):
            _execute("active", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tuned-adm", "active"]

    def test_recommend_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="throughput-performance\n"))
        with patch("core.tools.tuned.run_subprocess", mock_fn):
            _execute("recommend", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tuned-adm", "recommend"]

    def test_profile_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.tuned.run_subprocess", mock_fn):
            _execute("profile", {"profile": "latency-performance"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tuned-adm", "profile", "latency-performance"]

    def test_off_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Turned off tuning.\n"))
        with patch("core.tools.tuned.run_subprocess", mock_fn):
            _execute("off", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tuned-adm", "off"]


# ---------------------------------------------------------------------------
# list operation
# ---------------------------------------------------------------------------

class TestList:
    def test_success_summary(self) -> None:
        stdout = (
            "Available profiles:\n"
            "- balanced\n"
            "- throughput-performance\n"
            "Current active profile: balanced\n"
        )
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("list", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="tuned-adm: error: daemon not running")):
            result = _execute("list", {})
        assert not result.ok
        assert str(result.exit_code) in result.summary or "failed" in result.summary.lower()

    def test_result_has_stdout(self) -> None:
        with _patch_run(_ok_result(stdout="Available profiles:\n- balanced\n")):
            result = _execute("list", {})
        assert "Available" in result.stdout or result.stdout != ""


# ---------------------------------------------------------------------------
# active operation
# ---------------------------------------------------------------------------

class TestActive:
    def test_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="Current active profile: throughput-performance\n")):
            result = _execute("active", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="No current active profile.")):
            result = _execute("active", {})
        assert not result.ok
        assert "failed" in result.summary.lower() or str(result.exit_code) in result.summary


# ---------------------------------------------------------------------------
# recommend operation
# ---------------------------------------------------------------------------

class TestRecommend:
    def test_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="throughput-performance\n")):
            result = _execute("recommend", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="tuned-adm: error: cannot recommend")):
            result = _execute("recommend", {})
        assert not result.ok
        assert "failed" in result.summary.lower() or str(result.exit_code) in result.summary


# ---------------------------------------------------------------------------
# profile operation
# ---------------------------------------------------------------------------

class TestProfile:
    def test_success_summary_names_profile(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("profile", {"profile": "latency-performance"})
        assert result.ok
        assert "latency-performance" in result.summary

    def test_failure_summary_names_profile_and_exit(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="unknown profile: bogusprofile")):
            result = _execute("profile", {"profile": "bogusprofile"})
        assert not result.ok
        assert "bogusprofile" in result.summary
        assert "1" in result.summary

    def test_profile_is_write_class(self) -> None:
        cls = TUNED_SPEC.permission_class_for("profile")
        assert cls is OpClass.WRITE


# ---------------------------------------------------------------------------
# off operation
# ---------------------------------------------------------------------------

class TestOff:
    def test_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="Turned off tuning.\n")):
            result = _execute("off", {})
        assert result.ok
        assert "deactivated" in result.summary.lower() or "no profile" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Failed to communicate with tuned daemon.")):
            result = _execute("off", {})
        assert not result.ok
        assert "failed" in result.summary.lower() or str(result.exit_code) in result.summary

    def test_off_is_write_class(self) -> None:
        cls = TUNED_SPEC.permission_class_for("off")
        assert cls is OpClass.WRITE


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("list",      {}),
        ("active",    {}),
        ("recommend", {}),
        ("profile",   {"profile": "balanced"}),
        ("off",       {}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "tuned-adm: error: AVC avc: denied { read } for pid=1234 "
            "comm=\"tuned-adm\" name=\"tuned\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint not surfaced for op='{op}': {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="unknown profile: foo")):
            result = _execute("profile", {"profile": "foo"})
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list",      {}),
        ("active",    {}),
        ("recommend", {}),
        ("profile",   {"profile": "balanced"}),
        ("off",       {}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("list",      {}),
        ("active",    {}),
        ("recommend", {}),
        ("profile",   {"profile": "balanced"}),
        ("off",       {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="tuned-adm: command not found")):
            result = _execute("list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_missing_binary_profile_exit_127(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="tuned-adm: command not found")):
            result = _execute("profile", {"profile": "balanced"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_off_exit_127(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="tuned-adm: command not found")):
            result = _execute("off", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list",      {}),
        ("active",    {}),
        ("recommend", {}),
        ("profile",   {"profile": "balanced"}),
        ("off",       {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("list",      {}),
        ("active",    {}),
        ("recommend", {}),
        ("profile",   {"profile": "balanced"}),
        ("off",       {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )

    def test_no_ai_language_in_unknown_op_summary(self) -> None:
        result = _execute("__garbage__", {})
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in unknown-op summary: {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_list(self) -> None:
        with _patch_run(_ok_result(stdout="Available profiles:\n")):
            result = registry.dispatch("tuned", "list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_active(self) -> None:
        with _patch_run(_ok_result(stdout="Current active profile: balanced\n")):
            result = registry.dispatch("tuned", "active", {})
        assert result.ok

    def test_dispatch_profile(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("tuned", "profile", {"profile": "balanced"})
        assert result.ok

    def test_dispatch_missing_profile_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'profile'"):
            registry.dispatch("tuned", "profile", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("tuned", "nonexistent_op", {})

    def test_dispatch_off(self) -> None:
        with _patch_run(_ok_result(stdout="Turned off tuning.\n")):
            result = registry.dispatch("tuned", "off", {})
        assert result.ok


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real tuned-adm on Rocky Linux 9")
def test_live_list() -> None:
    """Live: tuned-adm list returns available profiles."""
    result = _execute("list", {})
    assert result.exit_code == 0
    assert "balanced" in result.stdout or len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real tuned-adm on Rocky Linux 9")
def test_live_active() -> None:
    """Live: tuned-adm active returns the current profile."""
    result = _execute("active", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real tuned-adm on Rocky Linux 9")
def test_live_recommend() -> None:
    """Live: tuned-adm recommend returns a profile name."""
    result = _execute("recommend", {})
    assert result.exit_code == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real tuned-adm on Rocky Linux 9; requires root or sudo")
def test_live_profile_requires_root() -> None:
    """Live: tuned-adm profile on Rocky requires elevated privileges.

    This test must be run as root or with sudo. As a regular user, tuned-adm
    may return a non-zero exit code with a permission error in stderr.
    """
    result = _execute("profile", {"profile": "balanced"})
    assert result.exit_code is not None
