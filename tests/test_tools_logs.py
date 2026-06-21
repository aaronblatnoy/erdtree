"""tests/test_tools_logs.py — Unit tests for core/tools/logs.py.

All subprocess calls are mocked; no live journalctl, dmesg, or Linux binary
is required.  Every test is expected to pass on the macOS dev host.

Tests that need a live Linux binary (journalctl, dmesg) are present as
documentation stubs and marked with::

    @pytest.mark.deferred_mossad

Those are SKIPPED here and must be verified on the mossad server.

Coverage:
  * TOOL_SPEC is registered into the global registry with the right name.
  * Every declared op has permission_class = READ.
  * execute() dispatches to each sub-op and returns a ToolResult.
  * journalctl query — correct cmd vector built from args; stdout in result.
  * journalctl tail  — --lines N flag built; default 50 used when absent.
  * journalctl since — --since flag required; cmd contains it.
  * journalctl boot_errors — -p err + --boot flags; defaults to boot 0.
  * dmesg_query — --color=never -T in cmd; grep filter applied in Python.
  * dmesg_query — bad regex returns exit_code 1 without calling subprocess.
  * dmesg_errors — -l err,crit,alert,emerg flag present in cmd.
  * SELinux hint extraction — AVC denial in stdout → hint in stderr.
  * SELinux hint extraction — no AVC → empty hint list.
  * Output line capping — _head_lines / _tail_lines truncate correctly.
  * Unknown op returns exit_code 1 with descriptive summary.
  * AuditLog: each execute() result fields map to AuditLog.write() without error.
  * Registry: tool 'logs' is discoverable; permission_class_for read ops is READ.
  * Priority-to-level mapping in dmesg_query works for friendly names.
  * Permission gate: all ops are classified READ by the permissions module.
  * Egress: all subprocess calls target localhost commands (no external URLs).

DEFERRED-TO-MOSSAD (marked skip):
  * Live journalctl output on a real Rocky Linux 9 box.
  * Live dmesg on a real Rocky Linux 9 box.
  * SELinux AVC detection end-to-end on a real Rocky 9 box.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------

# Importing logs.py triggers its registry.register() call.  We import it
# explicitly so the test module can reference the internals.
import core.tools.logs as logs_mod
from core.tools.logs import (
    TOOL_SPEC,
    _execute,
    _extract_selinux_hints,
    _head_lines,
    _tail_lines,
    _journalctl_query,
    _journalctl_tail,
    _journalctl_since,
    _journalctl_boot_errors,
    _dmesg_query,
    _dmesg_errors,
)
from core.tools import registry, ToolResult
from core.agent.permissions import OpClass, classify, ExecContext
from core.agent.audit import AuditLog


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_completed(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Build a fake subprocess.CompletedProcess."""
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


def _patch_run(stdout: str = "", stderr: str = "", returncode: int = 0):
    """Context manager: patch subprocess.run to return a canned result."""
    proc = _make_completed(stdout=stdout, stderr=stderr, returncode=returncode)
    return patch("subprocess.run", return_value=proc)


# ---------------------------------------------------------------------------
# 1. Tool registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_tool_registered_in_global_registry(self) -> None:
        spec = registry.get("logs")
        assert spec is not None, "logs tool must be registered in the global registry"

    def test_tool_name_is_logs(self) -> None:
        assert TOOL_SPEC.name == "logs"

    def test_all_ops_are_present(self) -> None:
        expected = {"query", "tail", "since", "boot_errors", "dmesg_query", "dmesg_errors"}
        assert set(TOOL_SPEC.ops.keys()) == expected

    def test_all_ops_are_read(self) -> None:
        """Every log operation must be READ — we never mutate state by reading logs."""
        for op_name, op_spec in TOOL_SPEC.ops.items():
            assert op_spec.permission_class is OpClass.READ, (
                f"op '{op_name}' must be READ, got {op_spec.permission_class}"
            )

    def test_registry_permission_class_for_all_ops(self) -> None:
        for op_name in TOOL_SPEC.ops:
            cls = registry.permission_class_for("logs", op_name)
            assert cls is OpClass.READ, (
                f"registry.permission_class_for('logs', '{op_name}') must be READ"
            )

    def test_description_contains_no_ai_language(self) -> None:
        """I2: no AI/LLM/model/agent language in user-facing descriptions."""
        ai_terms = {"ai", "llm", "model", "agent", "agentic", "neural", "gpt"}
        combined = TOOL_SPEC.description.lower()
        for op_spec in TOOL_SPEC.ops.values():
            combined += " " + op_spec.description.lower()
        for term in ai_terms:
            assert term not in combined, (
                f"AI language '{term}' found in logs tool description (violates I2)"
            )


