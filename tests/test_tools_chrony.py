"""tests/test_tools_chrony.py — Unit tests for core/tools/chrony.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without chronyc or systemctl present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: tracking/sources/status/conf_view are READ;
    makestep/conf_edit are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary naming the exit code.
  * Command vectors: exact argv list asserted for each op.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2: no AI/LLM/model/agent language in any summary.
  * execute() NEVER raises (I9): unknown op and exit-127 both return ToolResult.
  * as_dict() yields exactly the four required keys.
  * DEFERRED-TO-MOSSAD: live execution tests on Rocky Linux 9.

Mocking strategy
----------------
  Patch ``core.tools.chrony.run_subprocess`` (the binding in the chrony
  module's namespace, not the shared core.tools one) to return controlled
  ToolResult fixtures without launching real processes.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration side-effect.
import core.tools.chrony  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.chrony import CHRONY_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch run_subprocess in the chrony module namespace."""
    return patch("core.tools.chrony.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_chrony_registered(self) -> None:
        assert registry.get("chrony") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("chrony")
        assert spec is not None
        assert spec.name == "chrony"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("chrony")
        assert spec is not None
        expected = {"tracking", "sources", "status", "makestep", "conf_view", "conf_edit"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["tracking", "sources", "status", "conf_view"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("chrony", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["makestep", "conf_edit"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("chrony", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — assert exact argv list for each operation
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_tracking_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.chrony.run_subprocess", mock_fn):
            _execute("tracking", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["chronyc", "tracking"]

    def test_sources_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.chrony.run_subprocess", mock_fn):
            _execute("sources", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["chronyc", "sources"]

    def test_status_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.chrony.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "status", "--no-pager", "chronyd"]

    def test_makestep_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.chrony.run_subprocess", mock_fn):
            _execute("makestep", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["chronyc", "makestep"]

    def test_conf_view_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.chrony.run_subprocess", mock_fn):
            _execute("conf_view", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["cat", "/etc/chrony.conf"]

    def test_conf_edit_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="pool ntp.example.com iburst\n"))
        with patch("core.tools.chrony.run_subprocess", mock_fn):
            _execute("conf_edit", {"content": "pool ntp.example.com iburst\n"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tee", "/etc/chrony.conf"]

    def test_conf_edit_passes_input_kwarg(self) -> None:
        """conf_edit must pass content via input= to run_subprocess."""
        mock_fn = MagicMock(return_value=_ok())
        content = "server 10.0.0.1 iburst\n"
        with patch("core.tools.chrony.run_subprocess", mock_fn):
            _execute("conf_edit", {"content": content})
        kwargs = mock_fn.call_args[1]
        assert kwargs.get("input") == content


# ---------------------------------------------------------------------------
# Exit-code mapping (success / failure)
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
        ("makestep", {}),
        ("conf_view", {}),
        ("conf_edit", {"content": "pool 2.rocky.pool.ntp.org iburst\n"}),
    ])
    def test_exit_0_is_ok(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="some output")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
        ("makestep", {}),
        ("conf_view", {}),
        ("conf_edit", {"content": "pool 2.rocky.pool.ntp.org iburst\n"}),
    ])
    def test_nonzero_exit_is_not_ok(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1
        assert "1" in result.summary or "exit" in result.summary.lower() or len(result.summary) > 0

    def test_tracking_failure_summary_contains_exit_code(self) -> None:
        with _patch(_fail(exit_code=2)):
            result = _execute("tracking", {})
        assert not result.ok
        assert "2" in result.summary

    def test_status_failure_summary_mentions_chronyd(self) -> None:
        with _patch(_fail(exit_code=3)):
            result = _execute("status", {})
        assert not result.ok
        assert "chronyd" in result.summary.lower()

    def test_conf_edit_success_summary(self) -> None:
        with _patch(_ok()):
            result = _execute("conf_edit", {"content": "server 10.0.0.1 iburst\n"})
        assert result.ok
        assert "chrony.conf" in result.summary

    def test_conf_view_success_summary(self) -> None:
        with _patch(_ok(stdout="pool 2.rocky.pool.ntp.org iburst\n")):
            result = _execute("conf_view", {})
        assert result.ok
        assert "chrony.conf" in result.summary

    def test_makestep_success_summary(self) -> None:
        with _patch(_ok(stdout="200 OK\n")):
            result = _execute("makestep", {})
        assert result.ok
        assert "clock" in result.summary.lower() or "step" in result.summary.lower()


# ---------------------------------------------------------------------------
# I2 — No AI / model / LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
        ("makestep", {}),
        ("conf_view", {}),
        ("conf_edit", {"content": "pool 2.rocky.pool.ntp.org iburst\n"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
        ("makestep", {}),
        ("conf_view", {}),
        ("conf_edit", {"content": "pool 2.rocky.pool.ntp.org iburst\n"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="some error")):
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
        "AVC avc: denied { read } for pid=1234 "
        "comm=\"chronyc\" name=\"chrony.conf\" scontext=system_u"
    )

    @pytest.mark.parametrize("op,args", [
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
        ("makestep", {}),
        ("conf_view", {}),
        ("conf_edit", {"content": "pool 2.rocky.pool.ntp.org iburst\n"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"SELinux hint not surfaced for op='{op}': {result.summary!r}"
        )

    @pytest.mark.parametrize("op,args", [
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="Connection refused")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"SELinux hint should NOT be present for clean stderr, op='{op}'"
        )


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
        ("makestep", {}),
        ("conf_view", {}),
        ("conf_edit", {"content": "pool 2.rocky.pool.ntp.org iburst\n"}),
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
        ("tracking", {}),
        ("sources", {}),
        ("status", {}),
        ("makestep", {}),
        ("conf_view", {}),
        ("conf_edit", {"content": "x"}),
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
    def test_unknown_op_returns_toolresult(self) -> None:
        """An unknown op must NOT raise — it returns a well-formed ToolResult."""
        result = _execute("totally_bogus_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert "totally_bogus_op" in result.summary

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """A missing binary (exit 127) must degrade gracefully, not raise."""
        missing_bin = ToolResult(exit_code=127, stdout="", stderr="chronyc: command not found", summary="")
        with _patch(missing_bin):
            result = _execute("tracking", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_on_status(self) -> None:
        missing_bin = ToolResult(exit_code=127, stdout="", stderr="systemctl: command not found", summary="")
        with _patch(missing_bin):
            result = _execute("status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_missing_binary_on_conf_edit(self) -> None:
        missing_bin = ToolResult(exit_code=127, stdout="", stderr="tee: command not found", summary="")
        with _patch(missing_bin):
            result = _execute("conf_edit", {"content": "pool 2.rocky.pool.ntp.org iburst\n"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_tracking(self) -> None:
        with _patch(_ok(stdout="Reference ID")):
            result = registry.dispatch("chrony", "tracking", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_sources(self) -> None:
        with _patch(_ok(stdout="MS Name/IP")):
            result = registry.dispatch("chrony", "sources", {})
        assert result.ok

    def test_dispatch_conf_edit_missing_required_arg_raises(self) -> None:
        """content is required for conf_edit — missing it must raise TypeError."""
        with pytest.raises(TypeError, match="requires argument 'content'"):
            registry.dispatch("chrony", "conf_edit", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("chrony", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires chronyc on Rocky Linux 9")
def test_live_tracking() -> None:
    """Live: chronyc tracking returns a populated ToolResult."""
    result = _execute("tracking", {})
    assert result.exit_code in (0, 1)
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires chronyc on Rocky Linux 9")
def test_live_sources() -> None:
    """Live: chronyc sources returns source table."""
    result = _execute("sources", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires systemctl on Rocky Linux 9")
def test_live_status() -> None:
    """Live: systemctl status chronyd returns a meaningful result."""
    result = _execute("status", {})
    assert result.exit_code in (0, 3, 4)
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root + chronyc on Rocky Linux 9")
def test_live_makestep_requires_root() -> None:
    """Live: chronyc makestep requires root or appropriate capabilities.

    Run as root to confirm the clock is stepped. As a regular user it returns
    non-zero and surfaces a permission error in stderr.
    """
    result = _execute("makestep", {})
    assert result.exit_code is not None
