"""tests/test_tools_nginx.py — Unit tests for core/tools/nginx.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without nginx or systemctl present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: configtest/status are READ; start/stop/restart/reload
    are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (nonzero) → ok=False, failure summary.
  * Command vectors: exact argv lists passed to run_subprocess.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2 invariant: no forbidden AI/LLM/model/agent language in any summary.
  * execute() never raises (I9): unknown op and missing binary both return
    a well-formed ToolResult, no exception.
  * ToolResult.as_dict() has exactly the four required keys.
  * DEFERRED-TO-MOSSAD: live execution against real nginx on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.nginx.run_subprocess`` (the function in the nginx
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.nginx  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.nginx import NGINX_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.nginx.run_subprocess."""
    return patch("core.tools.nginx.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_nginx_registered_in_module_registry(self) -> None:
        assert registry.get("nginx") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("nginx")
        assert spec is not None
        assert spec.name == "nginx"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("nginx")
        assert spec is not None
        expected = {"configtest", "status", "start", "stop", "restart", "reload"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["configtest", "status"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nginx", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["start", "stop", "restart", "reload"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nginx", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_configtest_default_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            _execute("configtest", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nginx", "-t"]

    def test_configtest_with_config_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            _execute("configtest", {"config": "/etc/nginx/nginx.conf"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nginx", "-t", "-c", "/etc/nginx/nginx.conf"]

    def test_status_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "status", "--no-pager", "nginx.service"]

    def test_start_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            _execute("start", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "start", "nginx.service"]

    def test_stop_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            _execute("stop", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "stop", "nginx.service"]

    def test_restart_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            _execute("restart", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "restart", "nginx.service"]

    def test_reload_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            _execute("reload", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "reload", "nginx.service"]


# ---------------------------------------------------------------------------
# configtest operation
# ---------------------------------------------------------------------------

class TestConfigtest:
    def test_success_summary(self) -> None:
        with _patch_run(_ok_result(stderr="nginx: configuration file /etc/nginx/nginx.conf test is successful\n")):
            result = _execute("configtest", {})
        assert result.ok
        assert "passed" in result.summary.lower() or "configtest" in result.summary.lower() or "configuration" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="nginx: [emerg] unexpected token in /etc/nginx/nginx.conf:10\n")):
            result = _execute("configtest", {})
        assert not result.ok
        assert result.exit_code == 1
        assert "fail" in result.summary.lower() or "configuration" in result.summary.lower()

    def test_success_with_explicit_config(self) -> None:
        with _patch_run(_ok_result(stderr="nginx: configuration file /tmp/test.conf test is successful\n")):
            result = _execute("configtest", {"config": "/tmp/test.conf"})
        assert result.ok
        assert "/tmp/test.conf" in result.summary

    def test_failure_with_explicit_config(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="nginx: [emerg] syntax error in /tmp/bad.conf:5\n")):
            result = _execute("configtest", {"config": "/tmp/bad.conf"})
        assert not result.ok
        assert "/tmp/bad.conf" in result.summary


# ---------------------------------------------------------------------------
# status operation
# ---------------------------------------------------------------------------

class TestStatus:
    def test_success_summary(self) -> None:
        stdout = (
            "● nginx.service - The nginx HTTP and reverse proxy server\n"
            "     Active: active (running) since Fri 2026-07-03 00:01:04 UTC\n"
        )
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("status", {})
        assert result.ok
        assert "nginx" in result.summary.lower()

    def test_failed_unit_nonzero_exit(self) -> None:
        with _patch_run(_fail_result(exit_code=3, stderr="Unit nginx.service not found")):
            result = _execute("status", {})
        assert not result.ok
        assert result.exit_code == 3
        assert "nginx" in result.summary.lower()

    def test_result_has_stdout(self) -> None:
        with _patch_run(_ok_result(stdout="nginx status output")):
            result = _execute("status", {})
        assert result.stdout == "nginx status output"


# ---------------------------------------------------------------------------
# start operation
# ---------------------------------------------------------------------------

class TestStart:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("start", {})
        assert result.ok
        assert "nginx" in result.summary.lower()
        assert "start" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="failed to start")):
            result = _execute("start", {})
        assert not result.ok
        assert "nginx" in result.summary.lower()
        assert "fail" in result.summary.lower()


