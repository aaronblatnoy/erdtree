"""tests/test_tools_fapolicyd.py — Unit tests for core/tools/fapolicyd.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without fapolicyd or fapolicyd-cli present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/list_rules are READ; allow/deny/update are WRITE.
  * Command vectors: exact argv list for each operation.
  * Exit-code mapping: exit 0 -> ok=True; nonzero -> ok=False.
  * I2 invariant: no AI/LLM/model/agent language in any summary.
  * SELinux AVC hint surfaced when stderr contains AVC language.
  * execute() never raises (I9): unknown ops and missing binary (exit 127) both
    return well-formed ToolResult, no exception.
  * ToolResult structure: four required fields, as_dict() returns four keys.
  * DEFERRED-TO-MOSSAD: live execution against real fapolicyd on Rocky Linux 9.

Mocking strategy
----------------
  Patch ``core.tools.fapolicyd.run_subprocess`` (the function in the
  fapolicyd module's namespace, bound at import time) so no real process
  is launched. The tool builds argv lists and calls the module-level
  run_subprocess; patching there intercepts all calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Side-effect import: triggers registry.register(FAPOLICYD_SPEC)
import core.tools.fapolicyd  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.fapolicyd import FAPOLICYD_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Context-manager patch on core.tools.fapolicyd.run_subprocess."""
    return patch("core.tools.fapolicyd.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_fapolicyd_registered_in_module_registry(self) -> None:
        assert registry.get("fapolicyd") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("fapolicyd")
        assert spec is not None
        assert spec.name == "fapolicyd"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("fapolicyd")
        assert spec is not None
        expected = {"status", "list_rules", "allow", "deny", "update"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "list_rules"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("fapolicyd", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["allow", "deny", "update"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("fapolicyd", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_spec_permission_class_for_matches_registry(self) -> None:
        for op in ("status", "list_rules", "allow", "deny", "update"):
            assert FAPOLICYD_SPEC.permission_class_for(op) == registry.permission_class_for("fapolicyd", op)


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_status_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.fapolicyd.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "status", "--no-pager", "fapolicyd"]

    def test_list_rules_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.fapolicyd.run_subprocess", mock_fn):
            _execute("list_rules", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["fapolicyd-cli", "--list"]

    def test_allow_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.fapolicyd.run_subprocess", mock_fn):
            _execute("allow", {"path": "/usr/local/bin/myapp"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "fapolicyd-cli"
        assert argv[1] == "--add"
        assert "allow" in argv[2]
        assert "/usr/local/bin/myapp" in argv[2]

    def test_deny_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.fapolicyd.run_subprocess", mock_fn):
            _execute("deny", {"path": "/tmp/bad_binary"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "fapolicyd-cli"
        assert argv[1] == "--add"
        assert "deny" in argv[2]
        assert "/tmp/bad_binary" in argv[2]

    def test_update_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.fapolicyd.run_subprocess", mock_fn):
            _execute("update", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["fapolicyd-cli", "--update"]

    def test_allow_rule_string_contains_path(self) -> None:
        """The rule string passed to --add must contain the literal path."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.fapolicyd.run_subprocess", mock_fn):
            _execute("allow", {"path": "/opt/app/server"})
        rule_arg = mock_fn.call_args[0][0][2]
        assert "/opt/app/server" in rule_arg

    def test_deny_rule_string_contains_path(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.fapolicyd.run_subprocess", mock_fn):
            _execute("deny", {"path": "/var/tmp/dropper"})
        rule_arg = mock_fn.call_args[0][0][2]
        assert "/var/tmp/dropper" in rule_arg


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_status_success(self) -> None:
        with _patch_run(_ok_result(stdout="● fapolicyd.service\n   Active: active")):
            result = _execute("status", {})
        assert result.ok
        assert "fapolicyd" in result.summary.lower()

    def test_status_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=3, stderr="inactive")):
            result = _execute("status", {})
        assert not result.ok
        assert result.exit_code == 3
        assert "3" in result.summary

    def test_list_rules_success(self) -> None:
        with _patch_run(_ok_result(stdout="allow perm=any trust=1 : all\n")):
            result = _execute("list_rules", {})
        assert result.ok
        assert "rule" in result.summary.lower() or "fapolicyd" in result.summary.lower()

    def test_list_rules_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="cannot connect")):
            result = _execute("list_rules", {})
        assert not result.ok
        assert "1" in result.summary

    def test_allow_success(self) -> None:
        with _patch_run(_ok_result(stdout="Rule added")):
            result = _execute("allow", {"path": "/usr/local/bin/myapp"})
        assert result.ok
        assert "/usr/local/bin/myapp" in result.summary
        assert "allow" in result.summary.lower()

    def test_allow_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="rule error")):
            result = _execute("allow", {"path": "/bad/path"})
        assert not result.ok
        assert "/bad/path" in result.summary
        assert "1" in result.summary

    def test_deny_success(self) -> None:
        with _patch_run(_ok_result(stdout="Rule added")):
            result = _execute("deny", {"path": "/tmp/bad"})
        assert result.ok
        assert "/tmp/bad" in result.summary
        assert "deny" in result.summary.lower()

    def test_deny_success_includes_safety_note(self) -> None:
        """Deny success summary must include a note about critical path risk."""
        with _patch_run(_ok_result(stdout="Rule added")):
            result = _execute("deny", {"path": "/tmp/payload"})
        assert result.ok
        # Summary should warn about critical path risks
        low = result.summary.lower()
        assert "critical" in low or "login" in low or "broken" in low

    def test_deny_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="rule error")):
            result = _execute("deny", {"path": "/bad/path"})
        assert not result.ok
        assert "1" in result.summary

    def test_update_success(self) -> None:
        with _patch_run(_ok_result(stdout="Rules have been updated")):
            result = _execute("update", {})
        assert result.ok
        assert "reload" in result.summary.lower() or "fapolicyd" in result.summary.lower()

    def test_update_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="cannot connect to daemon")):
            result = _execute("update", {})
        assert not result.ok
        assert "1" in result.summary


# ---------------------------------------------------------------------------
# I2-clean summaries
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("list_rules", {}),
        ("allow",      {"path": "/usr/local/bin/myapp"}),
        ("deny",       {"path": "/tmp/bad_binary"}),
        ("update",     {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="success output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': "
                f"{result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("list_rules", {}),
        ("allow",      {"path": "/usr/local/bin/myapp"}),
        ("deny",       {"path": "/tmp/bad_binary"}),
        ("update",     {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': "
                f"{result.summary!r}"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("list_rules", {}),
        ("allow",      {"path": "/usr/local/bin/myapp"}),
        ("deny",       {"path": "/tmp/bad_binary"}),
        ("update",     {}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"fapolicyd-cli\" name=\"fapolicyd\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"Expected SELinux hint in summary for op='{op}', got: {result.summary!r}"
        )

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="daemon not running.")):
            result = _execute("status", {})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary

    def test_selinux_keyword_in_stderr_surfaces_hint(self) -> None:
        selinux_stderr = "fapolicyd: selinux policy prevented file access"
        with _patch_run(_fail_result(exit_code=1, stderr=selinux_stderr)):
            result = _execute("update", {})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert not result.ok

    def test_unknown_op_summary_is_nonempty(self) -> None:
        result = _execute("__totally_bogus__", {})
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_status(self) -> None:
        """Missing binary returns exit 127; execute() must not raise."""
        with _patch_run(ToolResult(
            exit_code=127, stdout="", stderr="systemctl: command not found", summary=""
        )):
            result = _execute("status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_exit_127_update(self) -> None:
        with _patch_run(ToolResult(
            exit_code=127, stdout="", stderr="fapolicyd-cli: command not found", summary=""
        )):
            result = _execute("update", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_exit_127_allow(self) -> None:
        with _patch_run(ToolResult(
            exit_code=127, stdout="", stderr="fapolicyd-cli: command not found", summary=""
        )):
            result = _execute("allow", {"path": "/usr/local/bin/x"})
        assert isinstance(result, ToolResult)
        assert not result.ok


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("list_rules", {}),
        ("allow",      {"path": "/usr/local/bin/myapp"}),
        ("deny",       {"path": "/tmp/bad_binary"}),
        ("update",     {}),
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
        ("status",     {}),
        ("list_rules", {}),
        ("allow",      {"path": "/usr/local/bin/myapp"}),
        ("deny",       {"path": "/tmp/bad_binary"}),
        ("update",     {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("list_rules", {}),
        ("allow",      {"path": "/usr/local/bin/myapp"}),
        ("deny",       {"path": "/tmp/bad_binary"}),
        ("update",     {}),
    ])
    def test_failure_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real fapolicyd on Rocky Linux 9")
def test_live_status_fapolicyd() -> None:
    """Live: systemctl status fapolicyd returns a populated ToolResult."""
    result = _execute("status", {})
    assert result.exit_code in (0, 3, 4)
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real fapolicyd-cli on Rocky Linux 9")
def test_live_list_rules() -> None:
    """Live: fapolicyd-cli --list returns loaded rules."""
    result = _execute("list_rules", {})
    assert result.exit_code == 0
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real fapolicyd-cli + root on Rocky Linux 9")
def test_live_update_requires_root() -> None:
    """Live: fapolicyd-cli --update on Rocky requires elevated privileges.

    Run as root for exit 0. As a regular user, the daemon rejects the request.
    """
    result = _execute("update", {})
    assert result.exit_code is not None
