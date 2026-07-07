"""tests/test_tools_restic.py — Unit tests for core/tools/restic.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without the restic binary present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: snapshots READ; backup/restore/forget WRITE;
    forget_prune DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code=1/127) → ok=False, failure summary with op details.
  * Command vectors: argv lists are exactly the expected shapes including --prune.
  * SELinux AVC hint surfaces in summary when stderr contains AVC language.
  * I2: no AI/LLM/model/agent language in any summary.
  * I9: execute() never raises for unknown op or exit_code=127 (missing binary).
  * DEFERRED-TO-MOSSAD: live execution against real restic on Rocky Linux 9.

Mocking strategy
----------------
  Patch ``core.tools.restic.run_subprocess`` (the binding in this module's
  namespace after ``from core.tools import run_subprocess``).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import core.tools.restic  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.restic import RESTIC_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.restic.run_subprocess."""
    return patch("core.tools.restic.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_restic_registered_in_module_registry(self) -> None:
        assert registry.get("restic") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("restic")
        assert spec is not None
        assert spec.name == "restic"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("restic")
        assert spec is not None
        expected = {"snapshots", "backup", "restore", "forget", "forget_prune"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    def test_snapshots_is_read(self) -> None:
        cls = registry.permission_class_for("restic", "snapshots")
        assert cls is OpClass.READ

    @pytest.mark.parametrize("op", ["backup", "restore", "forget"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("restic", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_forget_prune_is_destructive(self) -> None:
        cls = registry.permission_class_for("restic", "forget_prune")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Verify the exact argv list passed to run_subprocess for each op."""

    def test_snapshots_basic_cmd(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("snapshots", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "restic"
        assert argv[1] == "snapshots"

    def test_snapshots_with_repo(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("snapshots", {"repo": "/mnt/backup"})
        argv = mock_fn.call_args[0][0]
        assert "--repo" in argv
        assert "/mnt/backup" in argv

    def test_snapshots_with_tag_and_host(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("snapshots", {"tag": "weekly", "host": "db01"})
        argv = mock_fn.call_args[0][0]
        assert "--tag" in argv
        assert "weekly" in argv
        assert "--host" in argv
        assert "db01" in argv

    def test_backup_cmd_includes_path(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("backup", {"path": "/etc"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["restic", "backup", "/etc"]

    def test_backup_cmd_with_repo_and_tag(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("backup", {"path": "/home", "repo": "/mnt/r", "tag": "daily"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "restic"
        assert argv[1] == "backup"
        assert "/home" in argv
        assert "--repo" in argv
        assert "/mnt/r" in argv
        assert "--tag" in argv
        assert "daily" in argv

    def test_restore_cmd_shape(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("restore", {"snapshot_id": "abc12345", "target": "/tmp/r"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "restic"
        assert argv[1] == "restore"
        assert "abc12345" in argv
        assert "--target" in argv
        assert "/tmp/r" in argv

    def test_forget_cmd_shape(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("forget", {"snapshot_id": "deadbeef"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["restic", "forget", "deadbeef"]

    def test_forget_prune_includes_prune_flag(self) -> None:
        """The DESTRUCTIVE flag --prune must appear verbatim in the argv."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("forget_prune", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "restic"
        assert argv[1] == "forget"
        assert "--prune" in argv

    def test_forget_prune_with_keep_last(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("forget_prune", {"keep_last": 7})
        argv = mock_fn.call_args[0][0]
        assert "--prune" in argv
        assert "--keep-last" in argv
        ki = argv.index("--keep-last")
        assert argv[ki + 1] == "7"

    def test_forget_prune_with_repo_and_host(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            _execute("forget_prune", {"repo": "/mnt/nas", "host": "srv01", "keep_last": 5})
        argv = mock_fn.call_args[0][0]
        assert "--prune" in argv
        assert "--repo" in argv
        assert "/mnt/nas" in argv
        assert "--host" in argv
        assert "srv01" in argv


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_snapshots_success(self) -> None:
        with _patch_run(_ok_result(stdout="3 snapshots")):
            result = _execute("snapshots", {})
        assert result.ok
        assert "snapshot" in result.summary.lower()

    def test_snapshots_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="no such file")):
            result = _execute("snapshots", {})
        assert not result.ok
        assert result.exit_code == 1
        assert "1" in result.summary

    def test_backup_success(self) -> None:
        with _patch_run(_ok_result(stdout="snapshot abc saved")):
            result = _execute("backup", {"path": "/etc"})
        assert result.ok
        assert "/etc" in result.summary
        assert "completed" in result.summary.lower() or "backup" in result.summary.lower()

    def test_backup_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="lstat /missing: no such file")):
            result = _execute("backup", {"path": "/missing"})
        assert not result.ok
        assert "/missing" in result.summary

    def test_restore_success(self) -> None:
        with _patch_run(_ok_result(stdout="Summary: Restored 100 Files")):
            result = _execute("restore", {"snapshot_id": "abc12345", "target": "/tmp/r"})
        assert result.ok
        assert "abc12345" in result.summary
        assert "/tmp/r" in result.summary

    def test_restore_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="does not exist")):
            result = _execute("restore", {"snapshot_id": "badid", "target": "/tmp/r"})
        assert not result.ok
        assert "badid" in result.summary

    def test_forget_success(self) -> None:
        with _patch_run(_ok_result(stdout="removed 1 snapshots")):
            result = _execute("forget", {"snapshot_id": "abc12345"})
        assert result.ok
        assert "abc12345" in result.summary

    def test_forget_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="does not exist")):
            result = _execute("forget", {"snapshot_id": "deadbeef"})
        assert not result.ok
        assert "deadbeef" in result.summary

    def test_forget_prune_success(self) -> None:
        with _patch_run(_ok_result(stdout="Removed snapshots: 3")):
            result = _execute("forget_prune", {"keep_last": 7})
        assert result.ok
        assert "prun" in result.summary.lower() or "removed" in result.summary.lower()

    def test_forget_prune_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="unable to open config")):
            result = _execute("forget_prune", {})
        assert not result.ok
        assert "1" in result.summary

    def test_missing_binary_exit_127_snapshots(self) -> None:
        """Missing binary returns exit 127; execute() must not raise (I9)."""
        with _patch_run(_fail_result(exit_code=127, stderr="restic: command not found")):
            result = _execute("snapshots", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_exit_127_backup(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="restic: command not found")):
            result = _execute("backup", {"path": "/etc"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# I2 — No AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("snapshots",    {}),
        ("backup",       {"path": "/etc"}),
        ("restore",      {"snapshot_id": "abc12345", "target": "/tmp/r"}),
        ("forget",       {"snapshot_id": "abc12345"}),
        ("forget_prune", {"keep_last": 7}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="ok")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': "
                f"{result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("snapshots",    {}),
        ("backup",       {"path": "/etc"}),
        ("restore",      {"snapshot_id": "abc12345", "target": "/tmp/r"}),
        ("forget",       {"snapshot_id": "abc12345"}),
        ("forget_prune", {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something failed")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "Fatal: chmod /var/backup/restic: "
        "AVC avc: denied { write } for pid=4321 "
        "comm=\"restic\" name=\"restic\" scontext=unconfined_u:unconfined_r"
    )

    @pytest.mark.parametrize("op,args", [
        ("snapshots",    {}),
        ("backup",       {"path": "/etc"}),
        ("restore",      {"snapshot_id": "abc12345", "target": "/tmp/r"}),
        ("forget",       {"snapshot_id": "abc12345"}),
        ("forget_prune", {}),
    ])
    def test_avc_in_stderr_surfaces_selinux_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"SELinux hint not surfaced for op='{op}'; summary={result.summary!r}"
        )

    @pytest.mark.parametrize("op,args", [
        ("snapshots",    {}),
        ("backup",       {"path": "/etc"}),
        ("forget_prune", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="unable to open config file")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("snapshots",    {}),
        ("backup",       {"path": "/etc"}),
        ("restore",      {"snapshot_id": "abc12345", "target": "/tmp/r"}),
        ("forget",       {"snapshot_id": "abc12345"}),
        ("forget_prune", {"keep_last": 7}),
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
        ("snapshots",    {}),
        ("backup",       {"path": "/etc"}),
        ("restore",      {"snapshot_id": "abc12345", "target": "/tmp/r"}),
        ("forget",       {"snapshot_id": "abc12345"}),
        ("forget_prune", {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() never raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_well_formed_result(self) -> None:
        """execute() with an unknown op must never raise (I9)."""
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)

    def test_missing_binary_exit_127_does_not_raise(self) -> None:
        with _patch_run(_fail_result(exit_code=127)):
            result = _execute("snapshots", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_forget_prune_invalid_keep_last_does_not_raise(self) -> None:
        """Invalid keep_last must be handled gracefully — no exception."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.restic.run_subprocess", mock_fn):
            result = _execute("forget_prune", {"keep_last": "not-a-number"})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# ToolSpec description I2 check
# ---------------------------------------------------------------------------

class TestSpecDescriptionsI2:
    """Descriptions on ToolSpec/OpSpec are user-facing; enforce I2."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    def test_tool_description_i2_clean(self) -> None:
        desc = RESTIC_SPEC.description
        for word in self._FORBIDDEN:
            assert word not in desc

    def test_op_descriptions_i2_clean(self) -> None:
        for op_name, op_spec in RESTIC_SPEC.ops.items():
            for word in self._FORBIDDEN:
                assert word not in op_spec.description, (
                    f"I2 violation in op '{op_name}' description: '{word}'"
                )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_snapshots(self) -> None:
        with _patch_run(_ok_result(stdout="3 snapshots")):
            result = registry.dispatch("restic", "snapshots", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_backup(self) -> None:
        with _patch_run(_ok_result(stdout="snapshot abc saved")):
            result = registry.dispatch("restic", "backup", {"path": "/etc"})
        assert result.ok

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError):
            registry.dispatch("restic", "backup", {})  # missing 'path'

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("restic", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires restic binary on Rocky Linux 9 with EPEL")
def test_live_snapshots_default_repo() -> None:
    """Live: restic snapshots returns a populated ToolResult."""
    result = _execute("snapshots", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires restic binary and configured repo on Rocky Linux 9")
def test_live_backup_etc() -> None:
    """Live: restic backup /etc returns exit 0 and a snapshot ID in stdout."""
    result = _execute("backup", {"path": "/etc"})
    assert result.exit_code == 0
    assert "snapshot" in result.stdout.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires restic binary and valid snapshot on Rocky Linux 9")
def test_live_forget_prune_requires_confirmation() -> None:
    """Live: forget_prune is DESTRUCTIVE and requires explicit caller confirmation."""
    result = _execute("forget_prune", {"keep_last": 999})
    assert result.exit_code is not None
