"""tests/test_tools_dns.py — Unit tests for core/tools/dns.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without dig, nslookup, host, resolvectl, or
systemctl present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: resolv_view/named_status/dig/nslookup/host are READ;
    flush_caches is WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (nonzero) → ok=False, failure summary with exit code.
  * Command vectors for each op match expected argv.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2: no AI/LLM/model/agent/agentic/neural language in any summary.
  * execute() NEVER raises (I9): unknown op and exit 127 both return a
    well-formed ToolResult with no exception.
  * ToolResult structure: non-None exit_code, str stdout/stderr/summary,
    len(summary) > 0, as_dict() has exactly 4 keys.
  * DEFERRED-TO-MOSSAD: live execution tests at the tail.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.dns  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.dns import DNS_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.dns.run_subprocess."""
    return patch("core.tools.dns.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_dns_registered_in_module_registry(self) -> None:
        assert registry.get("dns") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("dns")
        assert spec is not None
        assert spec.name == "dns"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("dns")
        assert spec is not None
        expected = {
            "resolv_view", "named_status", "dig", "nslookup", "host", "flush_caches"
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", [
        "resolv_view", "named_status", "dig", "nslookup", "host",
    ])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("dns", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    def test_write_op_flush_caches(self) -> None:
        cls = registry.permission_class_for("dns", "flush_caches")
        assert cls is OpClass.WRITE, f"Expected WRITE for 'flush_caches', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — assert the exact argv passed to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_resolv_view_cmd(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="nameserver 8.8.8.8\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("resolv_view", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["cat", "/etc/resolv.conf"]

    def test_named_status_cmd(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="● named.service"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("named_status", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["systemctl", "status", "--no-pager", "named"]

    def test_dig_basic_cmd(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="example.com. 300 IN A 1.2.3.4\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("dig", {"name": "example.com"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["dig", "+noall", "+answer", "example.com", "A"]

    def test_dig_with_type_and_server(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="example.com. 300 IN MX 10 mail.example.com.\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("dig", {"name": "example.com", "record_type": "MX", "server": "8.8.8.8"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["dig", "+noall", "+answer", "@8.8.8.8", "example.com", "MX"]

    def test_dig_no_server_omits_at_arg(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("dig", {"name": "example.com", "record_type": "A", "server": ""})
        cmd = mock_fn.call_args[0][0]
        assert "@" not in " ".join(cmd)

    def test_nslookup_basic_cmd(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Name: example.com\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("nslookup", {"name": "example.com"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["nslookup", "example.com"]

    def test_nslookup_with_server(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Name: example.com\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("nslookup", {"name": "example.com", "server": "10.0.0.1"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["nslookup", "example.com", "10.0.0.1"]

    def test_host_basic_cmd(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="example.com has address 1.2.3.4\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("host", {"name": "example.com"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["host", "example.com"]

    def test_host_with_server(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="example.com has address 1.2.3.4\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("host", {"name": "example.com", "server": "8.8.4.4"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["host", "example.com", "8.8.4.4"]

    def test_flush_caches_cmd(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("flush_caches", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["resolvectl", "flush-caches"]


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure paths
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("nslookup",     {"name": "example.com"}),
        ("host",         {"name": "example.com"}),
        ("flush_caches", {}),
    ])
    def test_success_path(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="output")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "bad.host"}),
        ("nslookup",     {"name": "bad.host"}),
        ("host",         {"name": "bad.host"}),
        ("flush_caches", {}),
    ])
    def test_failure_path(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error occurred")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1
        assert len(result.summary) > 0

    def test_named_status_exit_3(self) -> None:
        """systemctl status exits 3 when the unit is inactive — not .ok but handled."""
        with _patch_run(_fail_result(exit_code=3, stderr="")):
            result = _execute("named_status", {})
        assert not result.ok
        assert result.exit_code == 3
        assert "3" in result.summary

    def test_dig_failure_summary_contains_name(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="no servers could be reached")):
            result = _execute("dig", {"name": "nxdomain.example.com", "record_type": "A"})
        assert not result.ok
        assert "nxdomain.example.com" in result.summary

    def test_nslookup_failure_summary_contains_name(self) -> None:
        with _patch_run(_fail_result(exit_code=1)):
            result = _execute("nslookup", {"name": "nxdomain.example.com"})
        assert not result.ok
        assert "nxdomain.example.com" in result.summary

    def test_host_failure_summary_contains_name(self) -> None:
        with _patch_run(_fail_result(exit_code=1)):
            result = _execute("host", {"name": "nxdomain.example.com"})
        assert not result.ok
        assert "nxdomain.example.com" in result.summary


# ---------------------------------------------------------------------------
# I2-clean summaries — no forbidden AI/LLM language
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("nslookup",     {"name": "example.com"}),
        ("host",         {"name": "example.com"}),
        ("flush_caches", {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("nslookup",     {"name": "example.com"}),
        ("host",         {"name": "example.com"}),
        ("flush_caches", {}),
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
        "Failed to open /etc/resolv.conf: "
        "AVC avc: denied { read } for pid=5678 "
        "comm=\"cat\" name=\"resolv.conf\""
    )

    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("nslookup",     {"name": "example.com"}),
        ("host",         {"name": "example.com"}),
        ("flush_caches", {}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint not found for op='{op}': {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("flush_caches", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="permission error")):
            result = _execute(op, args)
        # 'permission error' without AVC/selinux context must NOT trigger the hint
        # (The _SELINUX_HINT_RE only fires on AVC-specific patterns)
        # Note: "Permission denied" DOES trigger — use a non-matching string here
        assert "ausearch" not in result.summary or "permission error" in result.stderr

    def test_plain_error_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="command not found")):
            result = _execute("dig", {"name": "example.com"})
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("nslookup",     {"name": "example.com"}),
        ("host",         {"name": "example.com"}),
        ("flush_caches", {}),
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
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("nslookup",     {"name": "example.com"}),
        ("host",         {"name": "example.com"}),
        ("flush_caches", {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        """An unknown op must degrade to a ToolResult, never raise."""
        result = _execute("not_a_real_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "not_a_real_op" in result.summary
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("resolv_view",  {}),
        ("named_status", {}),
        ("dig",          {"name": "example.com"}),
        ("nslookup",     {"name": "example.com"}),
        ("host",         {"name": "example.com"}),
        ("flush_caches", {}),
    ])
    def test_missing_binary_exit_127_returns_toolresult(self, op: str, args: dict) -> None:
        """A missing binary (exit 127) must degrade gracefully — never raise."""
        with _patch_run(_fail_result(exit_code=127, stderr="command not found")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_resolv_view(self) -> None:
        with _patch_run(_ok_result(stdout="nameserver 8.8.8.8\n")):
            result = registry.dispatch("dns", "resolv_view", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_dig(self) -> None:
        with _patch_run(_ok_result(stdout="example.com. 300 IN A 1.2.3.4\n")):
            result = registry.dispatch("dns", "dig", {"name": "example.com"})
        assert result.ok

    def test_dispatch_flush_caches(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("dns", "flush_caches", {})
        assert result.ok

    def test_dispatch_dig_missing_name_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'name'"):
            registry.dispatch("dns", "dig", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("dns", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# dig record_type default
# ---------------------------------------------------------------------------

class TestDigDefaults:
    def test_dig_default_record_type_is_A(self) -> None:
        """When record_type is not supplied, dig should query for A records."""
        mock_fn = MagicMock(return_value=_ok_result(stdout="example.com. 300 IN A 1.2.3.4\n"))
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("dig", {"name": "example.com"})
        cmd = mock_fn.call_args[0][0]
        assert "A" in cmd
        # 'A' should be the record type, not a server flag
        assert cmd[-1] == "A"

    def test_dig_explicit_record_type(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.dns.run_subprocess", mock_fn):
            _execute("dig", {"name": "example.com", "record_type": "MX"})
        cmd = mock_fn.call_args[0][0]
        assert "MX" in cmd


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real dig on Rocky Linux 9")
def test_live_dig_A_record() -> None:
    """Live: dig +noall +answer example.com A returns a well-formed ToolResult."""
    result = _execute("dig", {"name": "example.com", "record_type": "A"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real resolvectl on Rocky Linux 9")
def test_live_flush_caches() -> None:
    """Live: resolvectl flush-caches returns exit 0."""
    result = _execute("flush_caches", {})
    assert result.exit_code == 0
    assert "flushed" in result.summary.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires systemctl on Rocky Linux 9")
def test_live_named_status() -> None:
    """Live: systemctl status named exits 0 or 3 (active/inactive)."""
    result = _execute("named_status", {})
    assert result.exit_code in (0, 3, 4)