# ---------------------------------------------------------------------------
# stop operation
# ---------------------------------------------------------------------------

class TestStop:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("stop", {})
        assert result.ok
        assert "stop" in result.summary.lower() or "nginx" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=5)):
            result = _execute("stop", {})
        assert not result.ok


# ---------------------------------------------------------------------------
# restart operation
# ---------------------------------------------------------------------------

class TestRestart:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("restart", {})
        assert result.ok
        assert "restart" in result.summary.lower() or "nginx" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="dependency failed")):
            result = _execute("restart", {})
        assert not result.ok
        assert "nginx" in result.summary.lower()


# ---------------------------------------------------------------------------
# reload operation
# ---------------------------------------------------------------------------

class TestReload:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("reload", {})
        assert result.ok
        assert "reload" in result.summary.lower() or "nginx" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="control process exited")):
            result = _execute("reload", {})
        assert not result.ok
        assert "nginx" in result.summary.lower()


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op", ["configtest", "status", "start", "stop", "restart", "reload"])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"nginx\" name=\"nginx.service\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, {})
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        )

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Unit not found.")):
            result = _execute("status", {})
        assert "ausearch" not in result.summary

    def test_selinux_hint_not_in_clean_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("start", {})
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestI9NeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert "nonexistent_op" in result.summary or "Unknown" in result.summary

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        mock_fn = MagicMock(
            return_value=ToolResult(exit_code=127, stdout="", stderr="nginx: command not found", summary="")
        )
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            result = _execute("status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_unknown_op_summary_is_nonempty(self) -> None:
        result = _execute("BOGUS", {})
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op", ["configtest", "status", "start", "stop", "restart", "reload"])
    def test_exit_127_handled_for_every_op(self, op: str) -> None:
        mock_fn = MagicMock(
            return_value=ToolResult(exit_code=127, stdout="", stderr="command not found", summary="")
        )
        with patch("core.tools.nginx.run_subprocess", mock_fn):
            result = _execute(op, {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op", [
        "configtest", "status", "start", "stop", "restart", "reload",
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
        "configtest", "status", "start", "stop", "restart", "reload",
    ])
    def test_as_dict_has_four_keys(self, op: str) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, {})
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}

    @pytest.mark.parametrize("op", [
        "configtest", "status", "start", "stop", "restart", "reload",
    ])
    def test_failure_result_structure(self, op: str) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error")):
            result = _execute(op, {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert not result.ok
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# I2 — No AI / model / LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op", [
        "configtest", "status", "start", "stop", "restart", "reload",
    ])
    def test_no_ai_language_in_success_summary(self, op: str) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, {})
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op", [
        "configtest", "status", "start", "stop", "restart", "reload",
    ])
    def test_no_ai_language_in_failure_summary(self, op: str) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, {})
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )

    def test_no_ai_language_in_unknown_op_summary(self) -> None:
        result = _execute("bogus_op", {})
        for word in self._FORBIDDEN:
            assert word not in result.summary


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    """Verify the full router path: registry.dispatch() calls _execute()."""

    def test_dispatch_status(self) -> None:
        with _patch_run(_ok_result(stdout="● nginx.service")):
            result = registry.dispatch("nginx", "status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_configtest(self) -> None:
        with _patch_run(_ok_result(stderr="syntax is ok\n")):
            result = registry.dispatch("nginx", "configtest", {})
        assert result.ok

    def test_dispatch_start(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("nginx", "start", {})
        assert result.ok

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("nginx", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nginx on Rocky Linux 9")
def test_live_configtest() -> None:
    """Live: nginx -t returns 0 when config is valid."""
    result = _execute("configtest", {})
    assert result.exit_code == 0
    assert "ok" in result.stderr.lower() or "successful" in result.stderr.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl on Rocky Linux 9")
def test_live_status() -> None:
    """Live: systemctl status nginx.service returns a populated ToolResult."""
    result = _execute("status", {})
    assert result.exit_code in (0, 3, 4)  # 0=active, 3=inactive/failed, 4=not-found
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl + sudo on Rocky Linux 9")
def test_live_reload_requires_running_nginx() -> None:
    """Live: systemctl reload nginx.service requires nginx to be running."""
    result = _execute("reload", {})
    assert result.exit_code is not None
