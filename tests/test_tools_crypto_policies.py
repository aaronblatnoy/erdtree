"""tests/test_tools_crypto_policies.py — Unit tests for core/tools/crypto_policies.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without update-crypto-policies or fips-mode-setup present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: get/list/fips-status are READ; set/fips-enable are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code!=0) -> not ok, failure summary naming the context.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() never raises (I9): unknown op and exit 127 both return ToolResult.
  * I2: no AI/LLM/model/agent language in any summary.
  * DEFERRED-TO-MOSSAD: live execution against real binaries on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.crypto_policies.run_subprocess`` (the function in the
  crypto_policies module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.crypto_policies  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.crypto_policies import CRYPTO_POLICIES_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.crypto_policies.run_subprocess."""
    return patch("core.tools.crypto_policies.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_crypto_policies_registered(self) -> None:
        assert registry.get("crypto_policies") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("crypto_policies")
        assert spec is not None
        assert spec.name == "crypto_policies"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("crypto_policies")
        assert spec is not None
        expected = {"get", "list", "set", "fips-status", "fips-enable"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["get", "list", "fips-status"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("crypto_policies", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["set", "fips-enable"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("crypto_policies", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Verify the exact argv list passed to run_subprocess for each op."""

    def test_get_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="DEFAULT\n"))
        with patch("core.tools.crypto_policies.run_subprocess", mock_fn):
            _execute("get", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["update-crypto-policies", "--show"]

    def test_list_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="DEFAULT\nFUTURE\nLEGACY\n"))
        with patch("core.tools.crypto_policies.run_subprocess", mock_fn):
            _execute("list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["update-crypto-policies", "--list"]

    def test_set_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.crypto_policies.run_subprocess", mock_fn):
            _execute("set", {"policy": "FUTURE"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["update-crypto-policies", "--set", "FUTURE"]

    def test_set_command_vector_includes_policy_name(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.crypto_policies.run_subprocess", mock_fn):
            _execute("set", {"policy": "LEGACY"})
        argv = mock_fn.call_args[0][0]
        assert "LEGACY" in argv
        assert argv[0] == "update-crypto-policies"
        assert "--set" in argv

    def test_fips_status_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="FIPS mode is enabled.\n"))
        with patch("core.tools.crypto_policies.run_subprocess", mock_fn):
            _execute("fips-status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["fips-mode-setup", "--check"]

    def test_fips_enable_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.crypto_policies.run_subprocess", mock_fn):
            _execute("fips-enable", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["fips-mode-setup", "--enable"]


# ---------------------------------------------------------------------------
# get operation
# ---------------------------------------------------------------------------

class TestGet:
    def test_success_summary_contains_policy(self) -> None:
        with _patch_run(_ok_result(stdout="DEFAULT\n")):
            result = _execute("get", {})
        assert result.ok
        assert "DEFAULT" in result.summary

    def test_success_with_future_policy(self) -> None:
        with _patch_run(_ok_result(stdout="FUTURE\n")):
            result = _execute("get", {})
        assert result.ok
        assert "FUTURE" in result.summary

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="command not found")):
            result = _execute("get", {})
        assert not result.ok
        assert "exit" in result.summary.lower() or "failed" in result.summary.lower()

    def test_result_has_stdout(self) -> None:
        with _patch_run(_ok_result(stdout="LEGACY\n")):
            result = _execute("get", {})
        assert result.stdout == "LEGACY\n"


# ---------------------------------------------------------------------------
# list operation
# ---------------------------------------------------------------------------

class TestList:
    def test_success_summary_mentions_policies(self) -> None:
        stdout = "DEFAULT\nFUTURE\nLEGACY\nFIPS\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("list", {})
        assert result.ok
        # summary should mention count or the word policies
        assert "4" in result.summary or "polic" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error")):
            result = _execute("list", {})
        assert not result.ok
        assert "failed" in result.summary.lower() or "exit" in result.summary.lower()

    def test_result_stdout_preserved(self) -> None:
        stdout = "DEFAULT\nFUTURE\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("list", {})
        assert result.stdout == stdout


# ---------------------------------------------------------------------------
# set operation
# ---------------------------------------------------------------------------

class TestSet:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("set", {"policy": "FUTURE"})
        assert result.ok
        assert "FUTURE" in result.summary
        assert "set" in result.summary.lower() or "polic" in result.summary.lower()

    def test_failure_exit_code_in_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Invalid policy")):
            result = _execute("set", {"policy": "BADPOLICY"})
        assert not result.ok
        assert "BADPOLICY" in result.summary
        assert "1" in result.summary

    def test_binary_not_found_exit_127(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="command not found")):
            result = _execute("set", {"policy": "DEFAULT"})
        assert not result.ok
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# fips-status operation
# ---------------------------------------------------------------------------

class TestFipsStatus:
    def test_success_fips_enabled(self) -> None:
        with _patch_run(_ok_result(stdout="FIPS mode is enabled.\n")):
            result = _execute("fips-status", {})
        assert result.ok
        assert "FIPS" in result.summary
        assert "enabled" in result.summary.lower()

    def test_fips_not_enabled_nonzero_exit(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stdout="FIPS mode is disabled.\n")):
            result = _execute("fips-status", {})
        assert not result.ok
        assert result.exit_code == 1
        # summary should mention not enabled or the exit code
        assert "not" in result.summary.lower() or "1" in result.summary

    def test_result_stdout_preserved(self) -> None:
        stdout = "FIPS mode is enabled.\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("fips-status", {})
        assert result.stdout == stdout


# ---------------------------------------------------------------------------
# fips-enable operation
# ---------------------------------------------------------------------------

class TestFipsEnable:
    def test_success_summary_mentions_reboot(self) -> None:
        with _patch_run(_ok_result(stdout="Setting system policy to FIPS\n")):
            result = _execute("fips-enable", {})
        assert result.ok
        assert "FIPS" in result.summary or "fips" in result.summary.lower()
        assert "reboot" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="unsupported hardware")):
            result = _execute("fips-enable", {})
        assert not result.ok
        assert "1" in result.summary or "failed" in result.summary.lower()


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("get", {}),
        ("list", {}),
        ("set", {"policy": "DEFAULT"}),
        ("fips-status", {}),
        ("fips-enable", {}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"update-crypto-policies\" name=\"crypto-policies\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Error: unknown policy name.")):
            result = _execute("set", {"policy": "BOGUS"})
        assert "ausearch" not in result.summary

    def test_selinux_keyword_in_stderr_surfaces_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="selinux: access denied")):
            result = _execute("get", {})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("get",         {}),
        ("list",        {}),
        ("set",         {"policy": "DEFAULT"}),
        ("fips-status", {}),
        ("fips-enable", {}),
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
        ("get",         {}),
        ("list",        {}),
        ("set",         {"policy": "DEFAULT"}),
        ("fips-status", {}),
        ("fips-enable", {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestI9NeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        """Unknown op must return a ToolResult, never raise."""
        result = _execute("totally-unknown-op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """exit_code=127 (binary not found) degrades gracefully."""
        with _patch_run(_fail_result(exit_code=127, stderr="command not found")):
            result = _execute("get", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_fips_enable_missing_binary_exit_127(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="fips-mode-setup: not found")):
            result = _execute("fips-enable", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_set_missing_binary_exit_127(self) -> None:
        with _patch_run(_fail_result(exit_code=127)):
            result = _execute("set", {"policy": "FUTURE"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_unknown_op_summary_mentions_op(self) -> None:
        result = _execute("bogus-op-xyz", {})
        assert "bogus-op-xyz" in result.summary


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("get",         {}),
        ("list",        {}),
        ("set",         {"policy": "DEFAULT"}),
        ("fips-status", {}),
        ("fips-enable", {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="DEFAULT\n")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("get",         {}),
        ("set",         {"policy": "DEFAULT"}),
        ("fips-enable", {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_get(self) -> None:
        with _patch_run(_ok_result(stdout="DEFAULT\n")):
            result = registry.dispatch("crypto_policies", "get", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_set(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("crypto_policies", "set", {"policy": "FUTURE"})
        assert result.ok

    def test_dispatch_set_missing_policy_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'policy'"):
            registry.dispatch("crypto_policies", "set", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("crypto_policies", "nonexistent_op", {})

    def test_dispatch_fips_enable(self) -> None:
        with _patch_run(_ok_result(stdout="Setting system policy to FIPS\n")):
            result = registry.dispatch("crypto_policies", "fips-enable", {})
        assert result.ok


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires update-crypto-policies on Rocky Linux 9")
def test_live_get() -> None:
    """Live: update-crypto-policies --show returns the active policy."""
    result = _execute("get", {})
    assert result.exit_code == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires update-crypto-policies on Rocky Linux 9")
def test_live_list() -> None:
    """Live: update-crypto-policies --list returns available policy names."""
    result = _execute("list", {})
    assert result.exit_code == 0
    assert "DEFAULT" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires fips-mode-setup on Rocky Linux 9")
def test_live_fips_status() -> None:
    """Live: fips-mode-setup --check returns exit 0 (enabled) or 1 (disabled)."""
    result = _execute("fips-status", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.summary, str)
