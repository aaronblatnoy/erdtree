"""tests/test_tools_hostname.py — Unit tests for core/tools/hostname.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without hostnamectl, cat, or tee present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/hosts-view are READ; set-hostname/hosts-edit are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code=1) → ok=False, failure summary with exit code.
  * Command vectors: exact argv passed to run_subprocess for each op.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * Clean stderr does NOT surface the hint.
  * I2: no AI/LLM/model/agent language in any summary.
  * I9: execute() NEVER raises — unknown ops and missing binaries (exit 127)
    degrade to well-formed ToolResult, no exception.
  * as_dict() always returns exactly the four required keys.
  * DEFERRED-TO-MOSSAD: live execution against real hostnamectl on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.hostname.run_subprocess`` (the function in the
  hostname module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.hostname  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.hostname import HOSTNAME_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.hostname.run_subprocess."""
    return patch("core.tools.hostname.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_hostname_registered_in_module_registry(self) -> None:
        assert registry.get("hostname") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("hostname")
        assert spec is not None
        assert spec.name == "hostname"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("hostname")
        assert spec is not None
        expected = {"status", "set-hostname", "hosts-view", "hosts-edit"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "hosts-view"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("hostname", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["set-hostname", "hosts-edit"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("hostname", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vector tests
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_status_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Static hostname: myhost"))
        with patch("core.tools.hostname.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["hostnamectl", "status"]

    def test_set_hostname_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.hostname.run_subprocess", mock_fn):
            _execute("set-hostname", {"name": "webserver-01.example.com"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["hostnamectl", "set-hostname", "webserver-01.example.com"]

    def test_hosts_view_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="127.0.0.1 localhost\n"))
        with patch("core.tools.hostname.run_subprocess", mock_fn):
            _execute("hosts-view", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["cat", "/etc/hosts"]

    def test_hosts_edit_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="10.0.1.5\tdb.internal\n"))
        with patch("core.tools.hostname.run_subprocess", mock_fn):
            _execute("hosts-edit", {"entry": "10.0.1.5\tdb.internal"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["tee", "-a", "/etc/hosts"]

    def test_hosts_edit_passes_entry_as_input(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="10.0.1.5\tdb.internal\n"))
        with patch("core.tools.hostname.run_subprocess", mock_fn):
            _execute("hosts-edit", {"entry": "10.0.1.5\tdb.internal"})
        kwargs = mock_fn.call_args[1]
        assert "input" in kwargs
        assert "10.0.1.5" in kwargs["input"]
        assert "db.internal" in kwargs["input"]


# ---------------------------------------------------------------------------
# status operation
# ---------------------------------------------------------------------------

class TestStatus:
    def test_success_summary(self) -> None:
        stdout = (
            "   Static hostname: myhost.example.com\n"
            "  Operating System: Rocky Linux 9.3\n"
        )
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("status", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Failed to connect to bus")):
            result = _execute("status", {})
        assert not result.ok
        assert result.exit_code == 1
        assert len(result.summary) > 0

    def test_result_has_stdout(self) -> None:
        stdout = "Static hostname: testhost\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("status", {})
        assert result.stdout == stdout


# ---------------------------------------------------------------------------
# set-hostname operation
# ---------------------------------------------------------------------------

class TestSetHostname:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("set-hostname", {"name": "webserver-01.example.com"})
        assert result.ok
        assert "webserver-01.example.com" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Invalid hostname")):
            result = _execute("set-hostname", {"name": "-invalid"})
        assert not result.ok
        assert "-invalid" in result.summary
        assert str(1) in result.summary

    def test_name_in_success_summary(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("set-hostname", {"name": "db-primary.prod.internal"})
        assert "db-primary.prod.internal" in result.summary


# ---------------------------------------------------------------------------
# hosts-view operation
# ---------------------------------------------------------------------------

class TestHostsView:
    def test_success_summary(self) -> None:
        stdout = "127.0.0.1   localhost\n::1         localhost\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("hosts-view", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="cat: /etc/hosts: Permission denied")):
            result = _execute("hosts-view", {})
        assert not result.ok

    def test_result_has_stdout(self) -> None:
        stdout = "127.0.0.1 localhost\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("hosts-view", {})
        assert result.stdout == stdout

    def test_summary_mentions_line_count(self) -> None:
        stdout = "127.0.0.1 localhost\n::1 localhost\n# comment\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("hosts-view", {})
        assert result.ok
        # summary should mention the count or "Hosts"
        assert any(
            token in result.summary
            for token in ("3", "lines", "Hosts", "hosts")
        )


# ---------------------------------------------------------------------------
# hosts-edit operation
# ---------------------------------------------------------------------------

class TestHostsEdit:
    def test_success(self) -> None:
        entry = "10.0.1.5\tdb-primary.internal"
        with _patch_run(_ok_result(stdout=entry + "\n")):
            result = _execute("hosts-edit", {"entry": entry})
        assert result.ok
        assert "10.0.1.5" in result.summary or "db-primary.internal" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="tee: /etc/hosts: Permission denied")):
            result = _execute("hosts-edit", {"entry": "10.0.1.5\tdb.internal"})
        assert not result.ok
        assert result.exit_code == 1

    def test_entry_in_success_summary(self) -> None:
        entry = "192.168.1.100\tcache-01.local"
        with _patch_run(_ok_result(stdout=entry + "\n")):
            result = _execute("hosts-edit", {"entry": entry})
        assert result.ok
        # The summary should reference the appended entry text
        assert "192.168.1.100" in result.summary or "cache-01.local" in result.summary


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("set-hostname", {"name": "testhost.example.com"}),
        ("hosts-view", {}),
        ("hosts-edit", {"entry": "10.0.0.1\ttest.local"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { open } for pid=1234 comm=\"hostnamectl\" "
            "name=\"hostname\" dev=\"tmpfs\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint for op='{op}'"

    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("set-hostname", {"name": "testhost.example.com"}),
        ("hosts-view", {}),
        ("hosts-edit", {"entry": "10.0.0.1\ttest.local"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Unit not found.")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"SELinux hint should not appear on clean stderr for op='{op}'"
        )


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("set-hostname", {"name": "testhost.example.com"}),
        ("hosts-view", {}),
        ("hosts-edit", {"entry": "10.0.0.1\ttest.local"}),
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
        ("status", {}),
        ("set-hostname", {"name": "testhost.example.com"}),
        ("hosts-view", {}),
        ("hosts-edit", {"entry": "10.0.0.1\ttest.local"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("set-hostname", {"name": "testhost.example.com"}),
        ("hosts-view", {}),
        ("hosts-edit", {"entry": "10.0.0.1\ttest.local"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("set-hostname", {"name": "testhost.example.com"}),
        ("hosts-view", {}),
        ("hosts-edit", {"entry": "10.0.0.1\ttest.local"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        """I9: an unknown op must return a well-formed ToolResult, not raise."""
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert "nonexistent_op" in result.summary

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """I9: exit 127 (binary not found) must degrade to a ToolResult."""
        with _patch_run(_fail_result(exit_code=127, stderr="hostnamectl: command not found")):
            result = _execute("status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_unknown_op_as_dict_has_four_keys(self) -> None:
        result = _execute("bogus_op", {})
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_status(self) -> None:
        with _patch_run(_ok_result(stdout="Static hostname: myhost")):
            result = registry.dispatch("hostname", "status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_hosts_view(self) -> None:
        with _patch_run(_ok_result(stdout="127.0.0.1 localhost\n")):
            result = registry.dispatch("hostname", "hosts-view", {})
        assert result.ok

    def test_dispatch_set_hostname_missing_name_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'name'"):
            registry.dispatch("hostname", "set-hostname", {})

    def test_dispatch_hosts_edit_missing_entry_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'entry'"):
            registry.dispatch("hostname", "hosts-edit", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("hostname", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real hostnamectl on Rocky Linux 9")
def test_live_status() -> None:
    """Live: hostnamectl status returns a populated ToolResult."""
    result = _execute("status", {})
    assert result.exit_code == 0
    assert len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real cat on Rocky Linux 9 with /etc/hosts")
def test_live_hosts_view() -> None:
    """Live: cat /etc/hosts returns the hosts file content."""
    result = _execute("hosts-view", {})
    assert result.exit_code == 0
    assert "localhost" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root on Rocky Linux 9")
def test_live_set_hostname_requires_root() -> None:
    """Live: hostnamectl set-hostname on Rocky requires elevated privileges."""
    result = _execute("set-hostname", {"name": "test-hostname.example.com"})
    assert result.exit_code is not None
