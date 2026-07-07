"""tests/test_tools_nfs.py — Unit tests for core/tools/nfs.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without exportfs, showmount, or mount present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: showmount/exportfs_list/exports_view are READ;
    exportfs_add/nfs_start/nfs_stop/mount_client are WRITE;
    exportfs_unexport is DESTRUCTIVE.
  * Command vectors: each op builds the exact expected argv.
  * Exit-code mapping: exit 0 → ok=True; nonzero → ok=False.
  * I2-clean summaries: no AI/LLM/model/agent language in any summary.
  * SELinux hint: AVC in stderr surfaces the hint; clean stderr does not.
  * execute() never raises (I9): unknown op and missing binary both return
    a well-formed ToolResult, no exception.
  * ToolResult structure: all four keys present via as_dict().
  * DEFERRED-TO-MOSSAD: live execution tests are marked skip.

Mocking strategy
----------------
  Patch ``core.tools.nfs.run_subprocess`` (the binding in the nfs module's
  namespace, not the shared core.tools.run_subprocess) so all calls are
  intercepted without launching real processes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration
import core.tools.nfs  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.nfs import NFS_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch run_subprocess in the nfs module's namespace."""
    return patch("core.tools.nfs.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_nfs_registered(self) -> None:
        assert registry.get("nfs") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("nfs")
        assert spec is not None
        assert spec.name == "nfs"

    def test_all_expected_ops(self) -> None:
        spec = registry.get("nfs")
        assert spec is not None
        expected = {
            "showmount",
            "exportfs_list",
            "exportfs_add",
            "exportfs_unexport",
            "exports_view",
            "nfs_start",
            "nfs_stop",
            "mount_client",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["showmount", "exportfs_list", "exports_view"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nfs", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["exportfs_add", "nfs_start", "nfs_stop", "mount_client"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nfs", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_exportfs_unexport_is_destructive(self) -> None:
        cls = registry.permission_class_for("nfs", "exportfs_unexport")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_showmount_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Export list for srv:\n/data  *\n"))
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("showmount", {"server": "fileserver.example.com"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["showmount", "-e", "fileserver.example.com"]

    def test_exportfs_list_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="/data\t*(rw,sync)\n"))
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("exportfs_list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["exportfs", "-v"]

    def test_exportfs_add_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("exportfs_add", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["exportfs", "-r"]

    def test_exportfs_unexport_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("exportfs_unexport", {"target": "192.168.1.0/24:/srv/nfs"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["exportfs", "-u", "192.168.1.0/24:/srv/nfs"]

    def test_exports_view_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="/srv/nfs  *(rw,sync)\n"))
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("exports_view", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["cat", "/etc/exports"]

    def test_nfs_start_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("nfs_start", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "start", "nfs-server"]

    def test_nfs_stop_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("nfs_stop", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "stop", "nfs-server"]

    def test_mount_client_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("mount_client", {
                "server": "nas.example.com",
                "path": "/srv/data",
                "mountpoint": "/mnt/data",
            })
        argv = mock_fn.call_args[0][0]
        assert argv == ["mount", "-t", "nfs", "nas.example.com:/srv/data", "/mnt/data"]


# ---------------------------------------------------------------------------
# Exit-code mapping: success and failure paths
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_showmount_success(self) -> None:
        with _patch(_ok(stdout="Export list for srv:\n/data  *\n")):
            result = _execute("showmount", {"server": "srv.example.com"})
        assert result.ok
        assert result.exit_code == 0
        assert "srv.example.com" in result.summary

    def test_showmount_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Connection refused")):
            result = _execute("showmount", {"server": "unreachable.example.com"})
        assert not result.ok
        assert "unreachable.example.com" in result.summary
        assert "1" in result.summary

    def test_exportfs_list_success(self) -> None:
        with _patch(_ok(stdout="/data\t*(rw)\n")):
            result = _execute("exportfs_list", {})
        assert result.ok
        assert "export" in result.summary.lower()

    def test_exportfs_list_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="exportfs: failed")):
            result = _execute("exportfs_list", {})
        assert not result.ok
        assert "1" in result.summary

    def test_exportfs_add_success(self) -> None:
        with _patch(_ok()):
            result = _execute("exportfs_add", {})
        assert result.ok
        assert "reload" in result.summary.lower() or "publish" in result.summary.lower()

    def test_exportfs_add_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="no exports")):
            result = _execute("exportfs_add", {})
        assert not result.ok

    def test_exportfs_unexport_success(self) -> None:
        with _patch(_ok()):
            result = _execute("exportfs_unexport", {"target": "*:/srv/nfs"})
        assert result.ok
        assert "*:/srv/nfs" in result.summary
        assert "revoked" in result.summary.lower()

    def test_exportfs_unexport_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Could not find export")):
            result = _execute("exportfs_unexport", {"target": "ghost:/path"})
        assert not result.ok
        assert "ghost:/path" in result.summary
        assert "1" in result.summary

    def test_exports_view_success(self) -> None:
        with _patch(_ok(stdout="# /etc/exports\n/srv/nfs  *(rw,sync)\n")):
            result = _execute("exports_view", {})
        assert result.ok
        assert "/etc/exports" in result.summary

    def test_exports_view_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="No such file or directory")):
            result = _execute("exports_view", {})
        assert not result.ok
        assert "1" in result.summary

    def test_nfs_start_success(self) -> None:
        with _patch(_ok()):
            result = _execute("nfs_start", {})
        assert result.ok
        assert "started" in result.summary.lower()

    def test_nfs_start_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Failed to start nfs-server")):
            result = _execute("nfs_start", {})
        assert not result.ok
        assert "1" in result.summary

    def test_nfs_stop_success(self) -> None:
        with _patch(_ok()):
            result = _execute("nfs_stop", {})
        assert result.ok
        assert "stopped" in result.summary.lower()

    def test_nfs_stop_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Failed to stop")):
            result = _execute("nfs_stop", {})
        assert not result.ok

    def test_mount_client_success(self) -> None:
        with _patch(_ok()):
            result = _execute("mount_client", {
                "server": "nas.example.com",
                "path": "/data",
                "mountpoint": "/mnt/data",
            })
        assert result.ok
        assert "nas.example.com:/data" in result.summary
        assert "/mnt/data" in result.summary
        assert "mounted" in result.summary.lower()

    def test_mount_client_failure(self) -> None:
        with _patch(_fail(exit_code=32, stderr="Connection timed out")):
            result = _execute("mount_client", {
                "server": "bad.example.com",
                "path": "/data",
                "mountpoint": "/mnt/data",
            })
        assert not result.ok
        assert "bad.example.com:/data" in result.summary
        assert "32" in result.summary


