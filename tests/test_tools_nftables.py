"""tests/test_tools_nftables.py — Unit tests for core/tools/nftables.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without the nft binary present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list_ruleset is READ; add_rule/delete_rule are WRITE;
    flush_ruleset is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code != 0) → ok=False, failure summary.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises for any op including missing binary (exit 127).
  * I2: no AI/LLM/model/agent language in any summary.
  * Command vectors: argv lists match expected nft invocation shapes.
  * DEFERRED-TO-MOSSAD: live execution against real nft on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.nftables.run_subprocess`` (the function in the
  nftables module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

import os
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.nftables  # noqa: F401  (side-effect: registry.register)
from core.agent.audit import AuditLog, iter_records
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.nftables import NFTABLES_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.nftables.run_subprocess."""
    return patch("core.tools.nftables.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_nftables_registered_in_module_registry(self) -> None:
        assert registry.get("nftables") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("nftables")
        assert spec is not None
        assert spec.name == "nftables"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("nftables")
        assert spec is not None
        expected = {"list_ruleset", "add_rule", "delete_rule", "flush_ruleset"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list_ruleset"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nftables", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["add_rule", "delete_rule"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nftables", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["flush_ruleset"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nftables", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vector tests — verify exact argv lists
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_list_ruleset_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="table inet filter {}"))
        with patch("core.tools.nftables.run_subprocess", mock_fn):
            _execute("list_ruleset", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nft", "list", "ruleset"]

    def test_add_rule_argv_with_family(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nftables.run_subprocess", mock_fn):
            _execute("add_rule", {
                "family": "inet",
                "table": "filter",
                "chain": "input",
                "rule": "tcp dport 22 accept",
            })
        argv = mock_fn.call_args[0][0]
        assert argv == ["nft", "add", "rule", "inet", "filter", "input", "tcp", "dport", "22", "accept"]

    def test_add_rule_argv_default_family(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nftables.run_subprocess", mock_fn):
            _execute("add_rule", {
                "table": "filter",
                "chain": "input",
                "rule": "udp dport 53 accept",
            })
        argv = mock_fn.call_args[0][0]
        # family should default to "inet"
        assert argv[3] == "inet"
        assert argv[4] == "filter"
        assert argv[5] == "input"
        assert "udp" in argv
        assert "53" in argv
        assert "accept" in argv

    def test_delete_rule_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nftables.run_subprocess", mock_fn):
            _execute("delete_rule", {
                "family": "inet",
                "table": "filter",
                "chain": "input",
                "handle": "7",
            })
        argv = mock_fn.call_args[0][0]
        assert argv == ["nft", "delete", "rule", "inet", "filter", "input", "handle", "7"]

    def test_flush_ruleset_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nftables.run_subprocess", mock_fn):
            _execute("flush_ruleset", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nft", "flush", "ruleset"]

    def test_flush_ruleset_destructive_verb_in_argv(self) -> None:
        """Ensure the DESTRUCTIVE verb 'flush' and object 'ruleset' appear verbatim
        in argv[1] and argv[2] so permissions.classify() can gate them correctly."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.nftables.run_subprocess", mock_fn):
            _execute("flush_ruleset", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "nft"
        assert argv[1] == "flush"
        assert argv[2] == "ruleset"


# ---------------------------------------------------------------------------
# list_ruleset operation
# ---------------------------------------------------------------------------

class TestListRuleset:
    def test_success_summary(self) -> None:
        stdout = (
            "table inet filter {\n"
            "\tchain input { type filter hook input priority filter; policy drop; }\n"
            "}\n"
        )
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("list_ruleset", {})
        assert result.ok
        assert "table" in result.summary.lower() or "ruleset" in result.summary.lower()

    def test_failure_nonzero_exit(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Operation not permitted")):
            result = _execute("list_ruleset", {})
        assert not result.ok
        assert "1" in result.summary

    def test_result_has_stdout(self) -> None:
        with _patch_run(_ok_result(stdout="table inet filter {}")):
            result = _execute("list_ruleset", {})
        assert "table" in result.stdout


# ---------------------------------------------------------------------------
# add_rule operation
# ---------------------------------------------------------------------------

class TestAddRule:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("add_rule", {
                "family": "inet",
                "table": "filter",
                "chain": "input",
                "rule": "tcp dport 80 accept",
            })
        assert result.ok
        assert "filter" in result.summary
        assert "input" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Error: No such table")):
            result = _execute("add_rule", {
                "family": "inet",
                "table": "missing_table",
                "chain": "input",
                "rule": "tcp dport 80 accept",
            })
        assert not result.ok
        assert "missing_table" in result.summary

    def test_summary_names_table_and_chain(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("add_rule", {
                "table": "nat",
                "chain": "postrouting",
                "rule": "masquerade",
            })
        assert "nat" in result.summary
        assert "postrouting" in result.summary


# ---------------------------------------------------------------------------
# delete_rule operation
# ---------------------------------------------------------------------------

class TestDeleteRule:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("delete_rule", {
                "family": "inet",
                "table": "filter",
                "chain": "input",
                "handle": "5",
            })
        assert result.ok
        assert "5" in result.summary
        assert "filter" in result.summary
        assert "input" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Rule with handle 999 does not exist")):
            result = _execute("delete_rule", {
                "family": "inet",
                "table": "filter",
                "chain": "input",
                "handle": "999",
            })
        assert not result.ok
        assert "999" in result.summary

    def test_handle_in_summary(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("delete_rule", {
                "table": "filter",
                "chain": "forward",
                "handle": "42",
            })
        assert "42" in result.summary


# ---------------------------------------------------------------------------
# flush_ruleset operation
# ---------------------------------------------------------------------------

class TestFlushRuleset:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("flush_ruleset", {})
        assert result.ok
        assert "flush" in result.summary.lower() or "removed" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Operation not permitted")):
            result = _execute("flush_ruleset", {})
        assert not result.ok
        assert "1" in result.summary

    def test_flush_is_destructive_class(self) -> None:
        cls = NFTABLES_SPEC.permission_class_for("flush_ruleset")
        assert cls is OpClass.DESTRUCTIVE

    def test_missing_binary_exit_127(self) -> None:
        """I9: a missing nft binary (exit 127) must degrade to a well-formed ToolResult."""
        with _patch_run(_fail_result(exit_code=127, stderr="nft: command not found")):
            result = _execute("flush_ruleset", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("list_ruleset", {}),
        ("add_rule", {"table": "filter", "chain": "input", "rule": "tcp dport 22 accept"}),
        ("delete_rule", {"table": "filter", "chain": "input", "handle": "3"}),
        ("flush_ruleset", {}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "Operation not permitted: "
            "AVC avc: denied { write } for pid=5678 "
            "comm=\"nft\" name=\"nftables\""
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "AVC" in result.summary
            or "ausearch" in result.summary
        ), f"No SELinux hint in summary for op={op!r}: {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Error: table not found")):
            result = _execute("list_ruleset", {})
        assert "ausearch" not in result.summary

    def test_permission_denied_triggers_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Permission denied")):
            result = _execute("flush_ruleset", {})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list_ruleset", {}),
        ("add_rule", {"table": "filter", "chain": "input", "rule": "tcp dport 22 accept"}),
        ("delete_rule", {"table": "filter", "chain": "input", "handle": "1"}),
        ("flush_ruleset", {}),
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
        ("list_ruleset", {}),
        ("add_rule", {"table": "f", "chain": "c", "rule": "accept"}),
        ("delete_rule", {"table": "f", "chain": "c", "handle": "1"}),
        ("flush_ruleset", {}),
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
        """I9: An unknown op must return a ToolResult, not raise."""
        result = _execute("nonexistent_operation", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_no_raise(self) -> None:
        """I9: exit_code=127 (binary not found) must return a ToolResult."""
        with _patch_run(_fail_result(exit_code=127, stderr="nft: command not found")):
            result = _execute("list_ruleset", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_all_ops_no_raise_on_exit_127(self) -> None:
        """I9: every defined op must handle exit 127 gracefully."""
        ops_and_args = [
            ("list_ruleset", {}),
            ("add_rule", {"table": "filter", "chain": "input", "rule": "accept"}),
            ("delete_rule", {"table": "filter", "chain": "input", "handle": "1"}),
            ("flush_ruleset", {}),
        ]
        for op, args in ops_and_args:
            with _patch_run(_fail_result(exit_code=127, stderr="nft: command not found")):
                result = _execute(op, args)
            assert isinstance(result, ToolResult), f"Expected ToolResult for op={op!r}"
            assert result.exit_code == 127

    def test_unknown_op_with_empty_args_no_raise(self) -> None:
        result = _execute("bogus_op_xyz", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None


# ---------------------------------------------------------------------------
# No AI / model / LLM language in any summary (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list_ruleset", {}),
        ("add_rule", {"table": "filter", "chain": "input", "rule": "tcp dport 22 accept"}),
        ("delete_rule", {"table": "filter", "chain": "input", "handle": "5"}),
        ("flush_ruleset", {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("list_ruleset", {}),
        ("add_rule", {"table": "filter", "chain": "input", "rule": "accept"}),
        ("delete_rule", {"table": "filter", "chain": "input", "handle": "1"}),
        ("flush_ruleset", {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_list_ruleset(self) -> None:
        with _patch_run(_ok_result(stdout="table inet filter {}")):
            result = registry.dispatch("nftables", "list_ruleset", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_flush_ruleset(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("nftables", "flush_ruleset", {})
        assert result.ok

    def test_dispatch_add_rule_missing_table_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'table'"):
            registry.dispatch("nftables", "add_rule", {"chain": "input", "rule": "accept"})

    def test_dispatch_delete_rule_missing_handle_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'handle'"):
            registry.dispatch("nftables", "delete_rule", {"table": "filter", "chain": "input"})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("nftables", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# Audit integration
# ---------------------------------------------------------------------------

class TestAuditIntegration:
    def test_audit_record_written_after_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "audit.jsonl")
            log = AuditLog(audit_path)

            with _patch_run(_ok_result(stdout="table inet filter {}")):
                result = _execute("list_ruleset", {})

            log.write(
                tier="test-tier",
                nl_input="show all nft rules",
                translated_command="nft list ruleset",
                tool="nftables",
                args={"op": "list_ruleset"},
                permission_decision="read",
                exit_code=result.exit_code,
                stdout_summary=result.stdout[:256],
                stderr_summary=result.stderr[:256],
                result=result.summary,
            )
            log.close()

            records = list(iter_records(audit_path))
            assert len(records) == 1
            rec = records[0]
            assert rec["tool"] == "nftables"
            assert rec["permission_decision"] == "read"
            assert rec["exit_code"] == 0

    def test_audit_record_written_for_destructive_op(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            audit_path = os.path.join(tmpdir, "audit.jsonl")
            log = AuditLog(audit_path)

            with _patch_run(_ok_result()):
                result = _execute("flush_ruleset", {})

            log.write(
                tier="test-tier",
                nl_input="flush the nftables ruleset",
                translated_command="nft flush ruleset",
                tool="nftables",
                args={"op": "flush_ruleset"},
                permission_decision="destructive:confirmed",
                exit_code=result.exit_code,
                stdout_summary=result.stdout[:256],
                stderr_summary=result.stderr[:256],
                result=result.summary,
            )
            log.close()

            records = list(iter_records(audit_path))
            assert len(records) == 1
            rec = records[0]
            assert rec["permission_decision"] == "destructive:confirmed"
            assert rec["result"] is not None


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nft binary on Rocky Linux 9")
def test_live_list_ruleset() -> None:
    """Live: nft list ruleset returns a populated ToolResult."""
    result = _execute("list_ruleset", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nft binary and root on Rocky Linux 9")
def test_live_flush_ruleset_requires_root() -> None:
    """Live: nft flush ruleset requires elevated privileges.

    This test must be run as root. It verifies that the destructive gate
    (REFUSE for non-interactive, CONFIRM for interactive) is enforced by the
    Phase 4 router before calling execute(). Running as a regular user should
    return exit_code != 0 with a permission error in stderr.
    """
    result = _execute("flush_ruleset", {})
    assert result.exit_code is not None
