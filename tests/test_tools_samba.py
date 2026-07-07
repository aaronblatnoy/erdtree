"""tests/test_tools_samba.py — Unit tests for core/tools/samba.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without smbd, nmbd, smbpasswd, testparm, or net
present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: smbd_status/nmbd_status/testparm/usershare_list are
    READ; smbpasswd_add/usershare_add are WRITE; smbpasswd_delete is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful I2-clean summary.
  * Failed exit (nonzero) -> not ok, failure summary naming object + exit code.
  * Command vectors: argv list passed to run_subprocess matches expected shape.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises (I9): unknown ops and missing binaries (exit 127)
    both return well-formed ToolResult without raising.
  * I2: no AI/LLM/model/agent/agentic/neural/language-model language in summaries.
  * DEFERRED-TO-MOSSAD: live execution tests.

Mocking strategy
----------------
  Patch ``core.tools.samba.run_subprocess`` (the binding in the samba module's
  namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import core.tools.samba  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.samba import SAMBA_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    return patch("core.tools.samba.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_samba_registered(self) -> None:
        assert registry.get("samba") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("samba")
        assert spec is not None
        assert spec.name == "samba"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("samba")
        assert spec is not None
        expected = {
            "smbd_status",
            "nmbd_status",
            "testparm",
            "smbpasswd_add",
            "smbpasswd_delete",
            "usershare_list",
            "usershare_add",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["smbd_status", "nmbd_status", "testparm", "usershare_list"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("samba", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["smbpasswd_add", "usershare_add"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("samba", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_destructive_op(self) -> None:
        cls = registry.permission_class_for("samba", "smbpasswd_delete")
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for 'smbpasswd_delete', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_smbd_status_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("smbd_status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "status", "--no-pager", "smbd", "nmbd"]

    def test_nmbd_status_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("nmbd_status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "status", "--no-pager", "nmbd"]

    def test_testparm_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("testparm", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["testparm", "-s"]

    def test_smbpasswd_add_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("smbpasswd_add", {"username": "alice", "password": "secret"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["smbpasswd", "-a", "alice"]

    def test_smbpasswd_delete_argv(self) -> None:
        """Destructive verb -x must appear verbatim in argv so the classifier can gate it."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("smbpasswd_delete", {"username": "bob"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["smbpasswd", "-x", "bob"]
        # -x must be in position 1 so classify() can detect the destructive flag
        assert argv[1] == "-x"

    def test_usershare_list_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("usershare_list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["net", "usershare", "list"]

    def test_usershare_add_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("usershare_add", {"name": "data", "path": "/srv/data"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "net"
        assert argv[1] == "usershare"
        assert argv[2] == "add"
        assert "data" in argv
        assert "/srv/data" in argv

    def test_usershare_add_with_comment_and_acl(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.samba.run_subprocess", mock_fn):
            _execute("usershare_add", {
                "name": "shared",
                "path": "/mnt/shared",
                "comment": "Team share",
                "acl": "Everyone:F",
            })
        argv = mock_fn.call_args[0][0]
        assert "Team share" in argv
        assert "Everyone:F" in argv


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("smbd_status", {}),
        ("nmbd_status", {}),
        ("testparm", {}),
        ("smbpasswd_add", {"username": "alice"}),
        ("usershare_list", {}),
        ("usershare_add", {"name": "x", "path": "/tmp/x"}),
    ])
    def test_success_is_ok(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout="success output")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("smbd_status", {}),
        ("nmbd_status", {}),
        ("testparm", {}),
        ("smbpasswd_add", {"username": "alice"}),
        ("smbpasswd_delete", {"username": "bob"}),
        ("usershare_list", {}),
        ("usershare_add", {"name": "x", "path": "/tmp/x"}),
    ])
    def test_failure_is_not_ok(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="something failed")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1

    def test_failure_summary_includes_exit_code(self) -> None:
        with _patch_run(_fail(exit_code=5, stderr="not found")):
            result = _execute("smbpasswd_delete", {"username": "carol"})
        assert not result.ok
        assert "5" in result.summary or "carol" in result.summary

    def test_testparm_success_summary(self) -> None:
        with _patch_run(_ok(stdout="Loaded services file OK.")):
            result = _execute("testparm", {})
        assert result.ok
        assert "valid" in result.summary.lower() or "passed" in result.summary.lower()

    def test_testparm_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="ERROR: invalid parameter")):
            result = _execute("testparm", {})
        assert not result.ok
        assert "1" in result.summary

    def test_smbpasswd_delete_success_names_user(self) -> None:
        with _patch_run(_ok(stdout="Deleted user dave.")):
            result = _execute("smbpasswd_delete", {"username": "dave"})
        assert result.ok
        assert "dave" in result.summary

    def test_usershare_add_success_names_share(self) -> None:
        with _patch_run(_ok()):
            result = _execute("usershare_add", {"name": "myshare", "path": "/srv/myshare"})
        assert result.ok
        assert "myshare" in result.summary


