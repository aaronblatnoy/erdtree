"""tests/test_tools_tar.py — Unit tests for core/tools/tar.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without tar present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/verify are READ; create/extract/create_gz/
    create_bz2/create_xz are WRITE.
  * Command vectors: each op builds the exact expected argv list.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code != 0) -> not ok, failure summary including archive name.
  * SELinux AVC hint surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises — unknown op and missing binary (exit 127) both return
    a well-formed ToolResult.
  * I2: no AI/LLM/model/agent language in any summary.
  * as_dict() returns exactly {exit_code, stdout, stderr, summary}.
  * DEFERRED-TO-MOSSAD: live execution against real tar on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.tar.run_subprocess`` (the function in the tar module's
  namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import core.tools.tar  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.tar import TAR_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 2, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    return patch("core.tools.tar.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_tar_registered(self) -> None:
        assert registry.get("tar") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("tar")
        assert spec is not None
        assert spec.name == "tar"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("tar")
        assert spec is not None
        expected = {"list", "create", "extract", "verify", "create_gz", "create_bz2", "create_xz"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list", "verify"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("tar", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["create", "extract", "create_gz", "create_bz2", "create_xz"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("tar", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_list_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("list", {"archive": "/backup/data.tar"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--list", "--verbose", "--file", "/backup/data.tar"]

    def test_create_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("create", {"archive": "/backup/out.tar", "sources": ["/etc", "/var/log"]})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--create", "--file", "/backup/out.tar", "/etc", "/var/log"]

    def test_extract_command_no_dest(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("extract", {"archive": "/backup/data.tar"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--extract", "--file", "/backup/data.tar"]

    def test_extract_command_with_dest(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("extract", {"archive": "/backup/data.tar", "dest": "/restore"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--extract", "--file", "/backup/data.tar", "--directory", "/restore"]

    def test_verify_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("verify", {"archive": "/backup/data.tar"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--compare", "--file", "/backup/data.tar"]

    def test_create_gz_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("create_gz", {"archive": "/backup/data.tar.gz", "sources": ["/etc"]})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--create", "--gzip", "--file", "/backup/data.tar.gz", "/etc"]

    def test_create_bz2_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("create_bz2", {"archive": "/backup/data.tar.bz2", "sources": ["/etc"]})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--create", "--bzip2", "--file", "/backup/data.tar.bz2", "/etc"]

    def test_create_xz_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.tar.run_subprocess", mock_fn):
            _execute("create_xz", {"archive": "/backup/data.tar.xz", "sources": ["/etc"]})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tar", "--create", "--xz", "--file", "/backup/data.tar.xz", "/etc"]


# ---------------------------------------------------------------------------
# Exit-code mapping and summaries
# ---------------------------------------------------------------------------

class TestListOp:
    def test_success_summary(self) -> None:
        stdout = "etc/\netc/nginx/\netc/nginx/nginx.conf\n"
        with _patch_run(_ok(stdout=stdout)):
            result = _execute("list", {"archive": "/backup/etc.tar"})
        assert result.ok
        assert "/backup/etc.tar" in result.summary
        assert "listed" in result.summary.lower() or "entries" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=2, stderr="Cannot open: No such file or directory")):
            result = _execute("list", {"archive": "/backup/missing.tar"})
        assert not result.ok
        assert result.exit_code == 2
        assert "/backup/missing.tar" in result.summary


class TestCreateOp:
    def test_success_summary(self) -> None:
        with _patch_run(_ok()):
            result = _execute("create", {"archive": "/backup/out.tar", "sources": ["/etc"]})
        assert result.ok
        assert "/backup/out.tar" in result.summary
        assert "created" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=2)):
            result = _execute("create", {"archive": "/backup/out.tar", "sources": ["/missing"]})
        assert not result.ok
        assert "/backup/out.tar" in result.summary

    def test_source_count_in_summary(self) -> None:
        with _patch_run(_ok()):
            result = _execute("create", {"archive": "/backup/out.tar", "sources": ["/a", "/b", "/c"]})
        assert "3" in result.summary


class TestExtractOp:
    def test_success_no_dest(self) -> None:
        with _patch_run(_ok()):
            result = _execute("extract", {"archive": "/backup/data.tar"})
        assert result.ok
        assert "current directory" in result.summary

    def test_success_with_dest(self) -> None:
        with _patch_run(_ok()):
            result = _execute("extract", {"archive": "/backup/data.tar", "dest": "/restore"})
        assert result.ok
        assert "/restore" in result.summary

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=2)):
            result = _execute("extract", {"archive": "/backup/data.tar", "dest": "/restore"})
        assert not result.ok
        assert "/backup/data.tar" in result.summary


class TestVerifyOp:
    def test_success_summary(self) -> None:
        with _patch_run(_ok()):
            result = _execute("verify", {"archive": "/backup/data.tar"})
        assert result.ok
        assert "verified" in result.summary.lower() or "match" in result.summary.lower()
        assert "/backup/data.tar" in result.summary

    def test_differences_found(self) -> None:
        with _patch_run(_fail(exit_code=1, stdout="etc/nginx.conf: Mod time differs")):
            result = _execute("verify", {"archive": "/backup/data.tar"})
        assert not result.ok
        assert "/backup/data.tar" in result.summary


class TestCreateGzOp:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("create_gz", {"archive": "/backup/data.tar.gz", "sources": ["/etc"]})
        assert result.ok
        assert "gzip" in result.summary.lower() or ".tar.gz" in result.summary or "Gzip" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=2)):
            result = _execute("create_gz", {"archive": "/backup/data.tar.gz", "sources": ["/etc"]})
        assert not result.ok


class TestCreateBz2Op:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("create_bz2", {"archive": "/backup/data.tar.bz2", "sources": ["/etc"]})
        assert result.ok
        assert "bzip2" in result.summary.lower() or "Bzip2" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=2)):
            result = _execute("create_bz2", {"archive": "/backup/data.tar.bz2", "sources": ["/etc"]})
        assert not result.ok


class TestCreateXzOp:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("create_xz", {"archive": "/backup/data.tar.xz", "sources": ["/etc"]})
        assert result.ok
        assert "xz" in result.summary.lower() or "Xz" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=2)):
            result = _execute("create_xz", {"archive": "/backup/data.tar.xz", "sources": ["/etc"]})
        assert not result.ok


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC = (
        "tar: /backup/data.tar: Cannot open: Permission denied\n"
        "AVC avc: denied { read } for pid=1234 comm=\"tar\" name=\"data.tar\""
    )

    @pytest.mark.parametrize("op,args", [
        ("list",       {"archive": "/backup/data.tar"}),
        ("create",     {"archive": "/backup/data.tar", "sources": ["/etc"]}),
        ("extract",    {"archive": "/backup/data.tar"}),
        ("verify",     {"archive": "/backup/data.tar"}),
        ("create_gz",  {"archive": "/backup/data.tar.gz", "sources": ["/etc"]}),
        ("create_bz2", {"archive": "/backup/data.tar.bz2", "sources": ["/etc"]}),
        ("create_xz",  {"archive": "/backup/data.tar.xz", "sources": ["/etc"]}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=2, stderr=self._AVC)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint missing for op='{op}': {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("list",   {"archive": "/backup/data.tar"}),
        ("verify", {"archive": "/backup/data.tar"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=2, stderr="Cannot open: No such file or directory")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary


# ---------------------------------------------------------------------------
# execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_operation", {"archive": "/backup/data.tar"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_operation" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127(self) -> None:
        with _patch_run(_fail(exit_code=127, stderr="tar: command not found")):
            result = _execute("list", {"archive": "/backup/data.tar"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_timeout_exit_124(self) -> None:
        with _patch_run(_fail(exit_code=124, stderr="timed out")):
            result = _execute("create_gz", {"archive": "/backup/data.tar.gz", "sources": ["/var/lib"]})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124
        assert not result.ok


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list",       {"archive": "/backup/data.tar"}),
        ("create",     {"archive": "/backup/data.tar", "sources": ["/etc"]}),
        ("extract",    {"archive": "/backup/data.tar"}),
        ("verify",     {"archive": "/backup/data.tar"}),
        ("create_gz",  {"archive": "/backup/data.tar.gz", "sources": ["/etc"]}),
        ("create_bz2", {"archive": "/backup/data.tar.bz2", "sources": ["/etc"]}),
        ("create_xz",  {"archive": "/backup/data.tar.xz", "sources": ["/etc"]}),
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
        ("list",       {"archive": "/backup/data.tar"}),
        ("create",     {"archive": "/backup/data.tar", "sources": ["/etc"]}),
        ("extract",    {"archive": "/backup/data.tar"}),
        ("verify",     {"archive": "/backup/data.tar"}),
        ("create_gz",  {"archive": "/backup/data.tar.gz", "sources": ["/etc"]}),
        ("create_bz2", {"archive": "/backup/data.tar.bz2", "sources": ["/etc"]}),
        ("create_xz",  {"archive": "/backup/data.tar.xz", "sources": ["/etc"]}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list",       {"archive": "/backup/data.tar"}),
        ("create",     {"archive": "/backup/data.tar", "sources": ["/etc"]}),
        ("extract",    {"archive": "/backup/data.tar"}),
        ("verify",     {"archive": "/backup/data.tar"}),
        ("create_gz",  {"archive": "/backup/data.tar.gz", "sources": ["/etc"]}),
        ("create_bz2", {"archive": "/backup/data.tar.bz2", "sources": ["/etc"]}),
        ("create_xz",  {"archive": "/backup/data.tar.xz", "sources": ["/etc"]}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("list",    {"archive": "/backup/data.tar"}),
        ("create",  {"archive": "/backup/data.tar", "sources": ["/etc"]}),
        ("extract", {"archive": "/backup/data.tar"}),
        ("verify",  {"archive": "/backup/data.tar"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=2, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_list(self) -> None:
        with _patch_run(_ok(stdout="etc/nginx.conf\n")):
            result = registry.dispatch("tar", "list", {"archive": "/backup/data.tar"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_create(self) -> None:
        with _patch_run(_ok()):
            result = registry.dispatch("tar", "create", {"archive": "/backup/data.tar", "sources": ["/etc"]})
        assert result.ok

    def test_dispatch_missing_archive_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'archive'"):
            registry.dispatch("tar", "list", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("tar", "bogus_op", {"archive": "/backup/data.tar"})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real tar on Rocky Linux 9")
def test_live_list_archive() -> None:
    """Live: tar --list --verbose --file on a real archive returns a ToolResult."""
    result = _execute("list", {"archive": "/tmp/test.tar"})
    assert result.exit_code in (0, 2)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real tar on Rocky Linux 9")
def test_live_create_and_list() -> None:
    """Live: create a tar archive of /tmp and then list it."""
    create_result = _execute("create", {"archive": "/tmp/test-live.tar", "sources": ["/tmp"]})
    assert create_result.exit_code is not None
    list_result = _execute("list", {"archive": "/tmp/test-live.tar"})
    assert list_result.exit_code is not None


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real tar on Rocky Linux 9")
def test_live_verify() -> None:
    """Live: tar --compare on an archive returns exit 0 or 1 (differences)."""
    result = _execute("verify", {"archive": "/tmp/test.tar"})
    assert result.exit_code in (0, 1, 2)
    assert isinstance(result.summary, str)
