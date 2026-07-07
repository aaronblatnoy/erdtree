"""tests/test_tools_cron.py — Unit tests for core/tools/cron.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without crontab, tee, cat, or ls present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/list-all/crond-view are READ; edit/crond-add are
    WRITE; remove is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code!=0) → ok=False, failure summary naming the target.
  * Command vectors: exact argv list asserted for each op.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises (I9) — unknown op and exit_code=127 (missing binary)
    both return a well-formed ToolResult.
  * I2 invariant: no AI/LLM/model/agent/agentic/neural/language model language
    in any summary (success or failure).
  * ToolResult.as_dict() returns exactly the four expected keys.
  * DEFERRED-TO-MOSSAD: live execution tests against real crontab on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.cron.run_subprocess`` (the binding in the cron module's
  namespace, established by the ``from core.tools import run_subprocess`` import).
  The ToolSpec.execute callable calls this module-level binding, so patching
  there intercepts all subprocess calls.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.cron  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.cron import CRON_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.cron.run_subprocess."""
    return patch("core.tools.cron.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_cron_registered_in_module_registry(self) -> None:
        assert registry.get("cron") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("cron")
        assert spec is not None
        assert spec.name == "cron"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("cron")
        assert spec is not None
        expected = {"list", "list-all", "edit", "remove", "crond-view", "crond-add"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list", "list-all", "crond-view"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("cron", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["edit", "crond-add"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("cron", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_remove_is_destructive(self) -> None:
        cls = registry.permission_class_for("cron", "remove")
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for 'remove', got {cls}"

    def test_spec_permission_class_for_remove(self) -> None:
        cls = CRON_SPEC.permission_class_for("remove")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors — assert the exact argv list passed to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Verify that each op calls run_subprocess with the correct argv."""

    def test_list_no_user(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="# crontab\n"))
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("list", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["crontab", "-l"]

    def test_list_with_user(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="# crontab\n"))
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("list", {"user": "deploy"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["crontab", "-l", "-u", "deploy"]

    def test_list_all_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="total 4\n"))
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("list-all", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["ls", "-la", "/var/spool/cron/"]

    def test_edit_no_user(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("edit", {"content": "* * * * * /bin/true\n"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["crontab", "-"]

    def test_edit_with_user(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("edit", {"content": "0 2 * * * /backup.sh\n", "user": "backup"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["crontab", "-u", "backup", "-"]

    def test_edit_passes_content_as_input(self) -> None:
        content = "0 2 * * * /usr/local/bin/backup.sh\n"
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("edit", {"content": content})
        kwargs = mock_fn.call_args[1]
        assert kwargs.get("input") == content

    def test_remove_no_user(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("remove", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["crontab", "-r"]

    def test_remove_with_user(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("remove", {"user": "legacy"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["crontab", "-r", "-u", "legacy"]

    def test_crond_view_no_name_lists_directory(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="total 8\n"))
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("crond-view", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["ls", "-la", "/etc/cron.d/"]

    def test_crond_view_with_name_cats_file(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="# content\n"))
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("crond-view", {"name": "backup-jobs"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["cat", "/etc/cron.d/backup-jobs"]

    def test_crond_add_command_and_input(self) -> None:
        content = "0 3 * * * root /usr/local/bin/job.sh\n"
        mock_fn = MagicMock(return_value=_ok_result(stdout=content))
        with patch("core.tools.cron.run_subprocess", mock_fn):
            _execute("crond-add", {"name": "myjob", "content": content})
        cmd = mock_fn.call_args[0][0]
        kwargs = mock_fn.call_args[1]
        assert cmd == ["tee", "/etc/cron.d/myjob"]
        assert kwargs.get("input") == content


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure branches
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_list_success(self) -> None:
        with _patch_run(_ok_result(stdout="0 2 * * * /backup.sh\n")):
            result = _execute("list", {})
        assert result.ok
        assert result.exit_code == 0
        assert len(result.summary) > 0

    def test_list_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="no crontab for user")):
            result = _execute("list", {"user": "missing"})
        assert not result.ok
        assert result.exit_code == 1
        assert "missing" in result.summary

    def test_list_all_success(self) -> None:
        with _patch_run(_ok_result(stdout="total 8\n-rw------- 1 root root 100 Jul 1 deploy\n")):
            result = _execute("list-all", {})
        assert result.ok

    def test_list_all_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Permission denied")):
            result = _execute("list-all", {})
        assert not result.ok
        assert "exit 1" in result.summary or "Failed" in result.summary

    def test_edit_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("edit", {"content": "0 2 * * * /backup.sh\n"})
        assert result.ok
        assert "updated" in result.summary.lower()

    def test_edit_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="bad minute")):
            result = _execute("edit", {"content": "bad entry", "user": "root"})
        assert not result.ok
        assert "root" in result.summary

    def test_remove_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("remove", {})
        assert result.ok
        assert "removed" in result.summary.lower()

    def test_remove_with_user_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("remove", {"user": "deploy"})
        assert result.ok
        assert "deploy" in result.summary

    def test_remove_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="user not found")):
            result = _execute("remove", {"user": "nobody"})
        assert not result.ok
        assert "nobody" in result.summary

    def test_crond_view_no_name_success(self) -> None:
        with _patch_run(_ok_result(stdout="total 8\n-rw-r--r-- 1 root root 100 Jul 1 aide\n")):
            result = _execute("crond-view", {})
        assert result.ok

    def test_crond_view_with_name_success(self) -> None:
        with _patch_run(_ok_result(stdout="# cron.d content\n")):
            result = _execute("crond-view", {"name": "aide"})
        assert result.ok
        assert "aide" in result.summary

    def test_crond_view_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="No such file or directory")):
            result = _execute("crond-view", {"name": "nonexistent"})
        assert not result.ok
        assert "nonexistent" in result.summary

    def test_crond_add_success(self) -> None:
        content = "0 3 * * * root /usr/local/bin/job.sh\n"
        with _patch_run(_ok_result(stdout=content)):
            result = _execute("crond-add", {"name": "backup-jobs", "content": content})
        assert result.ok
        assert "backup-jobs" in result.summary

    def test_crond_add_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Permission denied")):
            result = _execute("crond-add", {"name": "protected", "content": "data\n"})
        assert not result.ok
        assert "protected" in result.summary


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("list",       {}),
        ("list-all",   {}),
        ("edit",       {"content": "0 2 * * * /backup.sh\n"}),
        ("remove",     {}),
        ("crond-view", {}),
        ("crond-add",  {"name": "test", "content": "data\n"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"crontab\" name=\"crontab\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint not found for op={op!r}: {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="no crontab for user")):
            result = _execute("list", {})
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary

    def test_permission_denied_surfaces_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Permission denied")):
            result = _execute("crond-view", {"name": "protected"})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        # Should NOT raise; must return a well-formed ToolResult
        result = _execute("completely-bogus-op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_missing_binary_exit_127(self) -> None:
        # Simulate run_subprocess returning exit_code=127 (FileNotFoundError inside)
        with _patch_run(_fail_result(exit_code=127, stderr="command not found")):
            result = _execute("list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    @pytest.mark.parametrize("op,args", [
        ("list",       {}),
        ("list-all",   {}),
        ("edit",       {"content": "data\n"}),
        ("remove",     {}),
        ("crond-view", {}),
        ("crond-add",  {"name": "x", "content": "data\n"}),
    ])
    def test_every_op_with_exit_127_returns_toolresult(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=127)):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list",       {}),
        ("list-all",   {}),
        ("edit",       {"content": "0 2 * * * /backup.sh\n"}),
        ("remove",     {}),
        ("crond-view", {}),
        ("crond-view", {"name": "aide"}),
        ("crond-add",  {"name": "myjob", "content": "0 3 * * * root /job.sh\n"}),
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
        ("list",       {}),
        ("list-all",   {}),
        ("edit",       {"content": "data\n"}),
        ("remove",     {}),
        ("crond-view", {}),
        ("crond-add",  {"name": "x", "content": "data\n"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary — I2 invariant
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list",       {}),
        ("list-all",   {}),
        ("edit",       {"content": "0 2 * * * /backup.sh\n"}),
        ("remove",     {}),
        ("crond-view", {}),
        ("crond-view", {"name": "aide"}),
        ("crond-add",  {"name": "myjob", "content": "data\n"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("list",       {"user": "baduser"}),
        ("edit",       {"content": "bad\n", "user": "baduser"}),
        ("remove",     {"user": "baduser"}),
        ("crond-view", {"name": "badfile"}),
        ("crond-add",  {"name": "badname", "content": "data\n"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error occurred")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    """Verify the full router path: registry.dispatch() calls _execute()."""

    def test_dispatch_list(self) -> None:
        with _patch_run(_ok_result(stdout="# crontab\n0 2 * * * /backup.sh\n")):
            result = registry.dispatch("cron", "list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_remove(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("cron", "remove", {})
        assert result.ok

    def test_dispatch_crond_add_missing_name_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'name'"):
            registry.dispatch("cron", "crond-add", {"content": "data\n"})

    def test_dispatch_edit_missing_content_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'content'"):
            registry.dispatch("cron", "edit", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("cron", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real crontab on Rocky Linux 9")
def test_live_list_current_user() -> None:
    """Live: crontab -l returns a ToolResult (may exit 1 if no crontab exists)."""
    result = _execute("list", {})
    assert result.exit_code in (0, 1)  # 0=has crontab, 1=no crontab for user


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root on Rocky Linux 9")
def test_live_list_all() -> None:
    """Live: ls /var/spool/cron/ lists user crontab files (requires root)."""
    result = _execute("list-all", {})
    assert result.exit_code in (0, 1, 2)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real crontab on Rocky Linux 9")
def test_live_crond_view_directory() -> None:
    """Live: ls /etc/cron.d/ returns directory listing."""
    result = _execute("crond-view", {})
    assert result.exit_code == 0
    assert "0hourly" in result.stdout or len(result.stdout) > 0
