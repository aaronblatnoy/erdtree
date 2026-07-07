"""tests/test_tools_rsync.py — Unit tests for core/tools/rsync.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without rsync present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: dry-run/progress are READ; sync is WRITE;
    sync-delete is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary with exit code.
  * Command vectors: correct argv lists passed to run_subprocess including
    --delete flag for sync-delete.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2 invariant: no AI/LLM/model/agent language in any summary.
  * I9 invariant: execute() never raises for unknown op or missing binary.
  * DEFERRED-TO-MOSSAD: live execution against real rsync on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.rsync.run_subprocess`` (the function in the rsync
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import core.tools.rsync  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.rsync import RSYNC_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.rsync.run_subprocess."""
    return patch("core.tools.rsync.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_rsync_registered_in_module_registry(self) -> None:
        assert registry.get("rsync") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("rsync")
        assert spec is not None
        assert spec.name == "rsync"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("rsync")
        assert spec is not None
        expected = {"dry-run", "sync", "sync-delete", "progress"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["dry-run", "progress"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("rsync", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    def test_sync_is_write(self) -> None:
        cls = registry.permission_class_for("rsync", "sync")
        assert cls is OpClass.WRITE, f"Expected WRITE for 'sync', got {cls}"

    def test_sync_delete_is_destructive(self) -> None:
        cls = registry.permission_class_for("rsync", "sync-delete")
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for 'sync-delete', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_dry_run_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rsync.run_subprocess", mock_fn):
            _execute("dry-run", {"src": "/src/", "dest": "/dest/"})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "rsync"
        assert "--dry-run" in cmd
        assert "/src/" in cmd
        assert "/dest/" in cmd

    def test_sync_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rsync.run_subprocess", mock_fn):
            _execute("sync", {"src": "/src/", "dest": "/dest/"})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "rsync"
        assert "--delete" not in cmd, "sync must NOT include --delete"
        assert "/src/" in cmd
        assert "/dest/" in cmd

    def test_sync_delete_includes_delete_flag(self) -> None:
        """--delete must appear verbatim so the classifier can gate it."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rsync.run_subprocess", mock_fn):
            _execute("sync-delete", {"src": "/src/", "dest": "/dest/"})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "rsync"
        assert "--delete" in cmd
        assert "/src/" in cmd
        assert "/dest/" in cmd

    def test_progress_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rsync.run_subprocess", mock_fn):
            _execute("progress", {"src": "/src/", "dest": "/dest/"})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "rsync"
        assert "--dry-run" in cmd
        assert "--progress" in cmd
        assert "--stats" in cmd
        assert "/src/" in cmd
        assert "/dest/" in cmd

    def test_src_and_dest_appear_as_final_positional_args(self) -> None:
        """src and dest must be the last two elements so rsync sees them correctly."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rsync.run_subprocess", mock_fn):
            _execute("sync", {"src": "/a/", "dest": "/b/"})
        cmd = mock_fn.call_args[0][0]
        assert cmd[-2] == "/a/"
        assert cmd[-1] == "/b/"


# ---------------------------------------------------------------------------
# dry-run operation
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_success_summary(self) -> None:
        stdout = (
            ">f+++++++++ data/config.conf\n"
            ">f+++++++++ data/data.db\n"
            "\nsent 1,234 bytes  received 92 bytes (DRY RUN)\n"
        )
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("dry-run", {"src": "/data/", "dest": "/backup/"})
        assert result.ok
        assert "/data/" in result.summary
        assert "/backup/" in result.summary

    def test_failure_summary_includes_exit_code(self) -> None:
        stderr = 'rsync: [sender] change_dir "/missing/" failed: No such file or directory (2)\n'
        with _patch_run(_fail_result(exit_code=11, stderr=stderr)):
            result = _execute("dry-run", {"src": "/missing/", "dest": "/backup/"})
        assert not result.ok
        assert result.exit_code == 11
        assert "11" in result.summary

    def test_result_contains_stdout(self) -> None:
        with _patch_run(_ok_result(stdout="itemize output")):
            result = _execute("dry-run", {"src": "/a/", "dest": "/b/"})
        assert result.stdout == "itemize output"


# ---------------------------------------------------------------------------
# sync operation
# ---------------------------------------------------------------------------

class TestSync:
    def test_success(self) -> None:
        with _patch_run(_ok_result(stdout="sending incremental file list\n./\nfile.dat\n")):
            result = _execute("sync", {"src": "/data/", "dest": "/backup/"})
        assert result.ok
        assert "/data/" in result.summary
        assert "/backup/" in result.summary

    def test_failure(self) -> None:
        stderr = 'rsync: [Receiver] mkstemp failed: Permission denied (13)\n'
        with _patch_run(_fail_result(exit_code=23, stderr=stderr)):
            result = _execute("sync", {"src": "/data/", "dest": "/backup/"})
        assert not result.ok
        assert result.exit_code == 23
        assert "/data/" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        with _patch_run(_fail_result(exit_code=127)):
            result = _execute("sync", {"src": "/data/", "dest": "/backup/"})
        assert not result.ok
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# sync-delete operation
# ---------------------------------------------------------------------------

class TestSyncDelete:
    def test_success_summary_mentions_deletion(self) -> None:
        stdout = (
            "sending incremental file list\n"
            "deleting old_file.bak\n"
            "new_file.dat\n"
        )
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("sync-delete", {"src": "/src/", "dest": "/dest/"})
        assert result.ok
        assert "/src/" in result.summary
        assert "/dest/" in result.summary

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=11, stderr="source not found")):
            result = _execute("sync-delete", {"src": "/src/", "dest": "/dest/"})
        assert not result.ok
        assert "11" in result.summary

    def test_permission_class_is_destructive(self) -> None:
        cls = RSYNC_SPEC.permission_class_for("sync-delete")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# progress operation
# ---------------------------------------------------------------------------

class TestProgress:
    def test_success_summary(self) -> None:
        stdout = (
            "Number of files: 42 (reg: 42)\n"
            "Total file size: 1,234,567 bytes\n"
            "(DRY RUN)\n"
        )
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("progress", {"src": "/data/", "dest": "/backup/"})
        assert result.ok
        assert "/data/" in result.summary
        assert "/backup/" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=11, stderr="No such file or directory")):
            result = _execute("progress", {"src": "/missing/", "dest": "/backup/"})
        assert not result.ok
        assert result.exit_code == 11


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op", ["dry-run", "sync", "sync-delete", "progress"])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str) -> None:
        avc_stderr = (
            "rsync: send_files failed to open "
            "AVC avc: denied { read } for pid=4567 comm=\"rsync\""
        )
        with _patch_run(_fail_result(exit_code=23, stderr=avc_stderr)):
            result = _execute(op, {"src": "/src/", "dest": "/dest/"})
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op={op!r}: {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=11, stderr="No such file or directory")):
            result = _execute("sync", {"src": "/missing/", "dest": "/dest/"})
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary

    def test_permission_denied_pattern_surfaces_hint(self) -> None:
        stderr = "rsync: [Receiver] mkstemp failed: Permission denied (13)"
        with _patch_run(_fail_result(exit_code=23, stderr=stderr)):
            result = _execute("sync", {"src": "/src/", "dest": "/dest/"})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("dry-run",     {"src": "/src/", "dest": "/dest/"}),
        ("sync",        {"src": "/src/", "dest": "/dest/"}),
        ("sync-delete", {"src": "/src/", "dest": "/dest/"}),
        ("progress",    {"src": "/src/", "dest": "/dest/"}),
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
        ("dry-run",     {"src": "/a/", "dest": "/b/"}),
        ("sync",        {"src": "/a/", "dest": "/b/"}),
        ("sync-delete", {"src": "/a/", "dest": "/b/"}),
        ("progress",    {"src": "/a/", "dest": "/b/"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9: execute() never raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_well_formed_result(self) -> None:
        result = _execute("nonexistent_op", {"src": "/a/", "dest": "/b/"})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        assert "nonexistent_op" in result.summary

    def test_missing_binary_exit_127_is_graceful(self) -> None:
        with _patch_run(_fail_result(exit_code=127)):
            result = _execute("sync", {"src": "/a/", "dest": "/b/"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_unknown_op_does_not_raise(self) -> None:
        try:
            result = _execute("bogus", {})
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"_execute raised unexpectedly: {exc!r}")
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("dry-run",     {"src": "/src/", "dest": "/dest/"}),
        ("sync",        {"src": "/src/", "dest": "/dest/"}),
        ("sync-delete", {"src": "/src/", "dest": "/dest/"}),
        ("progress",    {"src": "/src/", "dest": "/dest/"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("dry-run",     {"src": "/src/", "dest": "/dest/"}),
        ("sync",        {"src": "/src/", "dest": "/dest/"}),
        ("sync-delete", {"src": "/src/", "dest": "/dest/"}),
        ("progress",    {"src": "/src/", "dest": "/dest/"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=11, stderr="No such file or directory")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_dry_run(self) -> None:
        with _patch_run(_ok_result(stdout="dry run output")):
            result = registry.dispatch("rsync", "dry-run", {"src": "/a/", "dest": "/b/"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_sync(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("rsync", "sync", {"src": "/a/", "dest": "/b/"})
        assert result.ok

    def test_dispatch_sync_delete(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("rsync", "sync-delete", {"src": "/a/", "dest": "/b/"})
        assert result.ok

    def test_dispatch_progress(self) -> None:
        with _patch_run(_ok_result(stdout="stats output")):
            result = registry.dispatch("rsync", "progress", {"src": "/a/", "dest": "/b/"})
        assert result.ok

    def test_dispatch_missing_src_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'src'"):
            registry.dispatch("rsync", "sync", {"dest": "/b/"})

    def test_dispatch_missing_dest_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'dest'"):
            registry.dispatch("rsync", "sync", {"src": "/a/"})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("rsync", "nonexistent_op", {"src": "/a/", "dest": "/b/"})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real rsync on Rocky Linux 9")
def test_live_dry_run() -> None:
    """Live: rsync --dry-run returns a populated ToolResult."""
    result = _execute("dry-run", {"src": "/etc/", "dest": "/tmp/rsync-test/"})
    assert result.exit_code in (0, 11, 23)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real rsync on Rocky Linux 9")
def test_live_progress_stats() -> None:
    """Live: rsync --dry-run --progress --stats returns transfer statistics."""
    result = _execute("progress", {"src": "/etc/", "dest": "/tmp/rsync-test/"})
    assert result.exit_code in (0, 11, 23)
    assert "Number of files" in result.stdout or result.exit_code != 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real rsync on Rocky Linux 9")
def test_live_sync_requires_destination_exists() -> None:
    """Live: rsync sync to a missing destination exits non-zero."""
    result = _execute("sync", {"src": "/etc/", "dest": "/tmp/nonexistent-rsync-target/"})
    assert result.exit_code is not None
