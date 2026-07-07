"""tests/test_tools_audit.py — Unit tests for core/tools/audit.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without auditctl, ausearch, aureport, or auditd present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/status/search-by-comm/search-by-key/search-by-time/report are READ;
    add-rule/auditd-start/auditd-stop are WRITE; delete-rule is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code != 0) → ok=False, failure summary with op context.
  * Command vectors are exactly as expected for each operation.
  * delete-rule with rule arg uses auditctl -d; without uses auditctl -D.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises for any op, including missing binary (exit 127) or unknown op.
  * ToolResult.as_dict() has exactly the four required keys.
  * No AI/LLM/model/agent language in any summary (I2).

DEFERRED-TO-MOSSAD: live execution against real auditctl/ausearch/aureport on Rocky Linux 9.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.audit  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.audit import AUDIT_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.audit.run_subprocess."""
    return patch("core.tools.audit.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_audit_registered_in_module_registry(self) -> None:
        assert registry.get("audit") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("audit")
        assert spec is not None
        assert spec.name == "audit"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("audit")
        assert spec is not None
        expected = {
            "list", "status", "add-rule", "delete-rule",
            "search-by-comm", "search-by-key", "search-by-time",
            "report", "auditd-start", "auditd-stop",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", [
        "list", "status", "search-by-comm", "search-by-key", "search-by-time", "report"
    ])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("audit", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["add-rule", "auditd-start", "auditd-stop"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("audit", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_delete_rule_is_destructive(self) -> None:
        cls = registry.permission_class_for("audit", "delete-rule")
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for 'delete-rule', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_list_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="-a always,exit\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("list", {})
        assert mock_fn.call_args[0][0] == ["auditctl", "-l"]

    def test_status_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="enabled 1\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("status", {})
        assert mock_fn.call_args[0][0] == ["auditctl", "-s"]

    def test_add_rule_command(self) -> None:
        rule = "always,exit -F arch=b64 -S execve -k exec_watch"
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("add-rule", {"rule": rule})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "auditctl"
        assert cmd[1] == "-a"
        assert cmd[2] == "always,exit"
        assert "-k" in cmd
        assert "exec_watch" in cmd

    def test_delete_rule_all_command(self) -> None:
        """delete-rule with no rule arg must use auditctl -D."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("delete-rule", {})
        assert mock_fn.call_args[0][0] == ["auditctl", "-D"]

    def test_delete_rule_specific_command(self) -> None:
        """delete-rule with a rule arg must use auditctl -d."""
        rule = "always,exit -F arch=b64 -S execve -k exec_watch"
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("delete-rule", {"rule": rule})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "auditctl"
        assert cmd[1] == "-d"
        assert "always,exit" in cmd

    def test_search_by_comm_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="----\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("search-by-comm", {"comm": "sshd"})
        assert mock_fn.call_args[0][0] == ["ausearch", "-c", "sshd"]

    def test_search_by_key_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="----\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("search-by-key", {"key": "identity"})
        assert mock_fn.call_args[0][0] == ["ausearch", "-k", "identity"]

    def test_search_by_time_no_end(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="----\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("search-by-time", {"start": "recent"})
        assert mock_fn.call_args[0][0] == ["ausearch", "-ts", "recent"]

    def test_search_by_time_with_end(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="----\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("search-by-time", {"start": "today", "end": "now"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["ausearch", "-ts", "today", "-te", "now"]

    def test_report_default_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Summary Report\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("report", {})
        assert mock_fn.call_args[0][0] == ["aureport", "--summary"]

    def test_report_custom_type_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Login Report\n"))
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("report", {"report_type": "login"})
        assert mock_fn.call_args[0][0] == ["aureport", "--login"]

    def test_auditd_start_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("auditd-start", {})
        assert mock_fn.call_args[0][0] == ["systemctl", "start", "auditd"]

    def test_auditd_stop_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.audit.run_subprocess", mock_fn):
            _execute("auditd-stop", {})
        assert mock_fn.call_args[0][0] == ["systemctl", "stop", "auditd"]


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("list",           {}),
        ("status",         {}),
        ("add-rule",       {"rule": "always,exit -F arch=b64 -S execve -k test"}),
        ("delete-rule",    {}),
        ("search-by-comm", {"comm": "bash"}),
        ("search-by-key",  {"key": "identity"}),
        ("search-by-time", {"start": "recent"}),
        ("report",         {}),
        ("auditd-start",   {}),
        ("auditd-stop",    {}),
    ])
    def test_success_exit_0_is_ok(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="output")):
            result = _execute(op, args)
        assert result.exit_code == 0
        assert result.ok

    @pytest.mark.parametrize("op,args", [
        ("list",           {}),
        ("status",         {}),
        ("add-rule",       {"rule": "always,exit -F arch=b64 -S execve -k test"}),
        ("delete-rule",    {}),
        ("search-by-comm", {"comm": "bash"}),
        ("search-by-key",  {"key": "identity"}),
        ("search-by-time", {"start": "recent"}),
        ("report",         {}),
        ("auditd-start",   {}),
        ("auditd-stop",    {}),
    ])
    def test_failure_nonzero_not_ok(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error")):
            result = _execute(op, args)
        assert result.exit_code == 1
        assert not result.ok

    def test_failure_summary_contains_exit_code(self) -> None:
        with _patch_run(_fail_result(exit_code=5, stderr="some error")):
            result = _execute("list", {})
        assert "5" in result.summary

    def test_add_rule_success_summary_contains_rule(self) -> None:
        rule = "always,exit -F arch=b64 -S execve -k exec_watch"
        with _patch_run(_ok_result()):
            result = _execute("add-rule", {"rule": rule})
        assert "always,exit" in result.summary or "exec_watch" in result.summary

    def test_delete_rule_all_success_summary(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("delete-rule", {})
        assert "all" in result.summary.lower()

    def test_search_by_comm_failure_names_comm(self) -> None:
        with _patch_run(_fail_result(exit_code=1)):
            result = _execute("search-by-comm", {"comm": "sshd"})
        assert "sshd" in result.summary

    def test_search_by_key_failure_names_key(self) -> None:
        with _patch_run(_fail_result(exit_code=1)):
            result = _execute("search-by-key", {"key": "identity"})
        assert "identity" in result.summary

    def test_search_by_time_failure_names_start(self) -> None:
        with _patch_run(_fail_result(exit_code=1)):
            result = _execute("search-by-time", {"start": "today"})
        assert "today" in result.summary

    def test_auditd_stop_success_summary(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("auditd-stop", {})
        assert result.ok
        assert "stopped" in result.summary.lower() or "inactive" in result.summary.lower()


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list",            {}),
        ("status",          {}),
        ("add-rule",        {"rule": "always,exit -F arch=b64 -S execve -k test"}),
        ("delete-rule",     {}),
        ("search-by-comm",  {"comm": "bash"}),
        ("search-by-key",   {"key": "identity"}),
        ("search-by-time",  {"start": "recent"}),
        ("report",          {}),
        ("auditd-start",    {}),
        ("auditd-stop",     {}),
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
        ("list",            {}),
        ("status",          {}),
        ("add-rule",        {"rule": "always,exit -F arch=b64 -S execve -k test"}),
        ("delete-rule",     {}),
        ("search-by-comm",  {"comm": "bash"}),
        ("search-by-key",   {"key": "identity"}),
        ("search-by-time",  {"start": "recent"}),
        ("report",          {}),
        ("auditd-start",    {}),
        ("auditd-stop",     {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "auditctl: Error - AVC avc:  denied  { write } for  pid=1234 "
        "comm=\"auditctl\" name=\"audit.rules\" scontext=unconfined_u:unconfined_r:"
        "unconfined_t:s0-s0:c0.c1023 tcontext=system_u:object_r:etc_t:s0 tclass=file"
    )

    @pytest.mark.parametrize("op,args", [
        ("list",           {}),
        ("status",         {}),
        ("add-rule",       {"rule": "always,exit -F arch=b64 -S execve -k test"}),
        ("delete-rule",    {}),
        ("search-by-comm", {"comm": "bash"}),
        ("search-by-key",  {"key": "identity"}),
        ("search-by-time", {"start": "recent"}),
        ("report",         {}),
        ("auditd-start",   {}),
        ("auditd-stop",    {}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint missing from summary for op='{op}': {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="auditctl: Error opening config file")):
            result = _execute("list", {})
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        """Unknown op must return a ToolResult, never raise."""
        result = _execute("totally-bogus-op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert "Unknown operation" in result.summary or len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """Binary not found (exit 127) must degrade gracefully."""
        missing_result = ToolResult(exit_code=127, stdout="", stderr="", summary="command not found: auditctl")
        with _patch_run(missing_result):
            result = _execute("list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_timeout_exit_124_returns_toolresult(self) -> None:
        timeout_result = ToolResult(exit_code=124, stdout="", stderr="", summary="timed out")
        with _patch_run(timeout_result):
            result = _execute("report", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124

    def test_unknown_op_never_raises_even_with_empty_args(self) -> None:
        try:
            result = _execute("nonexistent", {})
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"_execute raised unexpectedly: {exc}")
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list",            {}),
        ("status",          {}),
        ("add-rule",        {"rule": "always,exit -F arch=b64 -S execve -k test"}),
        ("delete-rule",     {}),
        ("search-by-comm",  {"comm": "bash"}),
        ("search-by-key",   {"key": "identity"}),
        ("search-by-time",  {"start": "recent"}),
        ("report",          {}),
        ("auditd-start",    {}),
        ("auditd-stop",     {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="some output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("list",            {}),
        ("status",          {}),
        ("add-rule",        {"rule": "always,exit -F arch=b64 -S execve -k test"}),
        ("delete-rule",     {}),
        ("search-by-comm",  {"comm": "bash"}),
        ("search-by-key",   {"key": "identity"}),
        ("search-by-time",  {"start": "recent"}),
        ("report",          {}),
        ("auditd-start",    {}),
        ("auditd-stop",     {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# AUDIT_SPEC sanity
# ---------------------------------------------------------------------------

class TestAuditSpec:
    def test_spec_is_audit_spec(self) -> None:
        assert AUDIT_SPEC.name == "audit"

    def test_delete_rule_op_class(self) -> None:
        cls = AUDIT_SPEC.permission_class_for("delete-rule")
        assert cls is OpClass.DESTRUCTIVE

    def test_add_rule_op_class(self) -> None:
        cls = AUDIT_SPEC.permission_class_for("add-rule")
        assert cls is OpClass.WRITE

    def test_list_op_class(self) -> None:
        cls = AUDIT_SPEC.permission_class_for("list")
        assert cls is OpClass.READ


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real auditctl on Rocky Linux 9")
def test_live_list_rules() -> None:
    """Live: auditctl -l returns a populated ToolResult."""
    result = _execute("list", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real auditctl on Rocky Linux 9")
def test_live_status() -> None:
    """Live: auditctl -s returns audit status."""
    result = _execute("status", {})
    assert result.exit_code in (0, 1)
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real ausearch on Rocky Linux 9")
def test_live_search_by_comm() -> None:
    """Live: ausearch -c sshd returns audit events or not-found."""
    result = _execute("search-by-comm", {"comm": "sshd"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.summary, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real aureport on Rocky Linux 9")
def test_live_report_summary() -> None:
    """Live: aureport --summary generates a report."""
    result = _execute("report", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl + auditd on Rocky Linux 9")
def test_live_auditd_start_requires_root() -> None:
    """Live: systemctl start auditd on Rocky requires elevated privileges."""
    result = _execute("auditd-start", {})
    assert result.exit_code is not None
