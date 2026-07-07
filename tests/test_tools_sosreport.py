"""tests/test_tools_sosreport.py — Unit tests for core/tools/sosreport.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without 'sos' present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: info is READ; generate is WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * Clean stderr produces no SELinux hint.
  * execute() never raises (I9) — unknown op and missing binary (exit 127)
    both return a well-formed ToolResult with no exception.
  * I2: no AI/LLM/model/agent language in any summary.
  * ToolResult structure: four required keys, non-None exit_code, len(summary)>0.
  * DEFERRED-TO-MOSSAD: live execution tests at the tail.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Side-effect import triggers self-registration in the module-level registry.
import core.tools.sosreport  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.sosreport import SOSREPORT_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.sosreport.run_subprocess."""
    return patch("core.tools.sosreport.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_sosreport_registered_in_module_registry(self) -> None:
        assert registry.get("sosreport") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("sosreport")
        assert spec is not None
        assert spec.name == "sosreport"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("sosreport")
        assert spec is not None
        expected = {"generate", "info"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    def test_info_is_read(self) -> None:
        cls = registry.permission_class_for("sosreport", "info")
        assert cls is OpClass.READ, f"Expected READ for 'info', got {cls}"

    def test_generate_is_write(self) -> None:
        cls = registry.permission_class_for("sosreport", "generate")
        assert cls is OpClass.WRITE, f"Expected WRITE for 'generate', got {cls}"

    @pytest.mark.parametrize("op,expected", [
        ("info", OpClass.READ),
        ("generate", OpClass.WRITE),
    ])
    def test_permission_classes_parametrized(self, op: str, expected: OpClass) -> None:
        assert registry.permission_class_for("sosreport", op) is expected


# ---------------------------------------------------------------------------
# generate operation
# ---------------------------------------------------------------------------

class TestGenerate:
    _ARCHIVE_STDOUT = (
        "Your sosreport has been generated and saved in:\n"
        "\tsosreport-rocky-host-2026-07-04-abc123.tar.xz\n"
        "\n"
        "Size\t...\t38.7MiB\n"
    )

    def test_success_summary_mentions_archive(self) -> None:
        with _patch_run(_ok_result(stdout=self._ARCHIVE_STDOUT)):
            result = _execute("generate", {})
        assert result.ok
        assert "sosreport" in result.summary.lower() or "archive" in result.summary.lower() or "generated" in result.summary.lower()

    def test_success_with_label_in_summary(self) -> None:
        with _patch_run(_ok_result(stdout="")):
            result = _execute("generate", {"label": "case-99999"})
        assert result.ok
        assert "case-99999" in result.summary or "collected" in result.summary.lower()

    def test_failure_nonzero_exit(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Please run this as root.")):
            result = _execute("generate", {})
        assert not result.ok
        assert result.exit_code == 1
        assert "exit" in result.summary.lower() or "failed" in result.summary.lower()

    def test_command_vector_includes_sos_report_batch(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.sosreport.run_subprocess", mock_fn):
            _execute("generate", {})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "sos"
        assert argv[1] == "report"
        assert "--batch" in argv

    def test_command_vector_includes_label(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.sosreport.run_subprocess", mock_fn):
            _execute("generate", {"label": "my-label"})
        argv = mock_fn.call_args[0][0]
        assert "--label" in argv
        idx = argv.index("--label")
        assert argv[idx + 1] == "my-label"

    def test_command_vector_includes_output_dir(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.sosreport.run_subprocess", mock_fn):
            _execute("generate", {"output_dir": "/tmp/sos"})
        argv = mock_fn.call_args[0][0]
        assert "--output-dir" in argv
        idx = argv.index("--output-dir")
        assert argv[idx + 1] == "/tmp/sos"

    def test_command_vector_no_label_no_flag(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.sosreport.run_subprocess", mock_fn):
            _execute("generate", {})
        argv = mock_fn.call_args[0][0]
        assert "--label" not in argv
        assert "--output-dir" not in argv

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="sos: command not found")):
            result = _execute("generate", {})
        assert not result.ok
        assert result.exit_code == 127
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_result_structure(self) -> None:
        with _patch_run(_ok_result(stdout="archive output")):
            result = _execute("generate", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_as_dict_four_keys(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("generate", {})
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# info operation
# ---------------------------------------------------------------------------

class TestInfo:
    _PLUGIN_LIST_STDOUT = (
        "The following plugins are currently enabled:\n"
        " kernel      | Kernel parameters\n"
        " networking  | Network data\n"
    )

    def test_success_no_plugin(self) -> None:
        with _patch_run(_ok_result(stdout=self._PLUGIN_LIST_STDOUT)):
            result = _execute("info", {})
        assert result.ok
        assert "plugin" in result.summary.lower() or "retrieved" in result.summary.lower()

    def test_success_with_plugin_arg(self) -> None:
        with _patch_run(_ok_result(stdout="Plugin: kernel\n  Status: enabled\n")):
            result = _execute("info", {"plugin": "kernel"})
        assert result.ok
        assert "kernel" in result.summary

    def test_failure_no_plugin(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="sos info failed")):
            result = _execute("info", {})
        assert not result.ok
        assert "exit" in result.summary.lower() or "failed" in result.summary.lower()

    def test_failure_unknown_plugin(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="No plugin named 'bogus' found.")):
            result = _execute("info", {"plugin": "bogus"})
        assert not result.ok
        assert "bogus" in result.summary

    def test_command_vector_no_plugin(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.sosreport.run_subprocess", mock_fn):
            _execute("info", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["sos", "info"]

    def test_command_vector_with_plugin(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.sosreport.run_subprocess", mock_fn):
            _execute("info", {"plugin": "selinux"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["sos", "info", "selinux"]

    def test_result_structure(self) -> None:
        with _patch_run(_ok_result(stdout=self._PLUGIN_LIST_STDOUT)):
            result = _execute("info", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_as_dict_four_keys(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("info", {})
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="sos: command not found")):
            result = _execute("info", {})
        assert not result.ok
        assert result.exit_code == 127
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("generate", {}),
        ("info", {}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=5678 "
            "comm=\"sos\" name=\"sos\" scontext=unconfined_u:unconfined_r:unconfined_t"
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op={op!r}, got: {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("generate", {}),
        ("info", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Permission error (non-AVC).")):
            result = _execute(op, args)
        # Plain "Permission error" does match _SELINUX_HINT_RE ("Permission denied")
        # only if the exact phrase "Permission denied" is present; "Permission error"
        # should not match. Verify no false positive from completely clean stderr.
        with _patch_run(_fail_result(exit_code=1, stderr="Operation not permitted by OS policy.")):
            result2 = _execute(op, args)
        assert "ausearch" not in result2.summary

    def test_selinux_hint_exact_pattern(self) -> None:
        """Verify the AVC pattern fires on 'type=AVC' in stderr."""
        avc_stderr = "kernel: type=AVC msg=audit(12345.678:999): avc: denied"
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute("generate", {})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op_xyz", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert "nonexistent_op_xyz" in result.summary

    def test_missing_binary_exit_127_no_raise(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="sos: command not found")):
            try:
                result = _execute("generate", {})
            except Exception as exc:
                pytest.fail(f"execute() raised unexpectedly: {exc!r}")
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_missing_binary_info_no_raise(self) -> None:
        with _patch_run(_fail_result(exit_code=127, stderr="sos: command not found")):
            try:
                result = _execute("info", {})
            except Exception as exc:
                pytest.fail(f"execute() raised unexpectedly: {exc!r}")
        assert isinstance(result, ToolResult)

    def test_timeout_exit_124_no_raise(self) -> None:
        with _patch_run(_fail_result(exit_code=124, stderr="Timeout")):
            try:
                result = _execute("generate", {})
            except Exception as exc:
                pytest.fail(f"execute() raised unexpectedly: {exc!r}")
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124


# ---------------------------------------------------------------------------
# I2 — No AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("generate", {}),
        ("generate", {"label": "case-0001"}),
        ("generate", {"output_dir": "/tmp"}),
        ("info", {}),
        ("info", {"plugin": "kernel"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("generate", {}),
        ("info", {}),
        ("info", {"plugin": "bogus"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )

    def test_no_ai_language_in_unknown_op_summary(self) -> None:
        result = _execute("bad_op", {})
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in unknown-op summary: {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# ToolResult structure invariants (all ops)
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("generate", {}),
        ("generate", {"label": "lbl", "output_dir": "/tmp"}),
        ("info", {}),
        ("info", {"plugin": "kernel"}),
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
        ("generate", {}),
        ("info", {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# ToolSpec direct attribute checks
# ---------------------------------------------------------------------------

class TestToolSpecAttributes:
    def test_generate_permission_class_write(self) -> None:
        assert SOSREPORT_SPEC.permission_class_for("generate") is OpClass.WRITE

    def test_info_permission_class_read(self) -> None:
        assert SOSREPORT_SPEC.permission_class_for("info") is OpClass.READ

    def test_generate_args_all_optional(self) -> None:
        op_spec = SOSREPORT_SPEC.ops["generate"]
        required_args = [a for a in op_spec.args if a.required]
        assert len(required_args) == 0, "generate args should all be optional"

    def test_info_args_all_optional(self) -> None:
        op_spec = SOSREPORT_SPEC.ops["info"]
        required_args = [a for a in op_spec.args if a.required]
        assert len(required_args) == 0, "info args should all be optional"


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sos on Rocky Linux 9")
def test_live_sos_info() -> None:
    """Live: sos info returns a plugin listing."""
    result = _execute("info", {})
    assert result.exit_code == 0
    assert len(result.stdout) > 0
    assert "kernel" in result.stdout.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sos + root on Rocky Linux 9")
def test_live_sos_report_generate() -> None:
    """Live: sos report --batch generates an archive.

    This test requires root and several minutes of run time.
    Run manually on mossad; verify the archive path appears in stdout.
    """
    result = _execute("generate", {"label": "test-live"})
    assert result.exit_code == 0
    assert ".tar.xz" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sos on Rocky Linux 9")
def test_live_sos_info_plugin() -> None:
    """Live: sos info kernel returns plugin details."""
    result = _execute("info", {"plugin": "kernel"})
    assert result.exit_code in (0, 1)  # 1 if plugin not found by name on this sos version
    assert isinstance(result.stdout, str)
