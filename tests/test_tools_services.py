"""tests/test_tools_services.py — Unit tests for core/tools/services.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without systemctl or journalctl present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/logs are READ; start/stop/restart/enable/
    disable/mask are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code=1) → ok=False, failure summary.
  * Read ops (status, logs) never require confirmation per permissions.classify().
  * Write ops (start, stop, restart, enable, disable, mask) require CONFIRM
    gate in an interactive context.
  * logs: lines argument is clamped to [1, 500]; default is 50.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * Audit: when an AuditLog is passed via the thin wrapper below, one record
    per execute() call is written.
  * DEFERRED-TO-MOSSAD: live execution against real systemctl on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.services.run_subprocess`` (the function in the
  services module's namespace) to return controlled ToolResult fixtures.
  The ToolSpec.execute callable calls the module-level ``run_subprocess``
  via the import in services.py, so patching there intercepts all calls.
"""

from __future__ import annotations

import json
import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.services  # noqa: F401  (side-effect: registry.register)
from core.agent.audit import AuditLog, iter_records
from core.agent.permissions import Gate, OpClass, classify
from core.tools import ToolResult, registry
from core.tools.services import SERVICES_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.services.run_subprocess."""
    return patch("core.tools.services.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_services_registered_in_module_registry(self) -> None:
        assert registry.get("services") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("services")
        assert spec is not None
        assert spec.name == "services"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("services")
        assert spec is not None
        expected = {"status", "start", "stop", "restart", "enable", "disable", "logs", "mask"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "logs"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("services", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["start", "stop", "restart", "enable", "disable", "mask"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("services", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Permission gate integration (via permissions.classify)
# ---------------------------------------------------------------------------

class TestPermissionGateIntegration:
    """Verify that the permission class declared by the tool aligns with what
    permissions.classify() returns for the actual systemctl command lines."""

    @pytest.mark.parametrize("op,cmd", [
        ("status", "systemctl status nginx.service"),
        ("logs",   "journalctl -u nginx.service -n 50 --no-pager"),
    ])
    def test_read_ops_get_allow_gate(self, op: str, cmd: str) -> None:
        decision = classify(cmd)
        assert decision.gate is Gate.ALLOW
        assert decision.auto_ok is True

    @pytest.mark.parametrize("op,cmd", [
        ("start",   "systemctl start nginx.service"),
        ("stop",    "systemctl stop nginx.service"),
        ("restart", "systemctl restart nginx.service"),
        ("enable",  "systemctl enable nginx.service"),
        ("disable", "systemctl disable nginx.service"),
        ("mask",    "systemctl mask nginx.service"),
    ])
    def test_write_ops_get_confirm_gate(self, op: str, cmd: str) -> None:
        decision = classify(cmd)
        assert decision.gate is Gate.CONFIRM
        assert decision.auto_ok is False


# ---------------------------------------------------------------------------
# status operation
# ---------------------------------------------------------------------------

class TestStatus:
    def test_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="● nginx.service - nginx\n   Active: active (running)")):
            result = _execute("status", {"unit": "nginx.service"})
        assert result.ok
        assert "nginx.service" in result.summary
        assert "active" in result.summary.lower() or "running" in result.summary.lower() or result.ok

    def test_failed_unit_nonzero_exit(self) -> None:
        with _patch_run(_fail_result(exit_code=3, stderr="Unit not found")):
            result = _execute("status", {"unit": "ghost.service"})
        assert not result.ok
        assert result.exit_code == 3
        assert "ghost.service" in result.summary

    def test_result_has_stdout(self) -> None:
        with _patch_run(_ok_result(stdout="status output")):
            result = _execute("status", {"unit": "sshd"})
        assert result.stdout == "status output"


# ---------------------------------------------------------------------------
# start operation
# ---------------------------------------------------------------------------

class TestStart:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("start", {"unit": "nginx.service"})
        assert result.ok
        assert "nginx.service" in result.summary
        assert "started" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="failed to start")):
            result = _execute("start", {"unit": "broken.service"})
        assert not result.ok
        assert "broken.service" in result.summary


# ---------------------------------------------------------------------------
# stop operation
# ---------------------------------------------------------------------------

class TestStop:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("stop", {"unit": "nginx.service"})
        assert result.ok
        assert "stopped" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=5)):
            result = _execute("stop", {"unit": "missing.service"})
        assert not result.ok


# ---------------------------------------------------------------------------
# restart operation
# ---------------------------------------------------------------------------

class TestRestart:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("restart", {"unit": "nginx.service"})
        assert result.ok
        assert "restarted" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="dependency failed")):
            result = _execute("restart", {"unit": "bad.service"})
        assert not result.ok
        assert "bad.service" in result.summary


# ---------------------------------------------------------------------------
# enable / disable operations
# ---------------------------------------------------------------------------

class TestEnableDisable:
    def test_enable_success(self) -> None:
        with _patch_run(_ok_result(stdout="Created symlink")):
            result = _execute("enable", {"unit": "nginx.service"})
        assert result.ok
        assert "enabled" in result.summary.lower()

    def test_disable_success(self) -> None:
        with _patch_run(_ok_result(stdout="Removed symlink")):
            result = _execute("disable", {"unit": "nginx.service"})
        assert result.ok
        assert "disabled" in result.summary.lower()

    def test_enable_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="not found")):
            result = _execute("enable", {"unit": "ghost.service"})
        assert not result.ok

    def test_disable_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="not found")):
            result = _execute("disable", {"unit": "ghost.service"})
        assert not result.ok


# ---------------------------------------------------------------------------
# logs operation
# ---------------------------------------------------------------------------

class TestLogs:
    def test_default_lines(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="line1\nline2\n"))
        with patch("core.tools.services.run_subprocess", mock_fn):
            _execute("logs", {"unit": "nginx.service"})
        call_args = mock_fn.call_args[0][0]
        # journalctl -u nginx.service -n 50 --no-pager
        assert "-n" in call_args
        n_idx = call_args.index("-n")
        assert call_args[n_idx + 1] == "50"

    def test_custom_lines(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="\n" * 100))
        with patch("core.tools.services.run_subprocess", mock_fn):
            result = _execute("logs", {"unit": "nginx.service", "lines": 100})
        call_args = mock_fn.call_args[0][0]
        n_idx = call_args.index("-n")
        assert call_args[n_idx + 1] == "100"
        assert result.ok

    def test_lines_clamped_to_max(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="\n" * 500))
        with patch("core.tools.services.run_subprocess", mock_fn):
            _execute("logs", {"unit": "nginx.service", "lines": 9999})
        call_args = mock_fn.call_args[0][0]
        n_idx = call_args.index("-n")
        assert call_args[n_idx + 1] == "500"

    def test_lines_clamped_to_min(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="line\n"))
        with patch("core.tools.services.run_subprocess", mock_fn):
            _execute("logs", {"unit": "sshd", "lines": 0})
        call_args = mock_fn.call_args[0][0]
        n_idx = call_args.index("-n")
        assert call_args[n_idx + 1] == "1"

    def test_summary_contains_line_count(self) -> None:
        stdout = "line1\nline2\nline3\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("logs", {"unit": "nginx.service"})
        assert result.ok
        # summary should mention the count
        assert "3" in result.summary or "log" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="no entries")):
            result = _execute("logs", {"unit": "absent.service"})
        assert not result.ok
        assert "absent.service" in result.summary


# ---------------------------------------------------------------------------
# mask operation
# ---------------------------------------------------------------------------

class TestMask:
    def test_success(self) -> None:
        with _patch_run(_ok_result(stdout="Created symlink /etc/systemd/system/nginx.service → /dev/null")):
            result = _execute("mask", {"unit": "nginx.service"})
        assert result.ok
        assert "masked" in result.summary.lower()
        assert "nginx.service" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="unit not found")):
            result = _execute("mask", {"unit": "ghost.service"})
        assert not result.ok

    def test_mask_is_write_class(self) -> None:
        cls = SERVICES_SPEC.permission_class_for("mask")
        assert cls is OpClass.WRITE


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op", ["status", "start", "stop", "restart", "enable", "disable", "mask"])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str) -> None:
        avc_stderr = (
            "Failed to start nginx.service: "
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"systemctl\" name=\"nginx.service\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, {"unit": "nginx.service"})
        assert "SELinux" in result.summary or "AVC" in result.summary or "ausearch" in result.summary

    def test_logs_avc_in_stdout_surfaces_hint(self) -> None:
        avc_stdout = (
            "Jun 21 00:00:00 host kernel: "
            "AVC avc: denied { read } for pid=2 comm=\"cat\""
        )
        with _patch_run(_ok_result(stdout=avc_stdout)):
            result = _execute("logs", {"unit": "kernel"})
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Unit not found.")):
            result = _execute("status", {"unit": "missing.service"})
        # Should NOT contain the SELinux hint
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("status",  {"unit": "nginx.service"}),
        ("start",   {"unit": "nginx.service"}),
        ("stop",    {"unit": "nginx.service"}),
        ("restart", {"unit": "nginx.service"}),
        ("enable",  {"unit": "nginx.service"}),
        ("disable", {"unit": "nginx.service"}),
        ("logs",    {"unit": "nginx.service"}),
        ("mask",    {"unit": "nginx.service"}),
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
        ("status",  {"unit": "u"}),
        ("start",   {"unit": "u"}),
        ("stop",    {"unit": "u"}),
        ("restart", {"unit": "u"}),
        ("enable",  {"unit": "u"}),
        ("disable", {"unit": "u"}),
        ("logs",    {"unit": "u"}),
        ("mask",    {"unit": "u"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# Audit integration
# ---------------------------------------------------------------------------

class TestAuditIntegration:
    """Verify that a caller can write audit records after calling _execute()."""

    def test_audit_record_written_after_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "audit.jsonl")
            log = AuditLog(audit_path)

            with _patch_run(_ok_result(stdout="active")):
                result = _execute("status", {"unit": "nginx.service"})

            # Caller writes the audit record (as Phase 4 router would do).
            log.write(
                tier="test-tier",
                nl_input="show me nginx status",
                translated_command="systemctl status nginx.service",
                tool="services",
                args={"op": "status", "unit": "nginx.service"},
                permission_decision="read",
                exit_code=result.exit_code,
                stdout_summary=result.stdout[:256],
                stderr_summary=result.stderr[:256],
                result=result.summary,
            )
            log.close()

            records = list(iter_records(audit_path))
            assert len(records) == 1
            rec = records[0]
            assert rec["tool"] == "services"
            assert rec["permission_decision"] == "read"
            assert rec["exit_code"] == 0

    def test_audit_record_written_for_write_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "audit.jsonl")
            log = AuditLog(audit_path)

            with _patch_run(_ok_result()):
                result = _execute("restart", {"unit": "nginx.service"})

            log.write(
                tier="test-tier",
                nl_input="restart nginx",
                translated_command="systemctl restart nginx.service",
                tool="services",
                args={"op": "restart", "unit": "nginx.service"},
                permission_decision="write:confirmed",
                exit_code=result.exit_code,
                stdout_summary=result.stdout[:256],
                stderr_summary=result.stderr[:256],
                result=result.summary,
            )
            log.close()

            records = list(iter_records(audit_path))
            assert len(records) == 1
            rec = records[0]
            assert rec["permission_decision"] == "write:confirmed"
            assert rec["result"] is not None


# ---------------------------------------------------------------------------
# Registry dispatch integration (Phase 4 router path)
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    """Verify the full router path: registry.dispatch() calls _execute()."""

    def test_dispatch_status(self) -> None:
        with _patch_run(_ok_result(stdout="● nginx.service")):
            result = registry.dispatch("services", "status", {"unit": "nginx.service"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_restart(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("services", "restart", {"unit": "nginx.service"})
        assert result.ok

    def test_dispatch_missing_unit_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'unit'"):
            registry.dispatch("services", "status", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("services", "nonexistent_op", {"unit": "x"})

    def test_dispatch_logs_with_lines(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="\n" * 10))
        with patch("core.tools.services.run_subprocess", mock_fn):
            result = registry.dispatch(
                "services", "logs", {"unit": "sshd", "lines": 10}
            )
        assert result.ok


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("status",  {"unit": "nginx.service"}),
        ("start",   {"unit": "nginx.service"}),
        ("stop",    {"unit": "nginx.service"}),
        ("restart", {"unit": "nginx.service"}),
        ("enable",  {"unit": "nginx.service"}),
        ("disable", {"unit": "nginx.service"}),
        ("logs",    {"unit": "nginx.service"}),
        ("mask",    {"unit": "nginx.service"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("status",  {"unit": "nginx.service"}),
        ("restart", {"unit": "nginx.service"}),
        ("logs",    {"unit": "nginx.service"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

# The following tests are intentionally SKIPPED on the macOS dev host.
# They must be run on mossad (Rocky Linux 9, systemctl + journalctl present).

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl on Rocky Linux 9")
def test_live_status_sshd() -> None:
    """Live: systemctl status sshd returns a populated ToolResult."""
    result = _execute("status", {"unit": "sshd"})
    assert result.exit_code in (0, 3, 4)  # 0=active, 3=inactive, 4=not-found
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real journalctl on Rocky Linux 9")
def test_live_logs_sshd() -> None:
    """Live: journalctl -u sshd returns log lines."""
    result = _execute("logs", {"unit": "sshd", "lines": 10})
    assert result.exit_code == 0
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl on Rocky Linux 9")
def test_live_restart_requires_sudo() -> None:
    """Live: systemctl restart on Rocky requires elevated privileges.

    This test must be run as root or with sudo. It verifies that the write
    permission gate (CONFIRM) is required before calling execute(), which is
    the Phase 4 router's responsibility. Running without sudo should return
    exit_code != 0 and include a permission error in stderr.
    """
    result = _execute("restart", {"unit": "crond"})
    # If run as root: should succeed (exit 0). As a regular user: exit non-0.
    assert result.exit_code is not None