# ---------------------------------------------------------------------------
# I2: no AI language in summaries
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("smbd_status",      {}),
        ("nmbd_status",      {}),
        ("testparm",         {}),
        ("smbpasswd_add",    {"username": "alice"}),
        ("smbpasswd_delete", {"username": "bob"}),
        ("usershare_list",   {}),
        ("usershare_add",    {"name": "s", "path": "/tmp/s"}),
    ])
    def test_no_ai_language_success(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout="ok output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("smbd_status",      {}),
        ("testparm",         {}),
        ("smbpasswd_delete", {"username": "carol"}),
        ("usershare_add",    {"name": "t", "path": "/tmp/t"}),
    ])
    def test_no_ai_language_failure(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# SELinux hint
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "smbd[1234]: AVC avc:  denied  { read } for  pid=1234 "
        "comm=\"smbd\" name=\"smb.conf\" scontext=system_u:system_r:smbd_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("smbd_status",      {}),
        ("nmbd_status",      {}),
        ("testparm",         {}),
        ("smbpasswd_add",    {"username": "alice"}),
        ("smbpasswd_delete", {"username": "bob"}),
        ("usershare_list",   {}),
        ("usershare_add",    {"name": "x", "path": "/tmp/x"}),
    ])
    def test_avc_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"SELinux hint not surfaced for op='{op}': {result.summary!r}"
        )

    @pytest.mark.parametrize("op,args", [
        ("smbd_status", {}),
        ("testparm",    {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="Unit not found.")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("smbd_status",      {}),
        ("nmbd_status",      {}),
        ("testparm",         {}),
        ("smbpasswd_add",    {"username": "alice"}),
        ("smbpasswd_delete", {"username": "bob"}),
        ("usershare_list",   {}),
        ("usershare_add",    {"name": "sh", "path": "/tmp/sh"}),
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
        ("smbd_status",      {}),
        ("nmbd_status",      {}),
        ("testparm",         {}),
        ("smbpasswd_add",    {"username": "u"}),
        ("smbpasswd_delete", {"username": "u"}),
        ("usershare_list",   {}),
        ("usershare_add",    {"name": "n", "path": "/p"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9: execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert "nonexistent_op" in result.summary or "Unknown" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        """Simulate a missing binary (exit 127) — should NOT raise."""
        with _patch_run(_fail(exit_code=127, stderr="command not found: smbd")):
            result = _execute("smbd_status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    @pytest.mark.parametrize("op,args", [
        ("smbd_status",      {}),
        ("nmbd_status",      {}),
        ("testparm",         {}),
        ("smbpasswd_add",    {"username": "u"}),
        ("smbpasswd_delete", {"username": "u"}),
        ("usershare_list",   {}),
        ("usershare_add",    {"name": "n", "path": "/p"}),
    ])
    def test_every_op_returns_toolresult_on_exit_127(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=127, stderr="command not found")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_smbd_status(self) -> None:
        with _patch_run(_ok(stdout="● smbd.service")):
            result = registry.dispatch("samba", "smbd_status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_testparm(self) -> None:
        with _patch_run(_ok(stdout="Loaded services file OK.")):
            result = registry.dispatch("samba", "testparm", {})
        assert result.ok

    def test_dispatch_missing_username_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'username'"):
            registry.dispatch("samba", "smbpasswd_delete", {})

    def test_dispatch_missing_name_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument"):
            registry.dispatch("samba", "usershare_add", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("samba", "bad_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real smbd/testparm on Rocky Linux 9")
def test_live_smbd_status() -> None:
    """Live: systemctl status smbd nmbd returns a populated ToolResult."""
    result = _execute("smbd_status", {})
    assert result.exit_code in (0, 3, 4)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real testparm on Rocky Linux 9")
def test_live_testparm() -> None:
    """Live: testparm -s validates /etc/samba/smb.conf."""
    result = _execute("testparm", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout + result.stderr, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real smbpasswd on Rocky Linux 9")
def test_live_usershare_list() -> None:
    """Live: net usershare list returns defined shares."""
    result = _execute("usershare_list", {})
    assert result.exit_code is not None
    assert isinstance(result.stdout, str)
