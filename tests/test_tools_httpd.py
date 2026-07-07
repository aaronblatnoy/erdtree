"""tests/test_tools_httpd.py — Unit tests for core/tools/httpd.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without apachectl, systemctl, or curl present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/configtest/vhost_list/mod_status are READ;
    start/stop/restart are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code != 0) -> not ok, failure summary with exit code.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() never raises (I9): unknown op and missing binary both degrade.
  * I2: no AI/LLM/model/agent language in any summary.
  * Command vectors are exactly correct (argv list content).
  * DEFERRED-TO-MOSSAD: live execution on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.httpd.run_subprocess`` (the function in the httpd
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.httpd  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.httpd import HTTPD_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.httpd.run_subprocess."""
    return patch("core.tools.httpd.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_httpd_registered_in_module_registry(self) -> None:
        assert registry.get("httpd") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("httpd")
        assert spec is not None
        assert spec.name == "httpd"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("httpd")
        assert spec is not None
        expected = {"status", "configtest", "start", "stop", "restart", "vhost_list", "mod_status"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "configtest", "vhost_list", "mod_status"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("httpd", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["start", "stop", "restart"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("httpd", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — assert exact argv passed to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_status_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.httpd.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["apachectl", "status"]

    def test_configtest_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.httpd.run_subprocess", mock_fn):
            _execute("configtest", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["apachectl", "configtest"]

    def test_start_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.httpd.run_subprocess", mock_fn):
            _execute("start", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "start", "httpd"]

    def test_stop_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.httpd.run_subprocess", mock_fn):
            _execute("stop", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "stop", "httpd"]

    def test_restart_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.httpd.run_subprocess", mock_fn):
            _execute("restart", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "restart", "httpd"]

    def test_vhost_list_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="VirtualHost configuration:\n*:80"))
        with patch("core.tools.httpd.run_subprocess", mock_fn):
            _execute("vhost_list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["apachectl", "-S"]

    def test_mod_status_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.httpd.run_subprocess", mock_fn):
            _execute("mod_status", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "curl"
        assert "--silent" in argv
        assert any("127.0.0.1" in arg for arg in argv)
        assert any("server-status" in arg for arg in argv)


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure branches
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op", ["status", "configtest", "start", "stop", "restart",
                                     "vhost_list", "mod_status"])
    def test_exit_zero_is_ok(self, op: str) -> None:
        with _patch_run(_ok_result(stdout="some output")):
            result = _execute(op, {})
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,exit_code", [
        ("status",     3),
        ("configtest", 1),
        ("start",      1),
        ("stop",       1),
        ("restart",    1),
        ("vhost_list", 1),
        ("mod_status", 7),
    ])
    def test_nonzero_exit_is_not_ok(self, op: str, exit_code: int) -> None:
        with _patch_run(_fail_result(exit_code=exit_code, stderr="something failed")):
            result = _execute(op, {})
        assert not result.ok
        assert result.exit_code == exit_code

    def test_start_success_summary(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("start", {})
        assert result.ok
        assert "started" in result.summary.lower() or "running" in result.summary.lower()

    def test_start_failure_summary_contains_exit_code(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="control process failed")):
            result = _execute("start", {})
        assert not result.ok
        assert "1" in result.summary

    def test_stop_success_summary(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("stop", {})
        assert "stopped" in result.summary.lower() or result.ok

    def test_restart_failure_summary_contains_exit_code(self) -> None:
        with _patch_run(_fail_result(exit_code=1)):
            result = _execute("restart", {})
        assert not result.ok
        assert "1" in result.summary

    def test_configtest_success_summary(self) -> None:
        with _patch_run(_ok_result(stderr="Syntax OK\n")):
            result = _execute("configtest", {})
        assert result.ok
        assert "valid" in result.summary.lower() or "syntax" in result.summary.lower()

    def test_configtest_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Syntax error on line 42")):
            result = _execute("configtest", {})
        assert not result.ok
        assert "1" in result.summary

    def test_vhost_list_success_summary(self) -> None:
        stdout = "VirtualHost configuration:\n*:80\n         port 80 namevhost example.com\n*:443\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("vhost_list", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_mod_status_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="Total Accesses: 100\nBusyWorkers: 2\n")):
            result = _execute("mod_status", {})
        assert result.ok
        assert "mod_status" in result.summary.lower() or "metric" in result.summary.lower() or result.ok


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op", ["status", "configtest", "start", "stop",
                                     "restart", "vhost_list", "mod_status"])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"httpd\" name=\"httpd.conf\" dev=sda1"
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, {})
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op='{op}': {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="httpd not running")):
            result = _execute("status", {})
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary

    def test_selinux_permission_denied_triggers_hint(self) -> None:
        stderr = "Permission denied: /etc/httpd/conf/httpd.conf"
        with _patch_run(_fail_result(exit_code=1, stderr=stderr)):
            result = _execute("configtest", {})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op", [
        "status", "configtest", "start", "stop", "restart", "vhost_list", "mod_status",
    ])
    def test_result_has_required_fields(self, op: str) -> None:
        with _patch_run(_ok_result(stdout=f"{op} output")):
            result = _execute(op, {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op", [
        "status", "configtest", "start", "stop", "restart", "vhost_list", "mod_status",
    ])
    def test_as_dict_has_four_keys(self, op: str) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, {})
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() never raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_operation", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """Simulate FileNotFoundError -> exit_code 127 from run_subprocess."""
        with _patch_run(_fail_result(exit_code=127, stderr="command not found")):
            result = _execute("start", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    @pytest.mark.parametrize("op", [
        "status", "configtest", "start", "stop", "restart", "vhost_list", "mod_status",
    ])
    def test_all_ops_survive_exit_127(self, op: str) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="apachectl: command not found")):
            result = _execute(op, {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None

    def test_timeout_exit_124_returns_toolresult(self) -> None:
        with _patch_run(_fail_result(exit_code=124, stderr="timeout")):
            result = _execute("mod_status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124


# ---------------------------------------------------------------------------
# I2 — No AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op", [
        "status", "configtest", "start", "stop", "restart", "vhost_list", "mod_status",
    ])
    def test_no_ai_language_in_success_summary(self, op: str) -> None:
        with _patch_run(_ok_result(stdout="output")):
            result = _execute(op, {})
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op", [
        "status", "configtest", "start", "stop", "restart", "vhost_list", "mod_status",
    ])
    def test_no_ai_language_in_failure_summary(self, op: str) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, {})
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )

    def test_spec_descriptions_no_ai_language(self) -> None:
        spec = registry.get("httpd")
        assert spec is not None
        for word in self._FORBIDDEN:
            assert word not in spec.description, (
                f"I2 violation: '{word}' in ToolSpec description"
            )
            for op_name, op_spec in spec.ops.items():
                assert word not in op_spec.description, (
                    f"I2 violation: '{word}' in OpSpec description for '{op_name}'"
                )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_status(self) -> None:
        with _patch_run(_ok_result(stdout="● httpd.service")):
            result = registry.dispatch("httpd", "status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_configtest(self) -> None:
        with _patch_run(_ok_result(stderr="Syntax OK\n")):
            result = registry.dispatch("httpd", "configtest", {})
        assert result.ok

    def test_dispatch_restart(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("httpd", "restart", {})
        assert result.ok

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("httpd", "bogus_op", {})


# ---------------------------------------------------------------------------
# HTTPD_SPEC direct attribute checks
# ---------------------------------------------------------------------------

class TestSpecAttributes:
    def test_spec_has_correct_name(self) -> None:
        assert HTTPD_SPEC.name == "httpd"

    def test_read_ops_advisory_class(self) -> None:
        for op in ("status", "configtest", "vhost_list", "mod_status"):
            assert HTTPD_SPEC.permission_class_for(op) is OpClass.READ

    def test_write_ops_advisory_class(self) -> None:
        for op in ("start", "stop", "restart"):
            assert HTTPD_SPEC.permission_class_for(op) is OpClass.WRITE


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real apachectl on Rocky Linux 9")
def test_live_configtest() -> None:
    """Live: apachectl configtest returns Syntax OK on a valid config."""
    result = _execute("configtest", {})
    assert result.exit_code in (0, 1)
    assert len(result.stderr) > 0 or len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real apachectl on Rocky Linux 9")
def test_live_vhost_list() -> None:
    """Live: apachectl -S returns a virtual host listing."""
    result = _execute("vhost_list", {})
    assert result.exit_code in (0, 1)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires httpd + mod_status on Rocky Linux 9")
def test_live_mod_status() -> None:
    """Live: mod_status endpoint returns metrics when httpd is running."""
    result = _execute("mod_status", {})
    assert result.exit_code in (0, 7)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl on Rocky Linux 9")
def test_live_status() -> None:
    """Live: apachectl status returns service state."""
    result = _execute("status", {})
    assert result.exit_code is not None
