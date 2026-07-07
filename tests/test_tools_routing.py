"""tests/test_tools_routing.py — Unit tests for core/tools/routing.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without the ip command present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: route_show and policy_rule_show are READ;
    route_add, route_del, and policy_rule_add are WRITE;
    route_flush and policy_rule_flush are DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (nonzero) → ok=False, failure summary mentioning the object.
  * Command vectors: assert the exact argv list passed to run_subprocess.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2: no AI/LLM/model/agent language in any summary.
  * execute() NEVER raises (I9): unknown op and exit-127 (missing binary) both
    return a well-formed ToolResult.

Mocking strategy
----------------
  We patch ``core.tools.routing.run_subprocess`` (the function in the routing
  module's namespace) — NOT the canonical core.tools.run_subprocess — to
  return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import core.tools.routing  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.routing import ROUTING_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Context-manager patch on core.tools.routing.run_subprocess."""
    return patch("core.tools.routing.run_subprocess", return_value=return_value)


def _mock_run(return_value: ToolResult) -> MagicMock:
    """Return a MagicMock configured to return return_value when called."""
    m = MagicMock(return_value=return_value)
    return m


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_routing_registered(self) -> None:
        assert registry.get("routing") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("routing")
        assert spec is not None
        assert spec.name == "routing"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("routing")
        assert spec is not None
        expected = {
            "route_show", "route_add", "route_del", "route_flush",
            "policy_rule_show", "policy_rule_add", "policy_rule_flush",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["route_show", "policy_rule_show"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("routing", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["route_add", "route_del", "policy_rule_add"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("routing", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["route_flush", "policy_rule_flush"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("routing", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vector tests (exact argv assertions)
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_route_show_no_table(self) -> None:
        m = _mock_run(_ok(stdout="default via 10.0.0.1\n"))
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_show", {})
        argv = m.call_args[0][0]
        assert argv == ["ip", "route", "show"]

    def test_route_show_with_table(self) -> None:
        m = _mock_run(_ok(stdout="10.0.0.0/8 dev eth0\n"))
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_show", {"table": "main"})
        argv = m.call_args[0][0]
        assert argv == ["ip", "route", "show", "table", "main"]

    def test_route_add_basic(self) -> None:
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_add", {"dest": "192.168.50.0/24", "gateway": "10.0.0.1"})
        argv = m.call_args[0][0]
        assert argv == ["ip", "route", "add", "192.168.50.0/24", "via", "10.0.0.1"]

    def test_route_add_with_dev_and_metric(self) -> None:
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_add", {
                "dest": "10.1.0.0/24",
                "gateway": "10.0.0.1",
                "dev": "eth0",
                "metric": 100,
            })
        argv = m.call_args[0][0]
        assert argv == [
            "ip", "route", "add", "10.1.0.0/24",
            "via", "10.0.0.1",
            "dev", "eth0",
            "metric", "100",
        ]

    def test_route_del_basic(self) -> None:
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_del", {"dest": "192.168.50.0/24"})
        argv = m.call_args[0][0]
        assert argv == ["ip", "route", "del", "192.168.50.0/24"]

    def test_route_del_default(self) -> None:
        """Verify the literal 'default' token appears in argv so the classifier can gate it."""
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_del", {"dest": "default"})
        argv = m.call_args[0][0]
        assert argv == ["ip", "route", "del", "default"]

    def test_route_del_with_gateway_and_dev(self) -> None:
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_del", {"dest": "10.0.0.0/8", "gateway": "10.0.0.1", "dev": "eth0"})
        argv = m.call_args[0][0]
        assert argv == ["ip", "route", "del", "10.0.0.0/8", "via", "10.0.0.1", "dev", "eth0"]

    def test_route_flush_argv(self) -> None:
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("route_flush", {"table": "100"})
        argv = m.call_args[0][0]
        assert argv == ["ip", "route", "flush", "table", "100"]

    def test_policy_rule_show_argv(self) -> None:
        m = _mock_run(_ok(stdout="0:\tfrom all lookup local\n"))
        with patch("core.tools.routing.run_subprocess", m):
            _execute("policy_rule_show", {})
        argv = m.call_args[0][0]
        assert argv == ["ip", "rule", "show"]

    def test_policy_rule_add_full_argv(self) -> None:
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("policy_rule_add", {
                "src": "10.1.0.0/24",
                "dest": "0.0.0.0/0",
                "priority": 200,
                "table": "100",
            })
        argv = m.call_args[0][0]
        assert argv == [
            "ip", "rule", "add",
            "from", "10.1.0.0/24",
            "to", "0.0.0.0/0",
            "priority", "200",
            "table", "100",
        ]

    def test_policy_rule_flush_argv(self) -> None:
        """Verify 'ip rule flush' appears verbatim in argv for the classifier."""
        m = _mock_run(_ok())
        with patch("core.tools.routing.run_subprocess", m):
            _execute("policy_rule_flush", {})
        argv = m.call_args[0][0]
        assert argv == ["ip", "rule", "flush"]


# ---------------------------------------------------------------------------
# Exit-code mapping (success / failure)
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_route_show_success(self) -> None:
        with _patch(_ok(stdout="default via 10.0.0.1 dev eth0\n")):
            result = _execute("route_show", {})
        assert result.ok
        assert "retrieved" in result.summary.lower() or "route" in result.summary.lower()

    def test_route_show_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Error: FIB table does not exist.")):
            result = _execute("route_show", {"table": "bogus99"})
        assert not result.ok
        assert "1" in result.summary or "failed" in result.summary.lower()

    def test_route_add_success(self) -> None:
        with _patch(_ok()):
            result = _execute("route_add", {"dest": "10.50.0.0/16", "gateway": "10.0.0.1"})
        assert result.ok
        assert "10.50.0.0/16" in result.summary
        assert "added" in result.summary.lower()

    def test_route_add_failure(self) -> None:
        with _patch(_fail(exit_code=2, stderr="RTNETLINK answers: File exists")):
            result = _execute("route_add", {"dest": "10.50.0.0/16"})
        assert not result.ok
        assert "10.50.0.0/16" in result.summary

    def test_route_del_success(self) -> None:
        with _patch(_ok()):
            result = _execute("route_del", {"dest": "192.168.50.0/24"})
        assert result.ok
        assert "192.168.50.0/24" in result.summary
        assert "deleted" in result.summary.lower()

    def test_route_del_failure(self) -> None:
        with _patch(_fail(exit_code=2, stderr="RTNETLINK answers: No such process")):
            result = _execute("route_del", {"dest": "10.99.0.0/24"})
        assert not result.ok
        assert "10.99.0.0/24" in result.summary

    def test_route_flush_success(self) -> None:
        with _patch(_ok()):
            result = _execute("route_flush", {"table": "100"})
        assert result.ok
        assert "100" in result.summary
        assert "flushed" in result.summary.lower()

    def test_route_flush_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Error: FIB table does not exist.")):
            result = _execute("route_flush", {"table": "bogus"})
        assert not result.ok
        assert "bogus" in result.summary

    def test_policy_rule_show_success(self) -> None:
        with _patch(_ok(stdout="0:\tfrom all lookup local\n32766:\tfrom all lookup main\n")):
            result = _execute("policy_rule_show", {})
        assert result.ok
        assert "rule" in result.summary.lower() or "retrieved" in result.summary.lower()

    def test_policy_rule_show_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Cannot open network namespace")):
            result = _execute("policy_rule_show", {})
        assert not result.ok
        assert "failed" in result.summary.lower() or "1" in result.summary

    def test_policy_rule_add_success(self) -> None:
        with _patch(_ok()):
            result = _execute("policy_rule_add", {"src": "10.1.0.0/24", "table": "100"})
        assert result.ok
        assert "added" in result.summary.lower() or "rule" in result.summary.lower()

    def test_policy_rule_add_failure(self) -> None:
        with _patch(_fail(exit_code=2, stderr="RTNETLINK answers: File exists")):
            result = _execute("policy_rule_add", {"src": "10.1.0.0/24"})
        assert not result.ok
        assert "failed" in result.summary.lower()

    def test_policy_rule_flush_success(self) -> None:
        with _patch(_ok()):
            result = _execute("policy_rule_flush", {})
        assert result.ok
        assert "flushed" in result.summary.lower()

    def test_policy_rule_flush_failure(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Operation not permitted")):
            result = _execute("policy_rule_flush", {})
        assert not result.ok
        assert "failed" in result.summary.lower()


# ---------------------------------------------------------------------------
# I2: no AI language in summaries
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("route_show",         {}),
        ("route_add",          {"dest": "192.168.1.0/24", "gateway": "10.0.0.1"}),
        ("route_del",          {"dest": "192.168.1.0/24"}),
        ("route_flush",        {"table": "100"}),
        ("policy_rule_show",   {}),
        ("policy_rule_add",    {"src": "10.1.0.0/24", "table": "100"}),
        ("policy_rule_flush",  {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="some output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("route_show",         {}),
        ("route_add",          {"dest": "192.168.1.0/24"}),
        ("route_del",          {"dest": "192.168.1.0/24"}),
        ("route_flush",        {"table": "main"}),
        ("policy_rule_show",   {}),
        ("policy_rule_add",    {}),
        ("policy_rule_flush",  {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="some error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC = (
        "AVC avc: denied { net_admin } for pid=1234 "
        "comm=\"ip\" scontext=system_u:system_r:unconfined_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("route_show",         {}),
        ("route_add",          {"dest": "192.168.1.0/24", "gateway": "10.0.0.1"}),
        ("route_del",          {"dest": "192.168.1.0/24"}),
        ("route_flush",        {"table": "100"}),
        ("policy_rule_show",   {}),
        ("policy_rule_add",    {"src": "10.0.0.0/8", "table": "50"}),
        ("policy_rule_flush",  {}),
    ])
    def test_avc_denial_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint missing for op='{op}': {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("route_show",        {}),
        ("route_add",         {"dest": "192.168.1.0/24"}),
        ("policy_rule_flush", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="RTNETLINK answers: No such process")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("route_show",         {}),
        ("route_add",          {"dest": "192.168.1.0/24", "gateway": "10.0.0.1"}),
        ("route_del",          {"dest": "192.168.1.0/24"}),
        ("route_flush",        {"table": "100"}),
        ("policy_rule_show",   {}),
        ("policy_rule_add",    {"src": "10.0.0.0/8"}),
        ("policy_rule_flush",  {}),
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
        ("route_show",         {}),
        ("route_add",          {"dest": "10.0.0.0/8"}),
        ("route_del",          {"dest": "10.0.0.0/8"}),
        ("route_flush",        {"table": "100"}),
        ("policy_rule_show",   {}),
        ("policy_rule_add",    {}),
        ("policy_rule_flush",  {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# execute() NEVER raises (I9)
# ---------------------------------------------------------------------------

class TestNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("totally_unknown_operation", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        missing = ToolResult(exit_code=127, stdout="", stderr="", summary="command not found: ip")
        with patch("core.tools.routing.run_subprocess", return_value=missing):
            result = _execute("route_show", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_no_exception_on_exit_127_for_all_ops(self) -> None:
        missing = ToolResult(exit_code=127, stdout="", stderr="", summary="command not found: ip")
        ops_args: list[tuple[str, dict]] = [
            ("route_show",         {}),
            ("route_add",          {"dest": "10.0.0.0/8"}),
            ("route_del",          {"dest": "10.0.0.0/8"}),
            ("route_flush",        {"table": "100"}),
            ("policy_rule_show",   {}),
            ("policy_rule_add",    {}),
            ("policy_rule_flush",  {}),
        ]
        with patch("core.tools.routing.run_subprocess", return_value=missing):
            for op, args in ops_args:
                result = _execute(op, args)  # must not raise
                assert isinstance(result, ToolResult), f"op={op} did not return ToolResult"
                assert result.exit_code is not None


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_route_show(self) -> None:
        with _patch(_ok(stdout="default via 10.0.0.1\n")):
            result = registry.dispatch("routing", "route_show", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_route_add(self) -> None:
        with _patch(_ok()):
            result = registry.dispatch("routing", "route_add", {
                "dest": "192.168.1.0/24",
                "gateway": "10.0.0.1",
            })
        assert result.ok

    def test_dispatch_route_del_missing_dest_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'dest'"):
            registry.dispatch("routing", "route_del", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("routing", "nonexistent_op", {})

    def test_dispatch_policy_rule_flush_no_args(self) -> None:
        with _patch(_ok()):
            result = registry.dispatch("routing", "policy_rule_flush", {})
        assert result.ok


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real ip command on Rocky Linux 9")
def test_live_route_show() -> None:
    """Live: ip route show returns a populated ToolResult."""
    result = _execute("route_show", {})
    assert result.exit_code in (0, 1, 127)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real ip command on Rocky Linux 9")
def test_live_policy_rule_show() -> None:
    """Live: ip rule show returns policy routing rules."""
    result = _execute("policy_rule_show", {})
    assert result.exit_code == 0
    assert "lookup local" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires elevated privileges on Rocky Linux 9")
def test_live_route_add_requires_root() -> None:
    """Live: ip route add requires elevated privileges; without root exits non-zero."""
    result = _execute("route_add", {"dest": "198.51.100.0/24", "gateway": "10.0.0.1"})
    assert result.exit_code is not None