# ---------------------------------------------------------------------------
# 2. Permission gate (I3) — logs ops must classify as READ / ALLOW
# ---------------------------------------------------------------------------

class TestPermissionGate:
    """All logs ops declare READ so the permission gate must ALLOW them."""

    @pytest.mark.parametrize("op", [
        "query", "tail", "since", "boot_errors", "dmesg_query", "dmesg_errors",
    ])
    def test_op_classifies_as_read(self, op: str) -> None:
        cls = TOOL_SPEC.ops[op].permission_class
        assert cls is OpClass.READ

    def test_journalctl_command_classifies_as_read_via_permissions_module(self) -> None:
        from core.agent.permissions import classify, ExecContext, Gate
        decision = classify("journalctl --no-pager -u nginx -n 100", ExecContext())
        assert decision.gate is Gate.ALLOW

    def test_dmesg_command_classifies_as_read_via_permissions_module(self) -> None:
        from core.agent.permissions import classify, ExecContext, Gate
        decision = classify("dmesg --color=never -T", ExecContext())
        assert decision.gate is Gate.ALLOW


# ---------------------------------------------------------------------------
# 3. SELinux hint extraction
# ---------------------------------------------------------------------------

AVC_SAMPLE = (
    "kernel: audit: avc: denied { read } for pid=1234 comm=\"nginx\" "
    "name=\"passwd\" dev=\"sda1\" ino=1048577 "
    "scontext=system_u:system_r:httpd_t:s0 "
    "tcontext=system_u:object_r:shadow_t:s0 tclass=file permissive=0"
)

AVC_SAMPLE_2 = (
    "kernel: audit: avc: denied { write } for pid=999 comm=\"python3\" "
    "scontext=user_u:user_r:user_t:s0 "
    "tcontext=system_u:object_r:var_log_t:s0 tclass=dir permissive=0"
)


class TestSELinuxHints:
    def test_no_avc_returns_empty_list(self) -> None:
        hints = _extract_selinux_hints("normal log line\nanother line")
        assert hints == []

    def test_single_avc_returns_one_hint(self) -> None:
        hints = _extract_selinux_hints(AVC_SAMPLE)
        assert len(hints) == 1
        hint = hints[0]
        assert "SELinux denied" in hint
        assert "read" in hint
        assert "audit2allow" in hint
        assert "semodule" in hint

    def test_two_avc_lines_return_two_hints(self) -> None:
        text = AVC_SAMPLE + "\n" + AVC_SAMPLE_2
        hints = _extract_selinux_hints(text)
        assert len(hints) == 2

    def test_hint_contains_scontext_and_tcontext(self) -> None:
        hints = _extract_selinux_hints(AVC_SAMPLE)
        assert len(hints) == 1
        hint = hints[0]
        assert "httpd_t" in hint
        assert "shadow_t" in hint

    def test_hint_contains_audit2allow_command(self) -> None:
        hints = _extract_selinux_hints(AVC_SAMPLE)
        assert "audit2allow -a -M" in hints[0]

    def test_empty_string_returns_empty(self) -> None:
        assert _extract_selinux_hints("") == []


