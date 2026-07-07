"""tests/test_tools_stratis.py — Unit tests for core/tools/stratis.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without the stratis binary present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: pool-list/filesystem-list are READ; pool-create/
    filesystem-create/filesystem-snapshot are WRITE; pool-destroy/
    filesystem-destroy are DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary naming the object.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2: no AI/LLM/model/agent language in any summary.
  * I9: execute() never raises — unknown op and exit-127 both degrade gracefully.
  * as_dict() yields exactly the four required keys.

Mocking strategy
----------------
  We patch ``core.tools.stratis.run_subprocess`` (in the stratis module's
  namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Side-effect import: triggers self-registration in the registry.
import core.tools.stratis  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.stratis import STRATIS_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    return patch("core.tools.stratis.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_stratis_registered(self) -> None:
        assert registry.get("stratis") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("stratis")
        assert spec is not None
        assert spec.name == "stratis"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("stratis")
        assert spec is not None
        expected = {
            "pool-list",
            "pool-create",
            "pool-destroy",
            "filesystem-list",
            "filesystem-create",
            "filesystem-snapshot",
            "filesystem-destroy",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------


class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["pool-list", "filesystem-list"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("stratis", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["pool-create", "filesystem-create", "filesystem-snapshot"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("stratis", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["pool-destroy", "filesystem-destroy"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("stratis", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vector tests
# ---------------------------------------------------------------------------


class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_pool_list_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Name   Total\n"))
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute("pool-list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stratis", "pool", "list"]

    def test_pool_create_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute("pool-create", {"pool": "mypool", "blockdev": "/dev/sdb"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stratis", "pool", "create", "mypool", "/dev/sdb"]

    def test_pool_destroy_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute("pool-destroy", {"pool": "oldpool"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stratis", "pool", "destroy", "oldpool"]

    def test_filesystem_list_no_pool_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Pool   Name\n"))
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute("filesystem-list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stratis", "filesystem", "list"]

    def test_filesystem_list_with_pool_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Pool   Name\n"))
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute("filesystem-list", {"pool": "datapool"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stratis", "filesystem", "list", "datapool"]

    def test_filesystem_create_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute("filesystem-create", {"pool": "datapool", "filesystem": "appdata"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stratis", "filesystem", "create", "datapool", "appdata"]

    def test_filesystem_snapshot_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute(
                "filesystem-snapshot",
                {"pool": "datapool", "filesystem": "appdata", "snapshot": "appdata-snap1"},
            )
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "stratis", "filesystem", "snapshot", "datapool", "appdata", "appdata-snap1"
        ]

    def test_filesystem_destroy_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.stratis.run_subprocess", mock_fn):
            _execute("filesystem-destroy", {"pool": "datapool", "filesystem": "oldfs"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stratis", "filesystem", "destroy", "datapool", "oldfs"]


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------


class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("pool-list",           {}),
        ("pool-create",         {"pool": "p", "blockdev": "/dev/sdb"}),
        ("pool-destroy",        {"pool": "p"}),
        ("filesystem-list",     {}),
        ("filesystem-create",   {"pool": "p", "filesystem": "f"}),
        ("filesystem-snapshot", {"pool": "p", "filesystem": "f", "snapshot": "s"}),
        ("filesystem-destroy",  {"pool": "p", "filesystem": "f"}),
    ])
    def test_zero_exit_is_ok(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("pool-list",           {}),
        ("pool-create",         {"pool": "p", "blockdev": "/dev/sdb"}),
        ("pool-destroy",        {"pool": "p"}),
        ("filesystem-list",     {}),
        ("filesystem-create",   {"pool": "p", "filesystem": "f"}),
        ("filesystem-snapshot", {"pool": "p", "filesystem": "f", "snapshot": "s"}),
        ("filesystem-destroy",  {"pool": "p", "filesystem": "f"}),
    ])
    def test_nonzero_exit_is_not_ok(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Success summaries reference the object name
# ---------------------------------------------------------------------------


class TestSuccessSummaries:
    def test_pool_create_names_pool(self) -> None:
        with _patch(_ok()):
            result = _execute("pool-create", {"pool": "mypool", "blockdev": "/dev/sdb"})
        assert "mypool" in result.summary

    def test_pool_destroy_names_pool(self) -> None:
        with _patch(_ok()):
            result = _execute("pool-destroy", {"pool": "deadpool"})
        assert "deadpool" in result.summary

    def test_filesystem_create_names_fs(self) -> None:
        with _patch(_ok()):
            result = _execute("filesystem-create", {"pool": "dp", "filesystem": "myfs"})
        assert "myfs" in result.summary

    def test_filesystem_snapshot_names_snapshot(self) -> None:
        with _patch(_ok()):
            result = _execute(
                "filesystem-snapshot",
                {"pool": "dp", "filesystem": "myfs", "snapshot": "myfs-snap"},
            )
        assert "myfs-snap" in result.summary

    def test_filesystem_destroy_names_fs(self) -> None:
        with _patch(_ok()):
            result = _execute("filesystem-destroy", {"pool": "dp", "filesystem": "deadfs"})
        assert "deadfs" in result.summary


# ---------------------------------------------------------------------------
# Failure summaries reference the object name and exit code
# ---------------------------------------------------------------------------


class TestFailureSummaries:
    def test_pool_create_failure_mentions_pool(self) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute("pool-create", {"pool": "badpool", "blockdev": "/dev/sdb"})
        assert "badpool" in result.summary
        assert not result.ok

    def test_pool_destroy_failure_mentions_pool(self) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute("pool-destroy", {"pool": "ghostpool"})
        assert "ghostpool" in result.summary
        assert "1" in result.summary

    def test_filesystem_destroy_failure_mentions_fs(self) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute("filesystem-destroy", {"pool": "dp", "filesystem": "ghostfs"})
        assert "ghostfs" in result.summary


# ---------------------------------------------------------------------------
# I2-clean summaries — no AI/LLM/model/agent language
# ---------------------------------------------------------------------------


class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("pool-list",           {}),
        ("pool-create",         {"pool": "p", "blockdev": "/dev/sdb"}),
        ("pool-destroy",        {"pool": "p"}),
        ("filesystem-list",     {}),
        ("filesystem-create",   {"pool": "p", "filesystem": "f"}),
        ("filesystem-snapshot", {"pool": "p", "filesystem": "f", "snapshot": "s"}),
        ("filesystem-destroy",  {"pool": "p", "filesystem": "f"}),
    ])
    def test_no_ai_language_success(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("pool-list",           {}),
        ("pool-create",         {"pool": "p", "blockdev": "/dev/sdb"}),
        ("pool-destroy",        {"pool": "p"}),
        ("filesystem-list",     {}),
        ("filesystem-create",   {"pool": "p", "filesystem": "f"}),
        ("filesystem-snapshot", {"pool": "p", "filesystem": "f", "snapshot": "s"}),
        ("filesystem-destroy",  {"pool": "p", "filesystem": "f"}),
    ])
    def test_no_ai_language_failure(self, op: str, args: dict) -> None:
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
        "AVC avc: denied { read } for pid=1234 comm=\"stratis\" "
        "name=\"/dev/sdb\" scontext=unconfined_u:unconfined_r:unconfined_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("pool-list",           {}),
        ("pool-create",         {"pool": "p", "blockdev": "/dev/sdb"}),
        ("pool-destroy",        {"pool": "p"}),
        ("filesystem-list",     {}),
        ("filesystem-create",   {"pool": "p", "filesystem": "f"}),
        ("filesystem-snapshot", {"pool": "p", "filesystem": "f", "snapshot": "s"}),
        ("filesystem-destroy",  {"pool": "p", "filesystem": "f"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op='{op}': {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Pool not found.")):
            result = _execute("pool-destroy", {"pool": "missing"})
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------


class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("pool-list",           {}),
        ("pool-create",         {"pool": "p", "blockdev": "/dev/sdb"}),
        ("pool-destroy",        {"pool": "p"}),
        ("filesystem-list",     {}),
        ("filesystem-list",     {"pool": "dp"}),
        ("filesystem-create",   {"pool": "p", "filesystem": "f"}),
        ("filesystem-snapshot", {"pool": "p", "filesystem": "f", "snapshot": "s"}),
        ("filesystem-destroy",  {"pool": "p", "filesystem": "f"}),
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
        ("pool-list",           {}),
        ("pool-create",         {"pool": "p", "blockdev": "/dev/sdb"}),
        ("pool-destroy",        {"pool": "p"}),
        ("filesystem-list",     {}),
        ("filesystem-create",   {"pool": "p", "filesystem": "f"}),
        ("filesystem-snapshot", {"pool": "p", "filesystem": "f", "snapshot": "s"}),
        ("filesystem-destroy",  {"pool": "p", "filesystem": "f"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------


class TestExecuteNeverRaises:
    def test_unknown_op_returns_tool_result(self) -> None:
        result = _execute("bogus-op-that-does-not-exist", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert len(result.summary) > 0
        assert "bogus-op-that-does-not-exist" in result.summary

    def test_missing_binary_exit_127_degrades(self) -> None:
        missing_binary = ToolResult(
            exit_code=127,
            stdout="",
            stderr="stratis: command not found",
            summary="",
        )
        with patch("core.tools.stratis.run_subprocess", return_value=missing_binary):
            result = _execute("pool-list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_pool_destroy_exit_127_degrades(self) -> None:
        missing_binary = ToolResult(
            exit_code=127,
            stdout="",
            stderr="stratis: command not found",
            summary="",
        )
        with patch("core.tools.stratis.run_subprocess", return_value=missing_binary):
            result = _execute("pool-destroy", {"pool": "mypool"})
        assert isinstance(result, ToolResult)
        assert not result.ok
        assert "mypool" in result.summary

    def test_filesystem_destroy_exit_127_degrades(self) -> None:
        missing_binary = ToolResult(
            exit_code=127,
            stdout="",
            stderr="stratis: command not found",
            summary="",
        )
        with patch("core.tools.stratis.run_subprocess", return_value=missing_binary):
            result = _execute("filesystem-destroy", {"pool": "p", "filesystem": "f"})
        assert isinstance(result, ToolResult)
        assert not result.ok


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real stratis CLI on Rocky Linux 9")
def test_live_pool_list() -> None:
    """Live: stratis pool list returns a populated ToolResult."""
    result = _execute("pool-list", {})
    assert result.exit_code in (0, 1, 127)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real stratis CLI on Rocky Linux 9")
def test_live_filesystem_list() -> None:
    """Live: stratis filesystem list returns a populated ToolResult."""
    result = _execute("filesystem-list", {})
    assert result.exit_code in (0, 1, 127)
    assert isinstance(result.stdout, str)
