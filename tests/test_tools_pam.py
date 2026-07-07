"""tests/test_tools_pam.py — Unit tests for core/tools/pam.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without pam utilities or pam.d files present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: pamd_audit/faillock_status are READ;
    faillock_reset/pam_auth_update are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful I2-clean summary.
  * Failed exit (exit_code!=0) → ok=False, failure summary with exit code.
  * Command vectors are exactly correct (argv lists, not shell strings).
  * SELinux AVC hint surfaces when stderr contains AVC language.
  * execute() NEVER raises — unknown op and exit 127 both degrade cleanly (I9).
  * No AI/LLM/model/agent language in any summary (I2).
  * DEFERRED-TO-MOSSAD: live execution tests requiring real pam utilities.

Mocking strategy
----------------
  We patch ``core.tools.pam.run_subprocess`` (the binding in the pam module's
  namespace) to return controlled ToolResult fixtures. This intercepts all
  subprocess calls without touching the real system.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.pam  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.pam import PAM_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.pam.run_subprocess with a fixed return value."""
    return patch("core.tools.pam.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_pam_registered(self) -> None:
        assert registry.get("pam") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("pam")
        assert spec is not None
        assert spec.name == "pam"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("pam")
        assert spec is not None
        expected = {"pamd_audit", "faillock_status", "faillock_reset", "pam_auth_update"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["pamd_audit", "faillock_status"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("pam", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["faillock_reset", "pam_auth_update"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("pam", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_spec_permission_class_for_matches_registry(self) -> None:
        for op in ("pamd_audit", "faillock_status", "faillock_reset", "pam_auth_update"):
            assert PAM_SPEC.permission_class_for(op) == registry.permission_class_for("pam", op)


# ---------------------------------------------------------------------------
# Command vector tests
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_pamd_audit_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="#%PAM-1.0\n"))
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("pamd_audit", {"service": "sshd"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["cat", "/etc/pam.d/sshd"]

    def test_pamd_audit_vector_sudo(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="#%PAM-1.0\n"))
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("pamd_audit", {"service": "sudo"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["cat", "/etc/pam.d/sudo"]

    def test_faillock_status_no_user_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="alice:\n"))
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("faillock_status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["faillock"]

    def test_faillock_status_with_user_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="alice:\n"))
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("faillock_status", {"user": "alice"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["faillock", "--user", "alice"]

    def test_faillock_reset_no_user_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("faillock_reset", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["faillock", "--reset"]

    def test_faillock_reset_with_user_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("faillock_reset", {"user": "bob"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["faillock", "--user", "bob", "--reset"]

    def test_pam_auth_update_enable_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Enabling mkhomedir\n"))
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("pam_auth_update", {"profile": "mkhomedir", "action": "enable"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["pam-auth-update", "--enable", "mkhomedir"]

    def test_pam_auth_update_disable_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Disabling pwquality\n"))
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("pam_auth_update", {"profile": "pwquality", "action": "disable"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["pam-auth-update", "--disable", "pwquality"]

    def test_pam_auth_update_default_action_is_enable(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.pam.run_subprocess", mock_fn):
            _execute("pam_auth_update", {"profile": "mkhomedir"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["pam-auth-update", "--enable", "mkhomedir"]


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure branches
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_pamd_audit_success(self) -> None:
        with _patch(_ok(stdout="#%PAM-1.0\nauth required pam_unix.so\n")):
            result = _execute("pamd_audit", {"service": "sshd"})
        assert result.ok
        assert result.exit_code == 0
        assert "sshd" in result.summary

    def test_pamd_audit_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="cat: /etc/pam.d/ghost: No such file or directory")):
            result = _execute("pamd_audit", {"service": "ghost"})
        assert not result.ok
        assert result.exit_code == 1
        assert "ghost" in result.summary
        assert "1" in result.summary

    def test_faillock_status_success_no_user(self) -> None:
        with _patch(_ok(stdout="alice:\n")):
            result = _execute("faillock_status", {})
        assert result.ok
        assert "tallies" in result.summary.lower() or "retrieved" in result.summary.lower()

    def test_faillock_status_success_with_user(self) -> None:
        with _patch(_ok(stdout="alice:\n")):
            result = _execute("faillock_status", {"user": "alice"})
        assert result.ok
        assert "alice" in result.summary

    def test_faillock_status_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Permission denied")):
            result = _execute("faillock_status", {"user": "alice"})
        assert not result.ok
        assert "alice" in result.summary

    def test_faillock_reset_success(self) -> None:
        with _patch(_ok()):
            result = _execute("faillock_reset", {"user": "alice"})
        assert result.ok
        assert "alice" in result.summary
        assert "reset" in result.summary.lower()

    def test_faillock_reset_success_all_users(self) -> None:
        with _patch(_ok()):
            result = _execute("faillock_reset", {})
        assert result.ok
        assert "reset" in result.summary.lower()

    def test_faillock_reset_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="user not found")):
            result = _execute("faillock_reset", {"user": "ghost"})
        assert not result.ok
        assert "ghost" in result.summary
        assert "1" in result.summary

    def test_pam_auth_update_success(self) -> None:
        with _patch(_ok(stdout="Enabling mkhomedir\n")):
            result = _execute("pam_auth_update", {"profile": "mkhomedir"})
        assert result.ok
        assert "mkhomedir" in result.summary

    def test_pam_auth_update_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="profile not found")):
            result = _execute("pam_auth_update", {"profile": "bad_profile"})
        assert not result.ok
        assert "bad_profile" in result.summary
        assert "1" in result.summary

    def test_pam_auth_update_invalid_action_no_subprocess(self) -> None:
        # Invalid action must NOT call run_subprocess at all; returns cleanly.
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.pam.run_subprocess", mock_fn):
            result = _execute("pam_auth_update", {"profile": "mkhomedir", "action": "nuke"})
        assert not result.ok
        mock_fn.assert_not_called()
        assert "nuke" in result.summary


# ---------------------------------------------------------------------------
# I2 — no AI / model / LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("pamd_audit",      {"service": "sshd"}),
        ("faillock_status", {}),
        ("faillock_status", {"user": "alice"}),
        ("faillock_reset",  {}),
        ("faillock_reset",  {"user": "alice"}),
        ("pam_auth_update", {"profile": "mkhomedir"}),
        ("pam_auth_update", {"profile": "mkhomedir", "action": "disable"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="output\n")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("pamd_audit",      {"service": "sshd"}),
        ("faillock_status", {"user": "alice"}),
        ("faillock_reset",  {"user": "alice"}),
        ("pam_auth_update", {"profile": "mkhomedir"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "AVC avc: denied { read } for pid=1234 "
        "comm=\"faillock\" scontext=system_u:system_r:crond_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("pamd_audit",      {"service": "sshd"}),
        ("faillock_status", {}),
        ("faillock_status", {"user": "alice"}),
        ("faillock_reset",  {}),
        ("faillock_reset",  {"user": "alice"}),
        ("pam_auth_update", {"profile": "mkhomedir"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"SELinux hint missing for op='{op}': {result.summary!r}"
        )

    @pytest.mark.parametrize("op,args", [
        ("pamd_audit",      {"service": "sshd"}),
        ("faillock_status", {}),
        ("faillock_reset",  {"user": "alice"}),
        ("pam_auth_update", {"profile": "mkhomedir"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="Unit not found.")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"Spurious SELinux hint for op='{op}': {result.summary!r}"
        )


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("pamd_audit",      {"service": "sshd"}),
        ("faillock_status", {}),
        ("faillock_status", {"user": "alice"}),
        ("faillock_reset",  {}),
        ("faillock_reset",  {"user": "alice"}),
        ("pam_auth_update", {"profile": "mkhomedir"}),
        ("pam_auth_update", {"profile": "mkhomedir", "action": "disable"}),
    ])
    def test_result_fields(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("pamd_audit",      {"service": "sshd"}),
        ("faillock_status", {}),
        ("faillock_reset",  {}),
        ("pam_auth_update", {"profile": "mkhomedir"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestI9NeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        """Unknown op must return a ToolResult, not raise."""
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert len(result.summary) > 0
        assert "nonexistent_op" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        """run_subprocess returning exit 127 (binary not found) degrades cleanly."""
        no_binary = ToolResult(exit_code=127, stdout="", stderr="command not found", summary="")
        with patch("core.tools.pam.run_subprocess", return_value=no_binary):
            result = _execute("pamd_audit", {"service": "sshd"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_missing_binary_faillock(self) -> None:
        no_binary = ToolResult(exit_code=127, stdout="", stderr="faillock: command not found", summary="")
        with patch("core.tools.pam.run_subprocess", return_value=no_binary):
            result = _execute("faillock_status", {"user": "alice"})
        assert isinstance(result, ToolResult)
        assert not result.ok

    def test_missing_binary_pam_auth_update(self) -> None:
        no_binary = ToolResult(exit_code=127, stdout="", stderr="pam-auth-update: not found", summary="")
        with patch("core.tools.pam.run_subprocess", return_value=no_binary):
            result = _execute("pam_auth_update", {"profile": "mkhomedir"})
        assert isinstance(result, ToolResult)
        assert not result.ok

    def test_no_raise_on_timeout_exit_124(self) -> None:
        timeout_result = ToolResult(exit_code=124, stdout="", stderr="", summary="")
        with patch("core.tools.pam.run_subprocess", return_value=timeout_result):
            result = _execute("pamd_audit", {"service": "sshd"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_pamd_audit(self) -> None:
        with _patch(_ok(stdout="#%PAM-1.0\n")):
            result = registry.dispatch("pam", "pamd_audit", {"service": "sshd"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_faillock_status(self) -> None:
        with _patch(_ok(stdout="alice:\n")):
            result = registry.dispatch("pam", "faillock_status", {})
        assert result.ok

    def test_dispatch_faillock_reset_with_user(self) -> None:
        with _patch(_ok()):
            result = registry.dispatch("pam", "faillock_reset", {"user": "alice"})
        assert result.ok

    def test_dispatch_pam_auth_update(self) -> None:
        with _patch(_ok(stdout="Enabling mkhomedir\n")):
            result = registry.dispatch("pam", "pam_auth_update", {"profile": "mkhomedir"})
        assert result.ok

    def test_dispatch_pamd_audit_missing_service_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'service'"):
            registry.dispatch("pam", "pamd_audit", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("pam", "no_such_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires /etc/pam.d/ on Rocky Linux 9")
def test_live_pamd_audit_sshd() -> None:
    """Live: read /etc/pam.d/sshd and return non-empty stdout."""
    result = _execute("pamd_audit", {"service": "sshd"})
    assert result.exit_code == 0
    assert len(result.stdout) > 0
    assert "#%PAM-1.0" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires faillock binary on Rocky Linux 9")
def test_live_faillock_status() -> None:
    """Live: faillock returns tally output with exit 0."""
    result = _execute("faillock_status", {})
    assert result.exit_code == 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires pam-auth-update and elevated privileges on Rocky Linux 9")
def test_live_pam_auth_update_enable() -> None:
    """Live: pam-auth-update --enable mkhomedir must succeed as root."""
    result = _execute("pam_auth_update", {"profile": "mkhomedir", "action": "enable"})
    assert result.exit_code == 0