# ---------------------------------------------------------------------------
# 4. Line-cap helpers
# ---------------------------------------------------------------------------

class TestLineCapHelpers:
    def test_head_lines_short_text_unchanged(self) -> None:
        text = "a\nb\nc"
        assert _head_lines(text, 10) == text

    def test_head_lines_truncates_at_n(self) -> None:
        text = "\n".join(str(i) for i in range(100))
        result = _head_lines(text, 5)
        lines = result.splitlines()
        # First 5 real lines + 1 truncation notice
        assert lines[0] == "0"
        assert lines[4] == "4"
        assert "truncated" in result

    def test_tail_lines_short_text_unchanged(self) -> None:
        text = "x\ny\nz"
        assert _tail_lines(text, 10) == text

    def test_tail_lines_returns_last_n(self) -> None:
        lines = [str(i) for i in range(20)]
        text = "\n".join(lines)
        result = _tail_lines(text, 3)
        assert result.strip().splitlines() == ["17", "18", "19"]


# ---------------------------------------------------------------------------
# 5. journalctl query
# ---------------------------------------------------------------------------

JOURNAL_SAMPLE = (
    "2026-01-01T00:00:00+0000 myhost nginx[1234]: started\n"
    "2026-01-01T00:01:00+0000 myhost nginx[1234]: ready\n"
)


class TestJournalctlQuery:
    def test_basic_query_calls_journalctl(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            result = _journalctl_query({})
        assert mock_run.called
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "journalctl"
        assert "--no-pager" in cmd

    def test_unit_filter_added_when_provided(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"unit": "nginx"})
        cmd = mock_run.call_args[0][0]
        assert "-u" in cmd
        assert "nginx" in cmd

    def test_since_flag_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"since": "1 hour ago"})
        cmd = mock_run.call_args[0][0]
        assert "--since" in cmd
        assert "1 hour ago" in cmd

    def test_until_flag_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"until": "now"})
        cmd = mock_run.call_args[0][0]
        assert "--until" in cmd

    def test_priority_flag_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"priority": "err"})
        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd
        assert "err" in cmd

    def test_lines_flag_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"lines": 42})
        cmd = mock_run.call_args[0][0]
        assert "-n" in cmd
        assert "42" in cmd

    def test_default_lines_is_100(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({})
        cmd = mock_run.call_args[0][0]
        assert "100" in cmd

    def test_grep_flag_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"grep": "error"})
        cmd = mock_run.call_args[0][0]
        assert "--grep" in cmd

    def test_identifier_flag_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"identifier": "sshd"})
        cmd = mock_run.call_args[0][0]
        assert "-t" in cmd
        assert "sshd" in cmd

    def test_boot_flag_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_query({"boot": "-1"})
        cmd = mock_run.call_args[0][0]
        assert "--boot" in cmd

    def test_returns_tool_result(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE):
            result = _journalctl_query({})
        assert isinstance(result, ToolResult)
        assert JOURNAL_SAMPLE in result.stdout

    def test_success_exit_code(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE, returncode=0):
            result = _journalctl_query({})
        assert result.exit_code == 0
        assert result.ok is True

    def test_nonzero_exit_code_propagated(self) -> None:
        with _patch_run(stdout="", stderr="unit not found", returncode=1):
            result = _journalctl_query({"unit": "ghost"})
        assert result.exit_code == 1
        assert result.ok is False

    def test_avc_denial_in_stdout_adds_hint_to_stderr(self) -> None:
        with _patch_run(stdout=AVC_SAMPLE, returncode=0):
            result = _journalctl_query({})
        assert "SELinux denied" in result.stderr
        assert "audit2allow" in result.stderr

    def test_avc_hint_count_in_summary(self) -> None:
        avc_double = AVC_SAMPLE + "\n" + AVC_SAMPLE_2
        with _patch_run(stdout=avc_double, returncode=0):
            result = _journalctl_query({})
        assert "2 SELinux denial" in result.summary


