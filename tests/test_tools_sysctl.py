"""tests/test_tools_sysctl.py — Unit tests for core/tools/sysctl.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without sysctl present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/get are READ; set/persist are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (nonzero) → ok=False, failure summary containing the key name.
  * Command vectors: exact argv lists verified for each op.
  * persist: two run_subprocess calls (tee then sysctl --system); failure of
    the tee write is propagated; reload failure is propagated.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2: no AI/LLM/model/agent language in any summary.
  * I9: execute() never raises for unknown op or missing binary (exit 127).
  * DEFERRED-TO-MOSSAD: live execution against real sysctl on Rocky Linux 9.

Mocking strategy
----------------
  Patch ``core.tools.sysctl.run_subprocess`` (the function in the sysctl
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

# Import the module to trigger self-registration.
import core.tools.sysctl  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.sysctl import SYSCTL_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    return patch("core.tools.sysctl.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_sysctl_registered(self) -> None:
        assert registry.get("sysctl") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("sysctl")
        assert spec is not None
        assert spec.name == "sysctl"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("sysctl")
        assert spec is not None
        expected = {"list", "get", "set", "persist"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list", "get"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("sysctl", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["set", "persist"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("sysctl", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — assert exact argv passed to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_list_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="vm.swappiness = 60\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["sysctl", "-a"]

    def test_get_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="vm.swappiness = 60\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("get", {"key": "vm.swappiness"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["sysctl", "vm.swappiness"]

    def test_set_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="vm.swappiness = 10\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("set", {"key": "vm.swappiness", "value": "10"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["sysctl", "-w", "vm.swappiness=10"]

    def test_persist_first_call_is_tee(self) -> None:
        """persist() must call tee <filepath> then sysctl --system."""
        mock_fn = MagicMock(return_value=_ok(stdout="ok\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("persist", {"key": "vm.swappiness", "value": "10"})
        assert mock_fn.call_count == 2
        first_argv = mock_fn.call_args_list[0][0][0]
        assert first_argv[0] == "tee"
        assert first_argv[1].startswith("/etc/sysctl.d/")
        assert first_argv[1].endswith(".conf")

    def test_persist_second_call_is_sysctl_system(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="ok\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("persist", {"key": "vm.swappiness", "value": "10"})
        second_argv = mock_fn.call_args_list[1][0][0]
        assert second_argv == ["sysctl", "--system"]

    def test_persist_custom_filename(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="ok\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("persist", {
                "key": "vm.swappiness",
                "value": "10",
                "filename": "99-custom.conf",
            })
        first_argv = mock_fn.call_args_list[0][0][0]
        assert first_argv[1] == "/etc/sysctl.d/99-custom.conf"

    def test_persist_tee_input_contains_key_value(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="ok\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("persist", {"key": "vm.swappiness", "value": "10"})
        # input keyword arg passed to first call (tee)
        first_call_kwargs = mock_fn.call_args_list[0][1]
        assert "input" in first_call_kwargs
        assert "vm.swappiness" in first_call_kwargs["input"]
        assert "10" in first_call_kwargs["input"]


# ---------------------------------------------------------------------------
# list operation
# ---------------------------------------------------------------------------

class TestList:
    def test_success(self) -> None:
        stdout = "vm.swappiness = 60\nnet.ipv4.ip_forward = 0\n"
        with _patch_run(_ok(stdout=stdout)):
            result = _execute("list", {})
        assert result.ok
        assert "kernel parameter" in result.summary.lower() or "listed" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="permission denied")):
            result = _execute("list", {})
        assert not result.ok
        assert result.exit_code == 1

    def test_no_args_required(self) -> None:
        with _patch_run(_ok(stdout="kernel.panic = 0\n")):
            result = _execute("list", {})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# get operation
# ---------------------------------------------------------------------------

class TestGet:
    def test_success_summary_contains_key(self) -> None:
        with _patch_run(_ok(stdout="vm.swappiness = 60\n")):
            result = _execute("get", {"key": "vm.swappiness"})
        assert result.ok
        assert "vm.swappiness" in result.summary

    def test_failure_summary_contains_key(self) -> None:
        with _patch_run(_fail(exit_code=255, stderr="No such file or directory")):
            result = _execute("get", {"key": "kernel.bogus_key"})
        assert not result.ok
        assert "kernel.bogus_key" in result.summary
        assert result.exit_code == 255

    def test_stdout_preserved(self) -> None:
        with _patch_run(_ok(stdout="net.ipv4.ip_forward = 0\n")):
            result = _execute("get", {"key": "net.ipv4.ip_forward"})
        assert result.stdout == "net.ipv4.ip_forward = 0\n"


# ---------------------------------------------------------------------------
# set operation
# ---------------------------------------------------------------------------

class TestSet:
    def test_success_summary(self) -> None:
        with _patch_run(_ok(stdout="vm.swappiness = 10\n")):
            result = _execute("set", {"key": "vm.swappiness", "value": "10"})
        assert result.ok
        assert "vm.swappiness" in result.summary
        assert "10" in result.summary
        assert "runtime" in result.summary.lower() or "not persistent" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=255, stderr="Read-only file system")):
            result = _execute("set", {"key": "net.ipv4.ip_forward", "value": "1"})
        assert not result.ok
        assert "net.ipv4.ip_forward" in result.summary
        assert "255" in result.summary

    def test_assignment_format(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            _execute("set", {"key": "vm.swappiness", "value": "5"})
        argv = mock_fn.call_args[0][0]
        # Must contain key=value as a single token
        assert "vm.swappiness=5" in argv


# ---------------------------------------------------------------------------
# persist operation
# ---------------------------------------------------------------------------

class TestPersist:
    def test_success_summary(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="ok\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute("persist", {"key": "vm.swappiness", "value": "10"})
        assert result.ok
        assert "vm.swappiness" in result.summary
        assert "10" in result.summary
        assert "/etc/sysctl.d/" in result.summary

    def test_tee_failure_propagated(self) -> None:
        """If the tee write fails, persist must return the failure without calling sysctl --system."""
        mock_fn = MagicMock(return_value=_fail(exit_code=1, stderr="Permission denied"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute("persist", {"key": "vm.swappiness", "value": "10"})
        assert not result.ok
        # Should only have called tee (1 call), not sysctl --system
        assert mock_fn.call_count == 1

    def test_reload_failure_propagated(self) -> None:
        """If tee succeeds but sysctl --system fails, return failure."""
        ok_then_fail = [_ok(stdout="vm.swappiness = 10\n"), _fail(exit_code=1)]
        mock_fn = MagicMock(side_effect=ok_then_fail)
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute("persist", {"key": "vm.swappiness", "value": "10"})
        assert not result.ok
        assert mock_fn.call_count == 2

    def test_filepath_restricted_to_sysctl_d(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="ok\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            # Even if filename contains slashes, must be under /etc/sysctl.d/
            _execute("persist", {
                "key": "vm.swappiness",
                "value": "10",
                "filename": "../../etc/cron.d/evil.conf",
            })
        first_argv = mock_fn.call_args_list[0][0][0]
        assert first_argv[1].startswith("/etc/sysctl.d/")


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("get",  {"key": "vm.swappiness"}),
        ("set",  {"key": "vm.swappiness", "value": "10"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "sysctl: setting key \"vm.swappiness\": "
            "AVC avc: denied { write } for pid=1234"
        )
        with _patch_run(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_persist_tee_avc_in_stderr_surfaces_hint(self) -> None:
        avc_stderr = "tee: /etc/sysctl.d/foo.conf: AVC avc: denied { write }"
        mock_fn = MagicMock(return_value=_fail(exit_code=1, stderr=avc_stderr))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute("persist", {"key": "vm.swappiness", "value": "10"})
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail(exit_code=255, stderr="No such file or directory")):
            result = _execute("get", {"key": "kernel.bogus"})
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list",    {}),
        ("get",     {"key": "vm.swappiness"}),
        ("set",     {"key": "vm.swappiness", "value": "10"}),
        ("persist", {"key": "vm.swappiness", "value": "10"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="ok output"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("list",    {}),
        ("get",     {"key": "vm.swappiness"}),
        ("set",     {"key": "vm.swappiness", "value": "10"}),
        ("persist", {"key": "vm.swappiness", "value": "10"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list",    {}),
        ("get",     {"key": "vm.swappiness"}),
        ("set",     {"key": "vm.swappiness", "value": "10"}),
        ("persist", {"key": "vm.swappiness", "value": "10"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="vm.swappiness = 10\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("get",     {"key": "kernel.bogus"}),
        ("set",     {"key": "vm.swappiness", "value": "10"}),
        ("persist", {"key": "vm.swappiness", "value": "10"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# I9: execute() NEVER raises
# ---------------------------------------------------------------------------

class TestNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("definitely_not_a_real_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert len(result.summary) > 0
        assert "definitely_not_a_real_op" in result.summary

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        mock_fn = MagicMock(
            return_value=ToolResult(
                exit_code=127,
                stdout="",
                stderr="sysctl: command not found",
                summary="",
            )
        )
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute("list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_persist_missing_binary_exit_127(self) -> None:
        mock_fn = MagicMock(
            return_value=ToolResult(
                exit_code=127,
                stdout="",
                stderr="tee: command not found",
                summary="",
            )
        )
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = _execute("persist", {"key": "vm.swappiness", "value": "10"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_list(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="kernel.panic = 0\n"))
        with patch("core.tools.sysctl.run_subprocess", mock_fn):
            result = registry.dispatch("sysctl", "list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_get(self) -> None:
        with _patch_run(_ok(stdout="vm.swappiness = 60\n")):
            result = registry.dispatch("sysctl", "get", {"key": "vm.swappiness"})
        assert result.ok

    def test_dispatch_get_missing_key_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'key'"):
            registry.dispatch("sysctl", "get", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("sysctl", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sysctl on Rocky Linux 9")
def test_live_list() -> None:
    """Live: sysctl -a returns a populated ToolResult with many parameters."""
    result = _execute("list", {})
    assert result.exit_code == 0
    assert "vm.swappiness" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sysctl on Rocky Linux 9")
def test_live_get_swappiness() -> None:
    """Live: read vm.swappiness returns a numeric value."""
    result = _execute("get", {"key": "vm.swappiness"})
    assert result.exit_code == 0
    assert "vm.swappiness" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root on Rocky Linux 9")
def test_live_set_swappiness() -> None:
    """Live: sysctl -w vm.swappiness=60 (requires root)."""
    result = _execute("set", {"key": "vm.swappiness", "value": "60"})
    assert result.exit_code == 0
    assert "vm.swappiness" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root on Rocky Linux 9")
def test_live_persist_swappiness() -> None:
    """Live: persist vm.swappiness=60 to /etc/sysctl.d/ and reload (requires root)."""
    result = _execute("persist", {
        "key": "vm.swappiness",
        "value": "60",
        "filename": "99-test-swappiness.conf",
    })
    assert result.exit_code == 0
    assert "/etc/sysctl.d/" in result.summary
