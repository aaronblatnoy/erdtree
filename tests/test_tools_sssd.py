"""tests/test_tools_sssd.py — Unit tests for core/tools/sssd.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without sssd, realm, sss_cache, or id present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/id_lookup/realm_list are READ;
    cache_flush/realm_join are WRITE; realm_leave is DESTRUCTIVE.
  * Command vectors: each op builds the correct argv list.
  * Exit-code mapping: exit 0 -> ok=True; non-zero -> ok=False.
  * ToolResult structure: all four keys present, non-None, summary non-empty.
  * I2-clean summaries: no AI/LLM/model/agent/neural/language model language.
  * SELinux hint fires on AVC stderr; does NOT fire on clean stderr.
  * execute() never raises for unknown op or exit 127 (missing binary).
  * DEFERRED-TO-MOSSAD: live execution spot checks.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.sssd  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.sssd import SSSD_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch run_subprocess in the sssd module's own namespace."""
    return patch("core.tools.sssd.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_sssd_registered(self) -> None:
        assert registry.get("sssd") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("sssd")
        assert spec is not None
        assert spec.name == "sssd"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("sssd")
        assert spec is not None
        expected = {"status", "id_lookup", "cache_flush", "realm_list", "realm_join", "realm_leave"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "id_lookup", "realm_list"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("sssd", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["cache_flush", "realm_join"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("sssd", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_realm_leave_is_destructive(self) -> None:
        cls = registry.permission_class_for("sssd", "realm_leave")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_status_calls_systemctl(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.sssd.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "systemctl"
        assert "status" in argv
        assert "sssd" in argv

    def test_id_lookup_calls_id(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="uid=1001(jsmith)"))
        with patch("core.tools.sssd.run_subprocess", mock_fn):
            _execute("id_lookup", {"user": "jsmith"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "id"
        assert "jsmith" in argv

    def test_cache_flush_calls_sss_cache(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.sssd.run_subprocess", mock_fn):
            _execute("cache_flush", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "sss_cache"
        assert "-E" in argv

    def test_realm_list_calls_realm(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="corp.example.com\n"))
        with patch("core.tools.sssd.run_subprocess", mock_fn):
            _execute("realm_list", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "realm"
        assert "list" in argv

    def test_realm_join_calls_realm_join(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.sssd.run_subprocess", mock_fn):
            _execute("realm_join", {"domain": "corp.example.com"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "realm"
        assert "join" in argv
        assert "corp.example.com" in argv

    def test_realm_leave_calls_realm_leave(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.sssd.run_subprocess", mock_fn):
            _execute("realm_leave", {"domain": "corp.example.com"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "realm"
        assert "leave" in argv
        assert "corp.example.com" in argv


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("id_lookup", {"user": "alice"}),
        ("cache_flush", {}),
        ("realm_list", {}),
        ("realm_join", {"domain": "corp.example.com"}),
        ("realm_leave", {"domain": "corp.example.com"}),
    ])
    def test_exit_0_is_ok(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("id_lookup", {"user": "alice"}),
        ("cache_flush", {}),
        ("realm_list", {}),
        ("realm_join", {"domain": "corp.example.com"}),
        ("realm_leave", {"domain": "corp.example.com"}),
    ])
    def test_nonzero_exit_is_not_ok(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1

    def test_realm_leave_success_summary_mentions_domain(self) -> None:
        with _patch(_ok()):
            result = _execute("realm_leave", {"domain": "corp.example.com"})
        assert "corp.example.com" in result.summary

    def test_realm_leave_failure_summary_mentions_domain(self) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute("realm_leave", {"domain": "test.lab"})
        assert "test.lab" in result.summary

    def test_realm_join_success_summary(self) -> None:
        with _patch(_ok()):
            result = _execute("realm_join", {"domain": "ad.company.org"})
        assert result.ok
        assert "ad.company.org" in result.summary

    def test_id_lookup_success_summary(self) -> None:
        with _patch(_ok(stdout="uid=1001(bob)")):
            result = _execute("id_lookup", {"user": "bob"})
        assert result.ok
        assert "bob" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("id_lookup", {"user": "alice"}),
        ("cache_flush", {}),
        ("realm_list", {}),
        ("realm_join", {"domain": "corp.example.com"}),
        ("realm_leave", {"domain": "corp.example.com"}),
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
        ("status", {}),
        ("id_lookup", {"user": "alice"}),
        ("cache_flush", {}),
        ("realm_list", {}),
        ("realm_join", {"domain": "corp.example.com"}),
        ("realm_leave", {"domain": "corp.example.com"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "realm: error: AVC avc: denied { read } for pid=2345 "
        "comm=\"realm\" name=\"sssd.conf\" dev=\"sda1\" ino=123456"
    )

    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("id_lookup", {"user": "alice"}),
        ("cache_flush", {}),
        ("realm_list", {}),
        ("realm_join", {"domain": "corp.example.com"}),
        ("realm_leave", {"domain": "corp.example.com"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op={op!r}, got: {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="No such user.")):
            result = _execute("id_lookup", {"user": "nobody"})
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary


# ---------------------------------------------------------------------------
# I2-clean summaries — no AI/LLM/model/agent language
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("id_lookup", {"user": "alice"}),
        ("cache_flush", {}),
        ("realm_list", {}),
        ("realm_join", {"domain": "corp.example.com"}),
        ("realm_leave", {"domain": "corp.example.com"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op={op!r}: {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("status", {}),
        ("id_lookup", {"user": "alice"}),
        ("cache_flush", {}),
        ("realm_list", {}),
        ("realm_join", {"domain": "corp.example.com"}),
        ("realm_leave", {"domain": "corp.example.com"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op={op!r}: {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# execute() never raises — I9
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("completely_unknown_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127(self) -> None:
        """Simulate a missing binary (run_subprocess returns exit 127)."""
        missing = ToolResult(exit_code=127, stdout="", stderr="command not found: realm", summary="")
        with patch("core.tools.sssd.run_subprocess", return_value=missing):
            result = _execute("realm_join", {"domain": "corp.example.com"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_missing_binary_cache_flush(self) -> None:
        missing = ToolResult(exit_code=127, stdout="", stderr="command not found: sss_cache", summary="")
        with patch("core.tools.sssd.run_subprocess", return_value=missing):
            result = _execute("cache_flush", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_status(self) -> None:
        missing = ToolResult(exit_code=127, stdout="", stderr="command not found", summary="")
        with patch("core.tools.sssd.run_subprocess", return_value=missing):
            result = _execute("status", {})
        assert isinstance(result, ToolResult)
        assert not result.ok


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_status(self) -> None:
        with _patch(_ok(stdout="● sssd.service")):
            result = registry.dispatch("sssd", "status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_id_lookup(self) -> None:
        with _patch(_ok(stdout="uid=1001(alice)")):
            result = registry.dispatch("sssd", "id_lookup", {"user": "alice"})
        assert result.ok

    def test_dispatch_realm_leave(self) -> None:
        with _patch(_ok()):
            result = registry.dispatch("sssd", "realm_leave", {"domain": "corp.example.com"})
        assert result.ok
        assert "corp.example.com" in result.summary

    def test_dispatch_id_lookup_missing_user_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'user'"):
            registry.dispatch("sssd", "id_lookup", {})

    def test_dispatch_realm_join_missing_domain_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'domain'"):
            registry.dispatch("sssd", "realm_join", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("sssd", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# SSSD_SPEC direct attribute checks
# ---------------------------------------------------------------------------

class TestSpecAttributes:
    def test_realm_leave_in_spec_ops(self) -> None:
        assert "realm_leave" in SSSD_SPEC.ops

    def test_realm_leave_spec_is_destructive(self) -> None:
        assert SSSD_SPEC.permission_class_for("realm_leave") is OpClass.DESTRUCTIVE

    def test_status_spec_is_read(self) -> None:
        assert SSSD_SPEC.permission_class_for("status") is OpClass.READ

    def test_cache_flush_spec_is_write(self) -> None:
        assert SSSD_SPEC.permission_class_for("cache_flush") is OpClass.WRITE

    def test_realm_join_spec_is_write(self) -> None:
        assert SSSD_SPEC.permission_class_for("realm_join") is OpClass.WRITE


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sssd on Rocky Linux 9")
def test_live_status_sssd() -> None:
    """Live: systemctl status sssd returns a populated ToolResult."""
    result = _execute("status", {})
    assert result.exit_code in (0, 3, 4)
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real id binary and sssd on Rocky Linux 9")
def test_live_id_lookup_root() -> None:
    """Live: id root always resolves."""
    result = _execute("id_lookup", {"user": "root"})
    assert result.exit_code == 0
    assert "root" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sss_cache and running sssd on Rocky Linux 9")
def test_live_cache_flush() -> None:
    """Live: sss_cache -E requires root and running sssd."""
    result = _execute("cache_flush", {})
    assert result.exit_code in (0, 1)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real realm binary on Rocky Linux 9")
def test_live_realm_list() -> None:
    """Live: realm list returns enrolled realms or empty output."""
    result = _execute("realm_list", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)
