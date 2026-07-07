"""tests/test_tools_quota.py — Unit tests for core/tools/quota.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without repquota, quota, quotaon, quotaoff,
quotacheck, or setquota present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: repquota/quota_user are READ; quotaon/quotaoff/
    quotacheck/edquota are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> not ok, failure summary naming the object.
  * Command vectors: exact argv lists passed to run_subprocess.
  * SELinux AVC hint surfaced in summary when stderr contains AVC language.
  * No AI/LLM/model/agent language in any summary (I2).
  * execute() NEVER raises (I9): unknown ops and missing binaries (exit 127)
    degrade to well-formed ToolResult.
  * DEFERRED-TO-MOSSAD: live execution against real quota utilities on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.quota.run_subprocess`` (the function in the quota
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration
import core.tools.quota  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.quota import QUOTA_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.quota.run_subprocess."""
    return patch("core.tools.quota.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_quota_registered(self) -> None:
        assert registry.get("quota") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("quota")
        assert spec is not None
        assert spec.name == "quota"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("quota")
        assert spec is not None
        expected = {"repquota", "quota_user", "quotaon", "quotaoff", "quotacheck", "edquota"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["repquota", "quota_user"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("quota", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["quotaon", "quotaoff", "quotacheck", "edquota"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("quota", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_repquota_specific_filesystem(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="quota report"))
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("repquota", {"filesystem": "/home"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["repquota", "-s", "/home"]

    def test_repquota_all_filesystems(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="quota report"))
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("repquota", {"filesystem": "-a"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["repquota", "-a", "-s"]

    def test_repquota_default_is_all(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="quota report"))
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("repquota", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["repquota", "-a", "-s"]

    def test_quota_user_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="alice quotas"))
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("quota_user", {"username": "alice"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["quota", "-u", "alice"]

    def test_quotaon_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="quotas turned on"))
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("quotaon", {"filesystem": "/home"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["quotaon", "-v", "/home"]

    def test_quotaoff_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="quotas turned off"))
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("quotaoff", {"filesystem": "/home"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["quotaoff", "-v", "/home"]

    def test_quotacheck_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Scanning done"))
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("quotacheck", {"filesystem": "/home"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["quotacheck", "-ugm", "/home"]

    def test_edquota_argv_defaults(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("edquota", {"username": "alice", "filesystem": "/home"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["setquota", "-u", "alice", "0", "0", "0", "0", "/home"]

    def test_edquota_argv_with_limits(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.quota.run_subprocess", mock_fn):
            _execute("edquota", {
                "username": "bob",
                "filesystem": "/home",
                "soft_blocks": 512000,
                "hard_blocks": 614400,
                "soft_inodes": 5000,
                "hard_inodes": 6000,
            })
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "setquota", "-u", "bob",
            "512000", "614400", "5000", "6000",
            "/home",
        ]


# ---------------------------------------------------------------------------
# Exit-code mapping: success and failure summaries
# ---------------------------------------------------------------------------

class TestRepquota:
    def test_success_summary(self) -> None:
        with _patch_run(_ok(stdout="Block limits\nalice 102400")):
            result = _execute("repquota", {"filesystem": "/home"})
        assert result.ok
        assert "/home" in result.summary

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="No quota")):
            result = _execute("repquota", {"filesystem": "/nosuchfs"})
        assert not result.ok
        assert result.exit_code == 1
        assert "/nosuchfs" in result.summary


class TestQuotaUser:
    def test_success_summary(self) -> None:
        with _patch_run(_ok(stdout="Disk quotas for alice")):
            result = _execute("quota_user", {"username": "alice"})
        assert result.ok
        assert "alice" in result.summary

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="user not found")):
            result = _execute("quota_user", {"username": "ghost"})
        assert not result.ok
        assert "ghost" in result.summary


class TestQuotaon:
    def test_success_summary(self) -> None:
        with _patch_run(_ok(stdout="/home: user quotas turned on")):
            result = _execute("quotaon", {"filesystem": "/home"})
        assert result.ok
        assert "/home" in result.summary
        assert "enabled" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="No quota files")):
            result = _execute("quotaon", {"filesystem": "/data"})
        assert not result.ok
        assert "/data" in result.summary


class TestQuotaoff:
    def test_success_summary(self) -> None:
        with _patch_run(_ok(stdout="/home: user quotas turned off")):
            result = _execute("quotaoff", {"filesystem": "/home"})
        assert result.ok
        assert "/home" in result.summary
        assert "disabled" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="not enabled")):
            result = _execute("quotaoff", {"filesystem": "/scratch"})
        assert not result.ok
        assert "/scratch" in result.summary


class TestQuotacheck:
    def test_success_summary(self) -> None:
        with _patch_run(_ok(stdout="quotacheck: Scanning /home done")):
            result = _execute("quotacheck", {"filesystem": "/home"})
        assert result.ok
        assert "/home" in result.summary
        assert "completed" in result.summary.lower() or "updated" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="Cannot find filesystem")):
            result = _execute("quotacheck", {"filesystem": "/nosuchfs"})
        assert not result.ok
        assert "/nosuchfs" in result.summary


class TestEdquota:
    def test_success_summary(self) -> None:
        with _patch_run(_ok()):
            result = _execute("edquota", {
                "username": "alice",
                "filesystem": "/home",
                "soft_blocks": 512000,
                "hard_blocks": 614400,
            })
        assert result.ok
        assert "alice" in result.summary
        assert "/home" in result.summary

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="user does not exist")):
            result = _execute("edquota", {"username": "ghost", "filesystem": "/home"})
        assert not result.ok
        assert "ghost" in result.summary

    def test_invalid_limit_type_returns_toolresult(self) -> None:
        # I9: bad limit values must not raise — they degrade to ToolResult
        result = _execute("edquota", {
            "username": "alice",
            "filesystem": "/home",
            "soft_blocks": "not-a-number",
        })
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("repquota",   {"filesystem": "/home"}),
        ("quota_user", {"username": "alice"}),
        ("quotaon",    {"filesystem": "/home"}),
        ("quotaoff",   {"filesystem": "/home"}),
        ("quotacheck", {"filesystem": "/home"}),
        ("edquota",    {"username": "alice", "filesystem": "/home"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"repquota\" name=\"aquota.user\""
        )
        with _patch_run(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op={op!r}: {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("repquota",   {"filesystem": "/home"}),
        ("quota_user", {"username": "alice"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="No such filesystem.")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("repquota",   {"filesystem": "/home"}),
        ("quota_user", {"username": "alice"}),
        ("quotaon",    {"filesystem": "/home"}),
        ("quotaoff",   {"filesystem": "/home"}),
        ("quotacheck", {"filesystem": "/home"}),
        ("edquota",    {"username": "alice", "filesystem": "/home"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("repquota",   {"filesystem": "/home"}),
        ("quota_user", {"username": "alice"}),
        ("quotaon",    {"filesystem": "/home"}),
        ("quotaoff",   {"filesystem": "/home"}),
        ("quotacheck", {"filesystem": "/home"}),
        ("edquota",    {"username": "alice", "filesystem": "/home"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# No AI / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("repquota",   {"filesystem": "/home"}),
        ("quota_user", {"username": "alice"}),
        ("quotaon",    {"filesystem": "/home"}),
        ("quotaoff",   {"filesystem": "/home"}),
        ("quotacheck", {"filesystem": "/home"}),
        ("edquota",    {"username": "alice", "filesystem": "/home"}),
    ])
    def test_no_ai_language_success(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op={op!r}: {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("repquota",   {"filesystem": "/home"}),
        ("quota_user", {"username": "alice"}),
        ("quotaon",    {"filesystem": "/home"}),
        ("edquota",    {"username": "alice", "filesystem": "/home"}),
    ])
    def test_no_ai_language_failure(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op={op!r}: {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# execute() NEVER raises (I9)
# ---------------------------------------------------------------------------

class TestNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("totally_bogus_op", {"filesystem": "/home"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert "totally_bogus_op" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        """run_subprocess returns exit 127 when the binary is not found (I9)."""
        not_found = ToolResult(
            exit_code=127,
            stdout="",
            stderr="repquota: command not found",
            summary="",
        )
        with patch("core.tools.quota.run_subprocess", return_value=not_found):
            result = _execute("repquota", {"filesystem": "/home"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        # Summary is non-empty (failure path)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("repquota",   {"filesystem": "/home"}),
        ("quota_user", {"username": "alice"}),
        ("quotaon",    {"filesystem": "/home"}),
        ("quotaoff",   {"filesystem": "/home"}),
        ("quotacheck", {"filesystem": "/home"}),
        ("edquota",    {"username": "alice", "filesystem": "/home"}),
    ])
    def test_nonzero_exit_never_raises(self, op: str, args: dict) -> None:
        err_result = ToolResult(exit_code=1, stdout="", stderr="error", summary="")
        with patch("core.tools.quota.run_subprocess", return_value=err_result):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_repquota(self) -> None:
        with _patch_run(_ok(stdout="quota report")):
            result = registry.dispatch("quota", "repquota", {"filesystem": "/home"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_quota_user(self) -> None:
        with _patch_run(_ok(stdout="alice: 102400")):
            result = registry.dispatch("quota", "quota_user", {"username": "alice"})
        assert result.ok

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError):
            registry.dispatch("quota", "quota_user", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("quota", "nonexistent_op", {"filesystem": "/home"})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires quota-utils on Rocky Linux 9")
def test_live_repquota_home() -> None:
    """Live: repquota /home returns a populated ToolResult."""
    result = _execute("repquota", {"filesystem": "/home"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires quota-utils on Rocky Linux 9")
def test_live_quota_user_root() -> None:
    """Live: quota -u root returns quota info."""
    result = _execute("quota_user", {"username": "root"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root + quota-utils on Rocky Linux 9")
def test_live_quotacheck_requires_root() -> None:
    """Live: quotacheck requires root privileges; exit non-0 without sudo."""
    result = _execute("quotacheck", {"filesystem": "/home"})
    assert result.exit_code is not None