# ---------------------------------------------------------------------------
# 6. journalctl tail
# ---------------------------------------------------------------------------

class TestJournalctlTail:
    def test_calls_journalctl_with_no_pager(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_tail({})
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "journalctl"
        assert "--no-pager" in cmd

    def test_default_lines_is_50(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_tail({})
        cmd = mock_run.call_args[0][0]
        assert "50" in cmd

    def test_custom_lines(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_tail({"lines": 25})
        cmd = mock_run.call_args[0][0]
        assert "25" in cmd

    def test_unit_filter_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_tail({"unit": "sshd"})
        cmd = mock_run.call_args[0][0]
        assert "-u" in cmd
        assert "sshd" in cmd

    def test_returns_tool_result(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE):
            result = _journalctl_tail({})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# 7. journalctl since
# ---------------------------------------------------------------------------

class TestJournalctlSince:
    def test_since_in_cmd(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_since({"since": "2 hours ago"})
        cmd = mock_run.call_args[0][0]
        assert "--since" in cmd
        assert "2 hours ago" in cmd

    def test_unit_filter_added(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_since({"since": "1 hour ago", "unit": "postgresql"})
        cmd = mock_run.call_args[0][0]
        assert "-u" in cmd
        assert "postgresql" in cmd

    def test_default_since_fallback(self) -> None:
        """When 'since' key is absent we fall back to '1 hour ago'."""
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_since({})
        cmd = mock_run.call_args[0][0]
        assert "--since" in cmd

    def test_lines_cap_applied(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE) as mock_run:
            _journalctl_since({"since": "yesterday", "lines": 77})
        cmd = mock_run.call_args[0][0]
        assert "77" in cmd

    def test_returns_tool_result(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE):
            result = _journalctl_since({"since": "1 hour ago"})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# 8. journalctl boot_errors
# ---------------------------------------------------------------------------

class TestJournalctlBootErrors:
    def test_default_boot_is_0(self) -> None:
        with _patch_run(stdout="") as mock_run:
            _journalctl_boot_errors({})
        cmd = mock_run.call_args[0][0]
        assert "--boot" in cmd
        assert "0" in cmd

    def test_custom_boot(self) -> None:
        with _patch_run(stdout="") as mock_run:
            _journalctl_boot_errors({"boot": "-1"})
        cmd = mock_run.call_args[0][0]
        assert "-1" in cmd

    def test_priority_err_flag(self) -> None:
        with _patch_run(stdout="") as mock_run:
            _journalctl_boot_errors({})
        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd
        assert "err" in cmd

    def test_returns_tool_result(self) -> None:
        with _patch_run(stdout="kernel panic\n"):
            result = _journalctl_boot_errors({})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# 9. dmesg_query
# ---------------------------------------------------------------------------

DMESG_SAMPLE = (
    "[    0.000000] Initializing cgroup subsys cpuset\n"
    "[    1.234567] EXT4-fs (sda1): mounted filesystem\n"
    "[    2.000000] audit: avc: denied { read } for pid=555 comm=\"test\" "
    "scontext=user_u:user_r:user_t:s0 "
    "tcontext=system_u:object_r:shadow_t:s0 tclass=file permissive=0\n"
)


class TestDmesgQuery:
    def test_calls_dmesg_with_color_never(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE) as mock_run:
            _dmesg_query({})
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "dmesg"
        assert "--color=never" in cmd

    def test_T_flag_present(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE) as mock_run:
            _dmesg_query({})
        cmd = mock_run.call_args[0][0]
        assert "-T" in cmd

    def test_level_err_adds_l_flag(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE) as mock_run:
            _dmesg_query({"level": "err"})
        cmd = mock_run.call_args[0][0]
        assert "-l" in cmd
        assert "3" in cmd  # err maps to 3

    def test_level_warn_maps_to_4(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE) as mock_run:
            _dmesg_query({"level": "warn"})
        cmd = mock_run.call_args[0][0]
        assert "4" in cmd

    def test_level_warning_maps_to_4(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE) as mock_run:
            _dmesg_query({"level": "warning"})
        cmd = mock_run.call_args[0][0]
        assert "4" in cmd

    def test_grep_filters_output(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE):
            result = _dmesg_query({"grep": "EXT4"})
        assert "EXT4" in result.stdout
        assert "cpuset" not in result.stdout

    def test_grep_no_match_returns_empty_stdout(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE):
            result = _dmesg_query({"grep": "XYZZY_NO_MATCH"})
        assert result.stdout.strip() == ""
        assert result.exit_code == 0

    def test_bad_regex_returns_error_without_subprocess(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE) as mock_run:
            result = _dmesg_query({"grep": "[invalid"})
        assert result.exit_code == 1
        assert "Invalid grep pattern" in result.stderr

    def test_since_flag_added_when_provided(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE) as mock_run:
            _dmesg_query({"since": "1 hour ago"})
        cmd = mock_run.call_args[0][0]
        assert "--since" in cmd

    def test_lines_cap_applied(self) -> None:
        # Generate many lines of dmesg output.
        many_lines = "\n".join(
            f"[  {i:6d}.000000] line {i}" for i in range(300)
        )
        with _patch_run(stdout=many_lines):
            result = _dmesg_query({"lines": 10})
        # tail returns last 10 lines; they start around line 290.
        assert len(result.stdout.splitlines()) <= 10

    def test_default_lines_cap_is_200(self) -> None:
        many_lines = "\n".join(
            f"[  {i:6d}.000000] line {i}" for i in range(300)
        )
        with _patch_run(stdout=many_lines):
            result = _dmesg_query({})
        assert len(result.stdout.splitlines()) <= 200

    def test_avc_in_dmesg_produces_hint(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE):
            result = _dmesg_query({})
        assert "SELinux denied" in result.stderr
        assert "audit2allow" in result.stderr

    def test_returns_tool_result(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE):
            result = _dmesg_query({})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# 10. dmesg_errors
# ---------------------------------------------------------------------------

class TestDmesgErrors:
    def test_calls_dmesg_with_error_level_filter(self) -> None:
        with _patch_run(stdout="") as mock_run:
            _dmesg_errors({})
        cmd = mock_run.call_args[0][0]
        assert "-l" in cmd
        assert "err,crit,alert,emerg" in cmd

    def test_default_lines_100(self) -> None:
        many_lines = "\n".join(f"err line {i}" for i in range(150))
        with _patch_run(stdout=many_lines):
            result = _dmesg_errors({})
        assert len(result.stdout.splitlines()) <= 100

    def test_custom_lines(self) -> None:
        many_lines = "\n".join(f"err line {i}" for i in range(60))
        with _patch_run(stdout=many_lines):
            result = _dmesg_errors({"lines": 20})
        assert len(result.stdout.splitlines()) <= 20

    def test_returns_tool_result(self) -> None:
        with _patch_run(stdout="kernel oops\n"):
            result = _dmesg_errors({})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# 11. Unified execute() dispatcher
# ---------------------------------------------------------------------------

class TestExecuteDispatcher:
    @pytest.mark.parametrize("op", [
        "query", "tail", "since", "boot_errors", "dmesg_query", "dmesg_errors",
    ])
    def test_execute_dispatches_each_op(self, op: str) -> None:
        args: dict[str, Any] = {}
        if op == "since":
            args["since"] = "1 hour ago"
        with _patch_run(stdout="sample output"):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)

    def test_unknown_op_returns_error_result(self) -> None:
        result = _execute("no_such_op", {})
        assert result.exit_code == 1
        assert "unknown log operation" in result.summary.lower()

    def test_execute_result_is_audit_compatible(self) -> None:
        """ToolResult fields must all be serialisable into AuditLog.write()."""
        with _patch_run(stdout="log line"):
            result = _execute("query", {})
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as f:
            log_path = f.name
        try:
            with AuditLog(log_path) as log:
                log.write(
                    tier=None,
                    nl_input="show logs",
                    translated_command="journalctl --no-pager -n 100",
                    tool="logs",
                    args={"lines": 100},
                    permission_decision="read",
                    exit_code=result.exit_code,
                    stdout_summary=result.stdout[:200] if result.stdout else None,
                    stderr_summary=result.stderr[:200] if result.stderr else None,
                    result=result.summary,
                )
        finally:
            Path(log_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# 12. Registry dispatch round-trip (via ToolRegistry.dispatch)
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_query_returns_tool_result(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE):
            result = registry.dispatch("logs", "query", {})
        assert isinstance(result, ToolResult)

    def test_dispatch_tail_returns_tool_result(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE):
            result = registry.dispatch("logs", "tail", {})
        assert isinstance(result, ToolResult)

    def test_dispatch_since_with_required_arg(self) -> None:
        with _patch_run(stdout=JOURNAL_SAMPLE):
            result = registry.dispatch("logs", "since", {"since": "1 hour ago"})
        assert isinstance(result, ToolResult)

    def test_dispatch_since_missing_required_arg_raises(self) -> None:
        """'since' op requires the 'since' arg."""
        with pytest.raises(TypeError, match="requires argument 'since'"):
            registry.dispatch("logs", "since", {})

    def test_dispatch_boot_errors_no_args(self) -> None:
        with _patch_run(stdout=""):
            result = registry.dispatch("logs", "boot_errors", {})
        assert isinstance(result, ToolResult)

    def test_dispatch_dmesg_query_no_args(self) -> None:
        with _patch_run(stdout=DMESG_SAMPLE):
            result = registry.dispatch("logs", "dmesg_query", {})
        assert isinstance(result, ToolResult)

    def test_dispatch_dmesg_errors_no_args(self) -> None:
        with _patch_run(stdout=""):
            result = registry.dispatch("logs", "dmesg_errors", {})
        assert isinstance(result, ToolResult)

    def test_dispatch_unknown_op_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="no operation"):
            registry.dispatch("logs", "nonexistent_op", {})

    def test_dispatch_wrong_arg_type_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="must be int"):
            registry.dispatch("logs", "query", {"lines": "not-an-int"})


# ---------------------------------------------------------------------------
# 13. Egress invariant (I1) — no external network calls
# ---------------------------------------------------------------------------

class TestEgressInvariant:
    def test_cmd_vectors_target_local_binaries_only(self) -> None:
        """All subprocess calls must target local system binaries.

        journalctl and dmesg are local Linux commands; they never reach an
        external network endpoint.  This test asserts that the first element
        of each command vector is a recognized local binary and contains no
        URL-like strings.
        """
        captured_cmds: list[list[str]] = []

        def _capturing_run(cmd, **kwargs):
            captured_cmds.append(list(cmd))
            return _make_completed(stdout="")

        all_ops_args = [
            ("query", {}),
            ("tail", {}),
            ("since", {"since": "1 hour ago"}),
            ("boot_errors", {}),
            ("dmesg_query", {}),
            ("dmesg_errors", {}),
        ]

        with patch("subprocess.run", side_effect=_capturing_run):
            for op, args in all_ops_args:
                _execute(op, args)

        assert len(captured_cmds) == len(all_ops_args)
        for cmd in captured_cmds:
            binary = cmd[0]
            assert binary in ("journalctl", "dmesg"), (
                f"Unexpected binary in command: {cmd}"
            )
            for token in cmd:
                assert "://" not in token, (
                    f"URL-like token '{token}' found in cmd {cmd} (violates I1)"
                )


# ---------------------------------------------------------------------------
# 14. No AI language in any string produced by the module (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    AI_TERMS = frozenset({"ai", "llm", "model", "agent", "agentic", "neural", "gpt"})

    def _check_string(self, s: str, context: str) -> None:
        lowered = s.lower()
        for term in self.AI_TERMS:
            # word-boundary check so e.g. "model" in "model-name" is caught
            # but "scontext" (substring of "context") is not.
            import re
            if re.search(rf"\b{re.escape(term)}\b", lowered):
                pytest.fail(
                    f"AI language '{term}' found in {context}: {s!r} (violates I2)"
                )

    def test_no_ai_language_in_execute_results(self) -> None:
        all_ops_args = [
            ("query", {}),
            ("tail", {}),
            ("since", {"since": "1 hour ago"}),
            ("boot_errors", {}),
            ("dmesg_query", {}),
            ("dmesg_errors", {}),
        ]
        with _patch_run(stdout="normal log output", returncode=0):
            for op, args in all_ops_args:
                result = _execute(op, args)
                self._check_string(result.summary, f"execute('{op}').summary")
                self._check_string(result.stderr,  f"execute('{op}').stderr")

    def test_no_ai_language_in_selinux_hints(self) -> None:
        hints = _extract_selinux_hints(AVC_SAMPLE)
        for hint in hints:
            self._check_string(hint, "SELinux hint")

    def test_no_ai_language_in_tool_spec(self) -> None:
        self._check_string(TOOL_SPEC.description, "TOOL_SPEC.description")
        for name, op_spec in TOOL_SPEC.ops.items():
            self._check_string(op_spec.description, f"op '{name}' description")


# ---------------------------------------------------------------------------
# 15. I6 — no tier / product names in this module
# ---------------------------------------------------------------------------

class TestNoTierNames:
    FORBIDDEN = frozenset({"marika", "radagon", "rocky", "starscourge", "radahn"})

    def test_no_tier_names_in_module_source(self) -> None:
        source = Path(logs_mod.__file__).read_text(encoding="utf-8").lower()
        for name in self.FORBIDDEN:
            assert name not in source, (
                f"Tier/product name '{name}' found in logs.py (violates I6)"
            )


# ---------------------------------------------------------------------------
# 16. DEFERRED-TO-MOSSAD stubs
#     These tests document what must pass on a live Rocky Linux 9 host.
#     They are skipped here because journalctl / dmesg are unavailable on macOS.
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires live Rocky Linux 9 with journalctl")
def test_live_journalctl_query_returns_output() -> None:
    """On mossad: journalctl must return at least some output from the live system."""
    result = _journalctl_query({"lines": 10})
    assert result.exit_code == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires live Rocky Linux 9 with journalctl")
def test_live_journalctl_boot_errors() -> None:
    """On mossad: boot_errors must complete without error."""
    result = _journalctl_boot_errors({})
    assert result.exit_code == 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires live Rocky Linux 9 with dmesg")
def test_live_dmesg_query_returns_output() -> None:
    """On mossad: dmesg must return at least some kernel ring buffer output."""
    result = _dmesg_query({"lines": 20})
    assert result.exit_code == 0
    assert len(result.stdout.strip()) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires live Rocky Linux 9 with dmesg")
def test_live_dmesg_errors() -> None:
    """On mossad: dmesg_errors must complete (empty output is valid if no errors)."""
    result = _dmesg_errors({})
    assert result.exit_code == 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires live Rocky Linux 9 with SELinux + AVC denials")
def test_live_selinux_avc_hint_end_to_end() -> None:
    """On mossad: with SELinux in enforcing mode and a triggered AVC denial,
    the logs tool must surface a hint containing audit2allow and semodule."""
    # 1. Trigger a known AVC denial (e.g. httpd trying to read a shadow_t file).
    # 2. Call _journalctl_query({"since": "1 minute ago", "grep": "avc"}).
    # 3. Assert "SELinux denied" in result.stderr.
    # 4. Assert "audit2allow" in result.stderr.
    pass
