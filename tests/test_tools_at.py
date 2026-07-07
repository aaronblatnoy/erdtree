"""tests/test_tools_at.py — Unit tests for core/tools/at.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without at, atq, or atrm present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: atq is READ; schedule is WRITE; atrm is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful I2-clean summary.
  * Failed exit (exit_code != 0) -> ok=False, failure summary with context.
  * Command vector assertions: argv list is exactly right for each op,
    including the destructive 'atrm' argv.
  * SELinux AVC hint surfaces when stderr contains AVC language.
  * execute() never raises (I9): unknown op and missing binary both degrade
    to a well-formed ToolResult.
  * I2 hygiene: no AI/LLM/model/agent/agentic/neural language in summaries.
  * DEFERRED-TO-MOSSAD: live execution against real at/atq/atrm on Rocky 9.

Mocking strategy
----------------
  Patch ``core.tools.at.run_subprocess`` (the binding in the at module's
  own namespace, imported via 'from core.tools import run_subprocess').
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Side-effect import: triggers registry.register(AT_SPEC) at import time.
import core.tools.at  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.at import AT_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    return patch("core.tools.at.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered(self) -> None:
        assert registry.get("at") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("at")
        assert spec is not None
        assert spec.name == "at"

    def test_all_ops_present(self) -> None:
        spec = registry.get("at")
        assert spec is not None
        assert set(spec.ops.keys()) == {"atq", "schedule", "atrm"}


# ---------------------------------------------------------------------------
# 2. Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    def test_atq_is_read(self) -> None:
        cls = registry.permission_class_for("at", "atq")
        assert cls is OpClass.READ

    def test_schedule_is_write(self) -> None:
        cls = registry.permission_class_for("at", "schedule")
        assert cls is OpClass.WRITE

    def test_atrm_is_destructive(self) -> None:
        cls = registry.permission_class_for("at", "atrm")
        assert cls is OpClass.DESTRUCTIVE

    @pytest.mark.parametrize("op,expected", [
        ("atq", OpClass.READ),
        ("schedule", OpClass.WRITE),
        ("atrm", OpClass.DESTRUCTIVE),
    ])
    def test_permission_class_parametrized(self, op: str, expected: OpClass) -> None:
        assert registry.permission_class_for("at", op) is expected


# ---------------------------------------------------------------------------
# 3. Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_atq_no_queue(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.at.run_subprocess", mock_fn):
            _execute("atq", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["atq"]

    def test_atq_with_queue(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.at.run_subprocess", mock_fn):
            _execute("atq", {"queue": "b"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["atq", "-q", "b"]

    def test_schedule_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.at.run_subprocess", mock_fn):
            _execute("schedule", {"time": "midnight", "command": "echo hi"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["at", "midnight"]

    def test_schedule_passes_command_via_input(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.at.run_subprocess", mock_fn):
            _execute("schedule", {"time": "now + 1 hour", "command": "/usr/local/bin/backup.sh"})
        kwargs = mock_fn.call_args[1]
        assert kwargs.get("input") == "/usr/local/bin/backup.sh"

    def test_atrm_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.at.run_subprocess", mock_fn):
            _execute("atrm", {"job_id": "7"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["atrm", "7"]

    def test_atrm_argv_includes_job_id(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.at.run_subprocess", mock_fn):
            _execute("atrm", {"job_id": "42"})
        argv = mock_fn.call_args[0][0]
        assert "atrm" in argv
        assert "42" in argv


# ---------------------------------------------------------------------------
# 4. Exit-code mapping and summaries
# ---------------------------------------------------------------------------

class TestAtq:
    def test_success_empty_queue(self) -> None:
        with _patch(_ok(stdout="")):
            result = _execute("atq", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_success_jobs_listed(self) -> None:
        jobs = "1\tThu Jul  4 22:00:00 2026 a\troot\n2\tThu Jul  4 23:00:00 2026 a\troot\n"
        with _patch(_ok(stdout=jobs)):
            result = _execute("atq", {})
        assert result.ok
        assert "2" in result.summary

    def test_failure_returns_nonzero(self) -> None:
        with _patch(_fail(exit_code=1, stderr="atq: cannot open spool")):
            result = _execute("atq", {})
        assert not result.ok
        assert result.exit_code == 1
        assert "exit" in result.summary


class TestSchedule:
    def test_success(self) -> None:
        stderr = "warning: commands will be executed using /bin/sh\njob 3 at midnight\n"
        with _patch(_ok(stderr=stderr)):
            result = _execute("schedule", {"time": "midnight", "command": "echo done"})
        assert result.ok
        assert "midnight" in result.summary

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Garbled time")):
            result = _execute("schedule", {"time": "invalidtime", "command": "echo x"})
        assert not result.ok
        assert "invalidtime" in result.summary
        assert "exit" in result.summary

    def test_success_summary_mentions_time(self) -> None:
        with _patch(_ok()):
            result = _execute("schedule", {"time": "noon tomorrow", "command": "/bin/true"})
        assert "noon tomorrow" in result.summary


class TestAtrm:
    def test_success(self) -> None:
        with _patch(_ok()):
            result = _execute("atrm", {"job_id": "5"})
        assert result.ok
        assert "5" in result.summary
        assert "removed" in result.summary.lower()

    def test_failure_no_such_job(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Cannot find jobid 99")):
            result = _execute("atrm", {"job_id": "99"})
        assert not result.ok
        assert "99" in result.summary
        assert "exit" in result.summary

    def test_atrm_is_destructive_class(self) -> None:
        assert AT_SPEC.permission_class_for("atrm") is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# 5. I2 — no AI language in summaries
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("atq",      {}),
        ("schedule", {"time": "midnight", "command": "echo hi"}),
        ("atrm",     {"job_id": "1"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("atq",      {}),
        ("schedule", {"time": "midnight", "command": "echo hi"}),
        ("atrm",     {"job_id": "1"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="error occurred")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# 6. SELinux hint
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC = (
        "atrm: AVC avc: denied { write } for pid=2345 comm=\"atrm\" "
        "name=\"spool\" dev=\"xfs\" ino=12345"
    )

    @pytest.mark.parametrize("op,args", [
        ("atq",      {}),
        ("schedule", {"time": "midnight", "command": "echo hi"}),
        ("atrm",     {"job_id": "3"}),
    ])
    def test_avc_in_stderr_surfaces_selinux_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Cannot find jobid 99")):
            result = _execute("atrm", {"job_id": "99"})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# 7. execute() NEVER raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        missing = ToolResult(exit_code=127, stdout="", stderr="at: command not found", summary="")
        with _patch(missing):
            result = _execute("atq", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_timeout_exit_124(self) -> None:
        timeout_r = ToolResult(exit_code=124, stdout="", stderr="", summary="")
        with _patch(timeout_r):
            result = _execute("schedule", {"time": "midnight", "command": "sleep 999"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124

    def test_no_exception_for_atrm_exit127(self) -> None:
        r = ToolResult(exit_code=127, stdout="", stderr="atrm: command not found", summary="")
        with _patch(r):
            result = _execute("atrm", {"job_id": "5"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# 8. ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("atq",      {}),
        ("schedule", {"time": "midnight", "command": "echo hi"}),
        ("atrm",     {"job_id": "3"}),
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
        ("atq",      {}),
        ("schedule", {"time": "midnight", "command": "echo hi"}),
        ("atrm",     {"job_id": "3"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real atq on Rocky Linux 9")
def test_live_atq() -> None:
    """Live: atq lists (possibly empty) queue without error."""
    result = _execute("atq", {})
    assert result.exit_code == 0
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real at on Rocky Linux 9")
def test_live_schedule_and_remove() -> None:
    """Live: schedule an echo job for now+1min then remove it."""
    result = _execute("schedule", {"time": "now + 1 minute", "command": "echo erdtree-test"})
    assert result.exit_code == 0
    # Extract job id from stderr: "job N at ..."
    import re
    m = re.search(r"job (\d+)", result.stderr)
    assert m is not None
    job_id = m.group(1)
    rm_result = _execute("atrm", {"job_id": job_id})
    assert rm_result.exit_code == 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real atrm on Rocky Linux 9")
def test_live_atrm_nonexistent() -> None:
    """Live: atrm on a non-existent job id returns non-zero."""
    result = _execute("atrm", {"job_id": "99999"})
    assert result.exit_code != 0
