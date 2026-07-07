"""tests/test_tools_subscription.py — Unit tests for core/tools/subscription.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without subscription-manager present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/list are READ; register/repos_enable/repos_disable
    are WRITE; unregister is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful I2-clean summary.
  * Failed exit (nonzero) → ok=False, failure summary naming the object.
  * SELinux AVC hint surfaces in summary when stderr contains AVC language.
  * execute() NEVER raises (I9) — unknown ops and missing binary (exit 127)
    both return well-formed ToolResult.
  * Command vectors: argv list passed to run_subprocess is correct for each op.
  * DEFERRED-TO-MOSSAD: live execution against real subscription-manager.

Mocking strategy
----------------
  Patch ``core.tools.subscription.run_subprocess`` (the function in the
  subscription module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.subscription  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.subscription import SUBSCRIPTION_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.subscription.run_subprocess with a fixed return value."""
    return patch("core.tools.subscription.run_subprocess", return_value=return_value)


def _patch_fn(fn: Any):
    """Patch with a callable mock."""
    return patch("core.tools.subscription.run_subprocess", side_effect=fn)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered(self) -> None:
        assert registry.get("subscription") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("subscription")
        assert spec is not None
        assert spec.name == "subscription"

    def test_all_ops_present(self) -> None:
        spec = registry.get("subscription")
        assert spec is not None
        expected = {"status", "list", "register", "unregister", "repos_enable", "repos_disable"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "list"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("subscription", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["register", "repos_enable", "repos_disable"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("subscription", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_unregister_is_destructive(self) -> None:
        cls = registry.permission_class_for("subscription", "unregister")
        assert cls is OpClass.DESTRUCTIVE

    def test_spec_permission_class_for(self) -> None:
        assert SUBSCRIPTION_SPEC.permission_class_for("unregister") is OpClass.DESTRUCTIVE
        assert SUBSCRIPTION_SPEC.permission_class_for("status") is OpClass.READ


# ---------------------------------------------------------------------------
# Command vector tests
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_status_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["subscription-manager", "status"]

    def test_list_consumed_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("list", {"what": "consumed"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["subscription-manager", "list", "--consumed"]

    def test_list_available_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("list", {"what": "available"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["subscription-manager", "list", "--available"]

    def test_list_default_is_consumed(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("list", {})
        argv = mock_fn.call_args[0][0]
        assert "--consumed" in argv

    def test_register_username_password_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("register", {"username": "admin", "password": "secret", "org": "MyOrg"})
        argv = mock_fn.call_args[0][0]
        assert "subscription-manager" in argv
        assert "register" in argv
        assert "--username" in argv
        assert "admin" in argv
        assert "--password" in argv
        assert "secret" in argv
        assert "--org" in argv
        assert "MyOrg" in argv

    def test_register_activationkey_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("register", {"activationkey": "mykey", "org": "MyOrg"})
        argv = mock_fn.call_args[0][0]
        assert "--activationkey" in argv
        assert "mykey" in argv
        assert "--org" in argv

    def test_unregister_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("unregister", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["subscription-manager", "unregister"]

    def test_repos_enable_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("repos_enable", {"repo": "rhel-9-for-x86_64-baseos-rpms"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "subscription-manager"
        assert argv[1] == "repos"
        assert "--enable=rhel-9-for-x86_64-baseos-rpms" in argv

    def test_repos_disable_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.subscription.run_subprocess", mock_fn):
            _execute("repos_disable", {"repo": "rhel-9-for-x86_64-appstream-rpms"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "subscription-manager"
        assert argv[1] == "repos"
        assert "--disable=rhel-9-for-x86_64-appstream-rpms" in argv


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_status_success(self) -> None:
        with _patch(_ok(stdout="Overall Status: Current")):
            result = _execute("status", {})
        assert result.ok
        assert "status" in result.summary.lower() or "subscription" in result.summary.lower()

    def test_status_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="not registered")):
            result = _execute("status", {})
        assert not result.ok
        assert result.exit_code == 1

    def test_list_success(self) -> None:
        with _patch(_ok(stdout="Subscription Name: RHEL")):
            result = _execute("list", {"what": "consumed"})
        assert result.ok
        assert "consumed" in result.summary.lower()

    def test_list_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="not registered")):
            result = _execute("list", {"what": "consumed"})
        assert not result.ok
        assert "consumed" in result.summary.lower()

    def test_register_success(self) -> None:
        with _patch(_ok(stdout="System has been registered")):
            result = _execute("register", {"username": "u", "password": "p"})
        assert result.ok
        assert "registered" in result.summary.lower()

    def test_register_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Invalid credentials")):
            result = _execute("register", {"username": "bad", "password": "wrong"})
        assert not result.ok
        assert result.exit_code == 1
        assert "registration failed" in result.summary.lower() or "failed" in result.summary.lower()

    def test_unregister_success(self) -> None:
        with _patch(_ok(stdout="System has been unregistered.")):
            result = _execute("unregister", {})
        assert result.ok
        assert "unregistered" in result.summary.lower()
        assert "entitlement" in result.summary.lower()

    def test_unregister_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="not registered")):
            result = _execute("unregister", {})
        assert not result.ok
        assert result.exit_code == 1
        assert "unregistration failed" in result.summary.lower() or "failed" in result.summary.lower()

    def test_repos_enable_success(self) -> None:
        with _patch(_ok(stdout="Repository 'rhel-9-for-x86_64-baseos-rpms' is enabled")):
            result = _execute("repos_enable", {"repo": "rhel-9-for-x86_64-baseos-rpms"})
        assert result.ok
        assert "rhel-9-for-x86_64-baseos-rpms" in result.summary
        assert "enabled" in result.summary.lower()

    def test_repos_enable_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="not allowed")):
            result = _execute("repos_enable", {"repo": "bogus-repo-id"})
        assert not result.ok
        assert "bogus-repo-id" in result.summary

    def test_repos_disable_success(self) -> None:
        with _patch(_ok(stdout="Repository 'rhel-9-for-x86_64-appstream-rpms' is disabled")):
            result = _execute("repos_disable", {"repo": "rhel-9-for-x86_64-appstream-rpms"})
        assert result.ok
        assert "rhel-9-for-x86_64-appstream-rpms" in result.summary
        assert "disabled" in result.summary.lower()

    def test_repos_disable_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="not allowed")):
            result = _execute("repos_disable", {"repo": "missing-repo-x"})
        assert not result.ok
        assert "missing-repo-x" in result.summary


# ---------------------------------------------------------------------------
# I2-clean summaries (TestNoAILanguage)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in any user-facing string."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("list",          {"what": "consumed"}),
        ("list",          {"what": "available"}),
        ("register",      {"username": "u", "password": "p"}),
        ("unregister",    {}),
        ("repos_enable",  {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
        ("repos_disable", {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="ok")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("list",          {"what": "consumed"}),
        ("register",      {"username": "u", "password": "p"}),
        ("unregister",    {}),
        ("repos_enable",  {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
        ("repos_disable", {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# SELinux hint
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("list",          {"what": "consumed"}),
        ("register",      {"username": "u", "password": "p"}),
        ("unregister",    {}),
        ("repos_enable",  {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
        ("repos_disable", {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 comm=\"subscription-manager\" "
            "scontext=system_u:system_r:unconfined_t:s0 tcontext=system_u:object_r:cert_t:s0"
        )
        with _patch(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"Expected SELinux hint for op='{op}', got: {result.summary!r}"
        )

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="This system is not yet registered.")):
            result = _execute("status", {})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("list",          {"what": "consumed"}),
        ("list",          {"what": "available"}),
        ("register",      {"username": "u", "password": "p"}),
        ("unregister",    {}),
        ("repos_enable",  {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
        ("repos_disable", {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
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
        ("status",        {}),
        ("list",          {}),
        ("register",      {"username": "u", "password": "p"}),
        ("unregister",    {}),
        ("repos_enable",  {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
        ("repos_disable", {"repo": "rhel-9-for-x86_64-baseos-rpms"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9: execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        # No patch needed — unknown op returns before calling run_subprocess
        result = _execute("bogus_operation", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "bogus_operation" in result.summary
        assert "Unknown operation" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        # Simulate subscription-manager not installed (exit 127)
        with _patch(_fail(exit_code=127, stderr="subscription-manager: command not found")):
            result = _execute("status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_unregister_exit_127(self) -> None:
        with _patch(_fail(exit_code=127, stderr="subscription-manager: command not found")):
            result = _execute("unregister", {})
        assert isinstance(result, ToolResult)
        assert not result.ok

    def test_repos_enable_no_exception(self) -> None:
        with _patch(_fail(exit_code=1, stderr="error")):
            result = _execute("repos_enable", {"repo": "some-repo-id"})
        assert isinstance(result, ToolResult)

    def test_register_no_args_no_exception(self) -> None:
        # All register args are optional — should not raise even with empty args
        with _patch(_fail(exit_code=1, stderr="must provide username")):
            result = _execute("register", {})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_status(self) -> None:
        with _patch(_ok(stdout="Overall Status: Current")):
            result = registry.dispatch("subscription", "status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_repos_enable_missing_repo_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'repo'"):
            registry.dispatch("subscription", "repos_enable", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("subscription", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires subscription-manager on Rocky Linux 9")
def test_live_status() -> None:
    """Live: subscription-manager status returns a populated ToolResult."""
    result = _execute("status", {})
    assert result.exit_code in (0, 1)
    assert len(result.summary) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires subscription-manager on Rocky Linux 9")
def test_live_list_consumed() -> None:
    """Live: subscription-manager list --consumed returns output."""
    result = _execute("list", {"what": "consumed"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real subscription-manager and credentials")
def test_live_register_requires_credentials() -> None:
    """Live: registration without credentials should fail cleanly."""
    result = _execute("register", {})
    assert not result.ok
    assert len(result.summary) > 0
