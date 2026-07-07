"""tests/test_tools_systemd_timers.py — Unit tests for core/tools/systemd_timers.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without systemctl or systemd-run present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list-timers/timer-show are READ; create/enable/
    disable/systemd-run are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code=1) -> ok=False, failure summary.
  * Command vectors match expected argv shapes for every op.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * No AI/LLM/model language in any summary (I2).
  * execute() never raises for any op, including missing binary (exit 127)
    and unknown op names (I9).
  * .as_dict() always yields exactly the four expected keys.
  * DEFERRED-TO-MOSSAD: live execution tests for real systemd on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.systemd_timers.run_subprocess`` (the function in the
  systemd_timers module's namespace, bound via its local import). Patching
  there intercepts all calls from every _op_* handler.
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.systemd_timers  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.systemd_timers import SYSTEMD_TIMERS_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch run_subprocess in the systemd_timers module's own namespace."""
    return patch("core.tools.systemd_timers.run_subprocess", return_value=return_value)


def _patch_mock():
    """Return a MagicMock patcher for call-vector inspection."""
    return patch("core.tools.systemd_timers.run_subprocess")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_registered_in_registry(self) -> None:
        assert registry.get("systemd_timers") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("systemd_timers")
        assert spec is not None
        assert spec.name == "systemd_timers"

    def test_all_ops_present(self) -> None:
        spec = registry.get("systemd_timers")
        assert spec is not None
        expected = {"list-timers", "timer-show", "create", "enable", "disable", "systemd-run"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list-timers", "timer-show"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("systemd_timers", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["create", "enable", "disable", "systemd-run"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("systemd_timers", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_spec_permission_class_for(self) -> None:
        spec = registry.get("systemd_timers")
        assert spec is not None
        assert spec.permission_class_for("list-timers") is OpClass.READ
        assert spec.permission_class_for("create") is OpClass.WRITE
        assert spec.permission_class_for("nonexistent") is None


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Each op must build the exact expected argv."""

    def test_list_timers_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="NEXT LEFT\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("list-timers", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "list-timers", "--all", "--no-pager"]

    def test_timer_show_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Id=backup.timer\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("timer-show", {"timer": "backup.timer"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "show", "backup.timer", "--no-pager"]

    def test_enable_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Created symlink\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("enable", {"timer": "backup.timer"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "enable", "backup.timer"]

    def test_disable_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Removed symlink\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("disable", {"timer": "logrotate.timer"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "disable", "logrotate.timer"]

    def test_create_argv_tee(self) -> None:
        """create calls tee with the unit path, then daemon-reload."""
        mock_fn = MagicMock(return_value=_ok(stdout=""))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("create", {"timer": "backup.timer", "content": "[Timer]\nOnCalendar=daily\n"})
        # First call should be tee
        first_argv = mock_fn.call_args_list[0][0][0]
        assert first_argv[0] == "tee"
        assert "/etc/systemd/system/backup.timer" in first_argv[1]
        # Second call should be daemon-reload
        second_argv = mock_fn.call_args_list[1][0][0]
        assert second_argv == ["systemctl", "daemon-reload"]

    def test_systemd_run_basic_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Running as unit: run-abc.service\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("systemd-run", {"command": "/usr/local/bin/backup.sh"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "systemd-run"
        assert "/usr/local/bin/backup.sh" in argv

    def test_systemd_run_with_unit_name(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Running as unit: backup-now.service\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("systemd-run", {
                "command": "/usr/local/bin/backup.sh",
                "unit_name": "backup-now",
            })
        argv = mock_fn.call_args[0][0]
        assert "--unit" in argv
        unit_idx = argv.index("--unit")
        assert argv[unit_idx + 1] == "backup-now"

    def test_systemd_run_with_on_calendar(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Running as unit: run-abc.service\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            _execute("systemd-run", {
                "command": "/usr/sbin/aide --check",
                "on_calendar": "daily",
            })
        argv = mock_fn.call_args[0][0]
        assert any("--on-calendar=daily" in a for a in argv)


# ---------------------------------------------------------------------------
# list-timers operation
# ---------------------------------------------------------------------------

class TestListTimers:
    def test_success_summary(self) -> None:
        stdout = "NEXT LEFT\nbakup.timer daily\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("list-timers", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Failed to connect to bus")):
            result = _execute("list-timers", {})
        assert not result.ok
        assert "exit" in result.summary.lower() or "failed" in result.summary.lower()

    def test_stdout_preserved(self) -> None:
        with _patch(_ok(stdout="timer output here")):
            result = _execute("list-timers", {})
        assert result.stdout == "timer output here"


# ---------------------------------------------------------------------------
# timer-show operation
# ---------------------------------------------------------------------------

class TestTimerShow:
    def test_success_summary_contains_timer_name(self) -> None:
        with _patch(_ok(stdout="Id=backup.timer\nActiveState=active\n")):
            result = _execute("timer-show", {"timer": "backup.timer"})
        assert result.ok
        assert "backup.timer" in result.summary

    def test_failure_summary_contains_timer_name(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Unit backup.timer could not be found.")):
            result = _execute("timer-show", {"timer": "backup.timer"})
        assert not result.ok
        assert "backup.timer" in result.summary

    def test_result_stdout(self) -> None:
        with _patch(_ok(stdout="Id=fstrim.timer\n")):
            result = _execute("timer-show", {"timer": "fstrim.timer"})
        assert "fstrim.timer" in result.stdout


# ---------------------------------------------------------------------------
# create operation
# ---------------------------------------------------------------------------

class TestCreate:
    def test_success_summary_contains_timer_and_path(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="[Timer]\n"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            result = _execute("create", {"timer": "backup.timer", "content": "[Timer]\nOnCalendar=daily\n"})
        assert result.ok
        assert "backup.timer" in result.summary

    def test_tee_failure_returns_nonzero(self) -> None:
        # Simulate tee failing (permission denied)
        def side_effect(cmd, **kwargs):
            if cmd[0] == "tee":
                return _fail(exit_code=1, stderr="Permission denied")
            return _ok()
        with patch("core.tools.systemd_timers.run_subprocess", side_effect=side_effect):
            result = _execute("create", {"timer": "backup.timer", "content": "x"})
        assert not result.ok
        assert "backup.timer" in result.summary

    def test_daemon_reload_failure_propagated(self) -> None:
        call_count = [0]
        def side_effect(cmd, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:  # tee
                return _ok(stdout="content")
            return _fail(exit_code=1, stderr="reload error")  # daemon-reload
        with patch("core.tools.systemd_timers.run_subprocess", side_effect=side_effect):
            result = _execute("create", {"timer": "backup.timer", "content": "x"})
        assert not result.ok
        assert "backup.timer" in result.summary


# ---------------------------------------------------------------------------
# enable operation
# ---------------------------------------------------------------------------

class TestEnable:
    def test_success_summary(self) -> None:
        with _patch(_ok(stdout="Created symlink\n")):
            result = _execute("enable", {"timer": "backup.timer"})
        assert result.ok
        assert "enabled" in result.summary.lower()
        assert "backup.timer" in result.summary

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="not found")):
            result = _execute("enable", {"timer": "ghost.timer"})
        assert not result.ok
        assert "ghost.timer" in result.summary


# ---------------------------------------------------------------------------
# disable operation
# ---------------------------------------------------------------------------

class TestDisable:
    def test_success_summary(self) -> None:
        with _patch(_ok(stdout="Removed symlink\n")):
            result = _execute("disable", {"timer": "backup.timer"})
        assert result.ok
        assert "disabled" in result.summary.lower()
        assert "backup.timer" in result.summary

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="not found")):
            result = _execute("disable", {"timer": "ghost.timer"})
        assert not result.ok
        assert "ghost.timer" in result.summary


# ---------------------------------------------------------------------------
# systemd-run operation
# ---------------------------------------------------------------------------

class TestSystemdRun:
    def test_success_summary(self) -> None:
        with _patch(_ok(stdout="Running as unit: run-abc.service\n")):
            result = _execute("systemd-run", {"command": "/usr/local/bin/backup.sh"})
        assert result.ok
        assert "systemd-run" in result.summary.lower() or "scheduled" in result.summary.lower() or "unit" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="unit name already in use")):
            result = _execute("systemd-run", {"command": "/usr/local/bin/backup.sh"})
        assert not result.ok
        assert "exit" in result.summary.lower() or "failed" in result.summary.lower()

    def test_with_named_unit_in_summary(self) -> None:
        with _patch(_ok(stdout="Running as unit: my-job.service\n")):
            result = _execute("systemd-run", {
                "command": "/usr/local/bin/job.sh",
                "unit_name": "my-job",
            })
        assert result.ok
        assert "my-job" in result.summary


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("timer-show", {"timer": "backup.timer"}),
        ("enable",     {"timer": "backup.timer"}),
        ("disable",    {"timer": "backup.timer"}),
        ("systemd-run", {"command": "/usr/local/bin/job.sh"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 "
            "comm=\"systemctl\" name=\"backup.timer\""
        )
        with _patch(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        )

    def test_list_timers_avc_in_stderr_surfaces_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="AVC avc: denied { list } for pid=100")):
            result = _execute("list-timers", {})
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_create_tee_avc_in_stderr_surfaces_hint(self) -> None:
        def side_effect(cmd, **kwargs):
            return _fail(exit_code=1, stderr="AVC avc: denied { write } for comm=\"tee\"")
        with patch("core.tools.systemd_timers.run_subprocess", side_effect=side_effect):
            result = _execute("create", {"timer": "backup.timer", "content": "x"})
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Unit not found.")):
            result = _execute("enable", {"timer": "missing.timer"})
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list-timers",  {}),
        ("timer-show",   {"timer": "backup.timer"}),
        ("enable",       {"timer": "backup.timer"}),
        ("disable",      {"timer": "backup.timer"}),
        ("systemd-run",  {"command": "/usr/local/bin/job.sh"}),
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
        ("list-timers",  {}),
        ("timer-show",   {"timer": "backup.timer"}),
        ("enable",       {"timer": "backup.timer"}),
        ("disable",      {"timer": "backup.timer"}),
        ("systemd-run",  {"command": "/usr/local/bin/job.sh"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}

    def test_create_result_has_required_fields(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="content"))
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            result = _execute("create", {"timer": "t.timer", "content": "[Timer]\n"})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert set(result.as_dict().keys()) == {"exit_code", "stdout", "stderr", "summary"}
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# No AI language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list-timers",  {}),
        ("timer-show",   {"timer": "backup.timer"}),
        ("enable",       {"timer": "backup.timer"}),
        ("disable",      {"timer": "backup.timer"}),
        ("systemd-run",  {"command": "/usr/local/bin/job.sh"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("list-timers",  {}),
        ("timer-show",   {"timer": "backup.timer"}),
        ("enable",       {"timer": "backup.timer"}),
        ("disable",      {"timer": "backup.timer"}),
        ("systemd-run",  {"command": "/usr/local/bin/job.sh"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )

    def test_no_ai_language_in_create_success(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            result = _execute("create", {"timer": "b.timer", "content": "[Timer]\n"})
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in create success summary"
            )

    def test_no_ai_language_in_unknown_op_summary(self) -> None:
        result = _execute("nonexistent_op", {})
        for word in self._FORBIDDEN:
            assert word not in result.summary


# ---------------------------------------------------------------------------
# execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("totally_bogus_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "totally_bogus_op" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """Simulate what run_subprocess returns when the binary is absent."""
        missing_binary = ToolResult(
            exit_code=127, stdout="", stderr="", summary="command not found: systemctl"
        )
        with _patch(missing_binary):
            result = _execute("list-timers", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    @pytest.mark.parametrize("op,args", [
        ("list-timers",  {}),
        ("timer-show",   {"timer": "x.timer"}),
        ("enable",       {"timer": "x.timer"}),
        ("disable",      {"timer": "x.timer"}),
        ("systemd-run",  {"command": "/usr/bin/true"}),
    ])
    def test_no_exception_on_exit_127(self, op: str, args: dict) -> None:
        not_found = ToolResult(exit_code=127, stdout="", stderr="", summary="command not found")
        with _patch(not_found):
            try:
                result = _execute(op, args)
                assert result.exit_code == 127
            except Exception as exc:
                pytest.fail(f"_execute raised {type(exc).__name__} for op '{op}': {exc}")

    def test_create_no_exception_on_tee_exit_127(self) -> None:
        not_found = ToolResult(exit_code=127, stdout="", stderr="", summary="command not found: tee")
        mock_fn = MagicMock(return_value=not_found)
        with patch("core.tools.systemd_timers.run_subprocess", mock_fn):
            try:
                result = _execute("create", {"timer": "b.timer", "content": "[Timer]\n"})
                assert isinstance(result, ToolResult)
            except Exception as exc:
                pytest.fail(f"_execute raised for create with missing binary: {exc}")


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_list_timers(self) -> None:
        with _patch(_ok(stdout="timer output")):
            result = registry.dispatch("systemd_timers", "list-timers", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_timer_show(self) -> None:
        with _patch(_ok(stdout="Id=backup.timer")):
            result = registry.dispatch("systemd_timers", "timer-show", {"timer": "backup.timer"})
        assert result.ok

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'timer'"):
            registry.dispatch("systemd_timers", "timer-show", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("systemd_timers", "totally_unknown_op", {})

    def test_dispatch_enable(self) -> None:
        with _patch(_ok(stdout="Created symlink")):
            result = registry.dispatch("systemd_timers", "enable", {"timer": "backup.timer"})
        assert result.ok


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl on Rocky Linux 9")
def test_live_list_timers() -> None:
    """Live: systemctl list-timers --all --no-pager returns a populated result."""
    result = _execute("list-timers", {})
    assert result.exit_code == 0
    assert len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl on Rocky Linux 9")
def test_live_timer_show_logrotate() -> None:
    """Live: systemctl show logrotate.timer returns properties."""
    result = _execute("timer-show", {"timer": "logrotate.timer"})
    assert result.exit_code in (0, 4)  # 0=found, 4=not found
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real systemctl on Rocky Linux 9")
def test_live_enable_requires_sudo() -> None:
    """Live: systemctl enable on Rocky requires elevated privileges.

    Run as root or with sudo to verify the WRITE gate works end-to-end.
    """
    result = _execute("enable", {"timer": "backup.timer"})
    assert result.exit_code is not None