# ---------------------------------------------------------------------------
# I2: No AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("showmount",         {"server": "fileserver.example.com"}),
        ("exportfs_list",     {}),
        ("exportfs_add",      {}),
        ("exportfs_unexport", {"target": "*:/srv/nfs"}),
        ("exports_view",      {}),
        ("nfs_start",         {}),
        ("nfs_stop",          {}),
        ("mount_client",      {"server": "nas.example.com", "path": "/data", "mountpoint": "/mnt/data"}),
    ])
    def test_no_ai_language_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="ok output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("showmount",         {"server": "fileserver.example.com"}),
        ("exportfs_add",      {}),
        ("exportfs_unexport", {"target": "*:/srv/nfs"}),
        ("mount_client",      {"server": "nas.example.com", "path": "/data", "mountpoint": "/mnt/data"}),
    ])
    def test_no_ai_language_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="some error")):
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
        "mount.nfs: access denied by server while mounting nas:/data\n"
        "type=AVC msg=audit(1751500000.123:456): avc:  denied  { read } for  "
        "pid=1234 comm=\"mount\" name=\"data\""
    )

    @pytest.mark.parametrize("op,args", [
        ("showmount",         {"server": "fileserver.example.com"}),
        ("exportfs_add",      {}),
        ("exportfs_unexport", {"target": "*:/srv/nfs"}),
        ("nfs_start",         {}),
        ("nfs_stop",          {}),
        ("mount_client",      {"server": "nas.example.com", "path": "/data", "mountpoint": "/mnt/data"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"SELinux hint missing for op='{op}': {result.summary!r}"
        )

    @pytest.mark.parametrize("op,args", [
        ("showmount",     {"server": "fileserver.example.com"}),
        ("exportfs_list", {}),
        ("nfs_start",     {}),
    ])
    def test_clean_stderr_no_selinux_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="Unit not found or connection refused.")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"False SELinux hint for op='{op}': {result.summary!r}"
        )


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("showmount",         {"server": "fileserver.example.com"}),
        ("exportfs_list",     {}),
        ("exportfs_add",      {}),
        ("exportfs_unexport", {"target": "*:/srv/nfs"}),
        ("exports_view",      {}),
        ("nfs_start",         {}),
        ("nfs_stop",          {}),
        ("mount_client",      {"server": "nas.example.com", "path": "/data", "mountpoint": "/mnt/data"}),
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
        ("showmount",         {"server": "srv"}),
        ("exportfs_list",     {}),
        ("exportfs_add",      {}),
        ("exportfs_unexport", {"target": "x:/y"}),
        ("exports_view",      {}),
        ("nfs_start",         {}),
        ("nfs_stop",          {}),
        ("mount_client",      {"server": "s", "path": "/p", "mountpoint": "/m"}),
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
        # No patch needed — the unknown-op path never calls run_subprocess
        result = _execute("nonexistent_op_xyz", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert len(result.summary) > 0

    def test_missing_binary_exit_127(self) -> None:
        """exit_code=127 (FileNotFoundError) degrades gracefully."""
        missing_binary = ToolResult(
            exit_code=127,
            stdout="",
            stderr="bash: exportfs: command not found",
            summary="",
        )
        with _patch(missing_binary):
            result = _execute("exportfs_list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_showmount_missing_binary_exit_127(self) -> None:
        missing_binary = ToolResult(
            exit_code=127,
            stdout="",
            stderr="bash: showmount: command not found",
            summary="",
        )
        with _patch(missing_binary):
            result = _execute("showmount", {"server": "srv.example.com"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_exportfs_list(self) -> None:
        with _patch(_ok(stdout="/data\t*(rw)\n")):
            result = registry.dispatch("nfs", "exportfs_list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_nfs_start(self) -> None:
        with _patch(_ok()):
            result = registry.dispatch("nfs", "nfs_start", {})
        assert result.ok

    def test_dispatch_showmount_missing_server_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'server'"):
            registry.dispatch("nfs", "showmount", {})

    def test_dispatch_mount_client_missing_args_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument"):
            registry.dispatch("nfs", "mount_client", {"server": "srv"})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("nfs", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# Destructive op: exportfs_unexport guard — vector has -u flag
# ---------------------------------------------------------------------------

class TestDestructiveVector:
    def test_unexport_argv_contains_minus_u(self) -> None:
        """The destructive exportfs -u shape must appear verbatim in argv."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nfs.run_subprocess", mock_fn):
            _execute("exportfs_unexport", {"target": "client:/srv/nfs"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "exportfs"
        assert "-u" in argv
        assert "client:/srv/nfs" in argv


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires Rocky Linux 9 with nfs-utils installed")
def test_live_showmount_localhost() -> None:
    """Live: showmount -e localhost on an NFS server."""
    result = _execute("showmount", {"server": "localhost"})
    assert result.exit_code in (0, 1)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires Rocky Linux 9 with nfs-utils installed")
def test_live_exportfs_list() -> None:
    """Live: exportfs -v on the Rocky host."""
    result = _execute("exportfs_list", {})
    assert result.exit_code == 0
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires Rocky Linux 9 with systemd + nfs-server")
def test_live_nfs_start_requires_sudo() -> None:
    """Live: systemctl start nfs-server requires elevated privileges."""
    result = _execute("nfs_start", {})
    assert result.exit_code is not None
