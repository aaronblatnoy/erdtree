"""tests/test_tools_rpm.py — Unit tests for core/tools/rpm.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without rpm or rpm2cpio present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: query_info/query_files/query_file/verify/checksig/
    rpm2cpio are READ; install is WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary naming the object.
  * Command vectors: assert exact argv passed to run_subprocess.
  * I2 invariant: no AI/LLM/model/agent language in any summary.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises for any op including unknown ops and exit 127.
  * verify op: generous timeout=180 is passed to run_subprocess.
  * DEFERRED-TO-MOSSAD: live execution against real rpm on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.rpm.run_subprocess`` (the function in the rpm
  module's namespace) so the tool's import binding is intercepted.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import core.tools.rpm  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.rpm import RPM_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.rpm.run_subprocess."""
    return patch("core.tools.rpm.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_rpm_registered_in_module_registry(self) -> None:
        assert registry.get("rpm") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("rpm")
        assert spec is not None
        assert spec.name == "rpm"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("rpm")
        assert spec is not None
        expected = {
            "query_info",
            "query_files",
            "query_file",
            "verify",
            "checksig",
            "install",
            "rpm2cpio",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize(
        "op",
        ["query_info", "query_files", "query_file", "verify", "checksig", "rpm2cpio"],
    )
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("rpm", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    def test_install_is_write(self) -> None:
        cls = registry.permission_class_for("rpm", "install")
        assert cls is OpClass.WRITE

    def test_spec_permission_class_for_install(self) -> None:
        assert RPM_SPEC.permission_class_for("install") is OpClass.WRITE

    def test_spec_permission_class_for_query_info(self) -> None:
        assert RPM_SPEC.permission_class_for("query_info") is OpClass.READ


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_query_info_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Name: bash"))
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("query_info", {"package": "bash"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "-qi", "bash"]

    def test_query_files_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="/usr/bin/bash\n"))
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("query_files", {"package": "bash"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "-ql", "bash"]

    def test_query_file_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="bash-5.1.8-6.el9.x86_64\n"))
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("query_file", {"file": "/usr/bin/bash"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "-qf", "/usr/bin/bash"]

    def test_verify_package_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("verify", {"package": "openssh-server"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "-V", "openssh-server"]

    def test_verify_all_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("verify", {"package": ""})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "-Va"]

    def test_verify_missing_optional_package(self) -> None:
        """verify with no 'package' key should default to rpm -Va."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("verify", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "-Va"]

    def test_checksig_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="/tmp/pkg.rpm: digests signatures OK\n"))
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("checksig", {"rpm_file": "/tmp/pkg.rpm"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "--checksig", "/tmp/pkg.rpm"]

    def test_install_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Updating / installing...\n"))
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("install", {"rpm_file": "/tmp/myapp-1.0.x86_64.rpm"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm", "-ivh", "/tmp/myapp-1.0.x86_64.rpm"]

    def test_rpm2cpio_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="<cpio-data>"))
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("rpm2cpio", {"rpm_file": "/tmp/pkg.rpm"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["rpm2cpio", "/tmp/pkg.rpm"]

    def test_verify_uses_generous_timeout(self) -> None:
        """verify op must pass timeout >= 120 to handle slow full-system audits."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.rpm.run_subprocess", mock_fn):
            _execute("verify", {"package": ""})
        kwargs = mock_fn.call_args[1]
        assert "timeout" in kwargs
        assert kwargs["timeout"] >= 120


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("query_info",  {"package": "bash"}),
        ("query_files", {"package": "bash"}),
        ("query_file",  {"file": "/usr/bin/bash"}),
        ("verify",      {"package": "bash"}),
        ("checksig",    {"rpm_file": "/tmp/pkg.rpm"}),
        ("install",     {"rpm_file": "/tmp/pkg.rpm"}),
        ("rpm2cpio",    {"rpm_file": "/tmp/pkg.rpm"}),
    ])
    def test_exit_0_is_ok(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="some output")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("query_info",  {"package": "ghost-pkg"}),
        ("query_files", {"package": "ghost-pkg"}),
        ("query_file",  {"file": "/no/such/file"}),
        ("verify",      {"package": "ghost-pkg"}),
        ("checksig",    {"rpm_file": "/no/such.rpm"}),
        ("install",     {"rpm_file": "/no/such.rpm"}),
        ("rpm2cpio",    {"rpm_file": "/no/such.rpm"}),
    ])
    def test_nonzero_exit_not_ok(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="not found")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1

    def test_query_info_failure_names_package_in_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="package not installed")):
            result = _execute("query_info", {"package": "nosuchpkg"})
        assert not result.ok
        assert "nosuchpkg" in result.summary

    def test_install_failure_names_file_in_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="dependency failed")):
            result = _execute("install", {"rpm_file": "/tmp/badpkg.rpm"})
        assert not result.ok
        assert "/tmp/badpkg.rpm" in result.summary
        assert "exit 1" in result.summary.lower() or "failed" in result.summary.lower()

    def test_checksig_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="signatures NOT OK")):
            result = _execute("checksig", {"rpm_file": "/tmp/bad.rpm"})
        assert not result.ok
        assert "/tmp/bad.rpm" in result.summary


# ---------------------------------------------------------------------------
# I2 — No AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {
        "AI", "LLM", "model", "agent", "agentic", "neural", "language model",
    }

    @pytest.mark.parametrize("op,args", [
        ("query_info",  {"package": "bash"}),
        ("query_files", {"package": "bash"}),
        ("query_file",  {"file": "/usr/bin/bash"}),
        ("verify",      {"package": "bash"}),
        ("checksig",    {"rpm_file": "/tmp/pkg.rpm"}),
        ("install",     {"rpm_file": "/tmp/pkg.rpm"}),
        ("rpm2cpio",    {"rpm_file": "/tmp/pkg.rpm"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("query_info",  {"package": "bash"}),
        ("install",     {"rpm_file": "/tmp/pkg.rpm"}),
        ("verify",      {"package": "bash"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "error: Failed to open /tmp/pkg.rpm: "
        "AVC avc: denied { read } for pid=5678 comm=\"rpm\" name=\"pkg.rpm\""
    )

    @pytest.mark.parametrize("op,args", [
        ("query_info",  {"package": "bash"}),
        ("query_files", {"package": "bash"}),
        ("query_file",  {"file": "/usr/bin/bash"}),
        ("verify",      {"package": "bash"}),
        ("checksig",    {"rpm_file": "/tmp/pkg.rpm"}),
        ("install",     {"rpm_file": "/tmp/pkg.rpm"}),
        ("rpm2cpio",    {"rpm_file": "/tmp/pkg.rpm"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"No SELinux hint in summary for op='{op}': {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="package not installed")):
            result = _execute("query_info", {"package": "ghost-pkg"})
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary


# ---------------------------------------------------------------------------
# execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert len(result.summary) > 0

    def test_exit_127_binary_not_found(self) -> None:
        """exit_code=127 (missing binary) returns a well-formed ToolResult."""
        with _patch_run(_fail_result(exit_code=127, stderr="command not found")):
            result = _execute("query_info", {"package": "bash"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("query_info",  {"package": "x"}),
        ("query_files", {"package": "x"}),
        ("query_file",  {"file": "/x"}),
        ("verify",      {}),
        ("checksig",    {"rpm_file": "/x.rpm"}),
        ("install",     {"rpm_file": "/x.rpm"}),
        ("rpm2cpio",    {"rpm_file": "/x.rpm"}),
    ])
    def test_all_ops_degrade_gracefully_on_failure(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("query_info",  {"package": "bash"}),
        ("query_files", {"package": "bash"}),
        ("query_file",  {"file": "/usr/bin/bash"}),
        ("verify",      {"package": "bash"}),
        ("checksig",    {"rpm_file": "/tmp/pkg.rpm"}),
        ("install",     {"rpm_file": "/tmp/pkg.rpm"}),
        ("rpm2cpio",    {"rpm_file": "/tmp/pkg.rpm"}),
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
        ("query_info",  {"package": "bash"}),
        ("query_files", {"package": "bash"}),
        ("query_file",  {"file": "/usr/bin/bash"}),
        ("verify",      {"package": "bash"}),
        ("checksig",    {"rpm_file": "/tmp/pkg.rpm"}),
        ("install",     {"rpm_file": "/tmp/pkg.rpm"}),
        ("rpm2cpio",    {"rpm_file": "/tmp/pkg.rpm"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# query_files line count in summary
# ---------------------------------------------------------------------------

class TestQueryFilesLineCount:
    def test_line_count_in_summary(self) -> None:
        stdout = "/usr/bin/bash\n/usr/share/man/man1/bash.1.gz\n/etc/bash.bashrc\n"
        with _patch_run(_ok_result(stdout=stdout)):
            result = _execute("query_files", {"package": "bash"})
        assert result.ok
        # summary should mention the count of files
        assert "3" in result.summary or "file" in result.summary.lower()


# ---------------------------------------------------------------------------
# query_file: file owner named in success summary
# ---------------------------------------------------------------------------

class TestQueryFileSummary:
    def test_owner_in_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="bash-5.1.8-6.el9.x86_64\n")):
            result = _execute("query_file", {"file": "/usr/bin/bash"})
        assert result.ok
        assert "/usr/bin/bash" in result.summary

    def test_file_path_in_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="not owned by any package")):
            result = _execute("query_file", {"file": "/tmp/orphan.so"})
        assert not result.ok
        assert "/tmp/orphan.so" in result.summary


# ---------------------------------------------------------------------------
# verify: discrepancy output mentioned in failure summary
# ---------------------------------------------------------------------------

class TestVerifySummary:
    def test_verify_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="")):
            result = _execute("verify", {"package": "openssh-server"})
        assert result.ok
        assert "pass" in result.summary.lower() or "no discrepan" in result.summary.lower()

    def test_verify_all_success_summary(self) -> None:
        with _patch_run(_ok_result(stdout="")):
            result = _execute("verify", {"package": ""})
        assert result.ok
        assert "all installed" in result.summary.lower() or "pass" in result.summary.lower()

    def test_verify_failure_summary(self) -> None:
        discrepancy_output = "S.5....T.  c /etc/openssh-server/ssh_config\n"
        with _patch_run(_fail_result(exit_code=1, stdout=discrepancy_output, stderr="")):
            result = _execute("verify", {"package": "openssh-server"})
        assert not result.ok
        assert "discrepancy" in result.summary.lower() or "exit 1" in result.summary.lower()


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_query_info(self) -> None:
        with _patch_run(_ok_result(stdout="Name: bash")):
            result = registry.dispatch("rpm", "query_info", {"package": "bash"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_install(self) -> None:
        with _patch_run(_ok_result(stdout="Installing...")):
            result = registry.dispatch("rpm", "install", {"rpm_file": "/tmp/pkg.rpm"})
        assert result.ok

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'package'"):
            registry.dispatch("rpm", "query_info", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("rpm", "nonexistent_op", {"package": "x"})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real rpm on Rocky Linux 9")
def test_live_query_info_bash() -> None:
    """Live: rpm -qi bash returns a populated ToolResult."""
    result = _execute("query_info", {"package": "bash"})
    assert result.exit_code == 0
    assert "bash" in result.stdout.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real rpm on Rocky Linux 9")
def test_live_query_file_bash_binary() -> None:
    """Live: rpm -qf /usr/bin/bash returns the owning package."""
    result = _execute("query_file", {"file": "/usr/bin/bash"})
    assert result.exit_code == 0
    assert "bash" in result.stdout.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real rpm on Rocky Linux 9 (slow)")
def test_live_verify_all() -> None:
    """Live: rpm -Va completes without raising (may return exit 1 if discrepancies exist)."""
    result = _execute("verify", {"package": ""})
    assert result.exit_code is not None
    assert isinstance(result.summary, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real rpm2cpio on Rocky Linux 9")
def test_live_rpm2cpio_requires_file() -> None:
    """Live: rpm2cpio on a nonexistent file returns exit_code != 0, no exception."""
    result = _execute("rpm2cpio", {"rpm_file": "/tmp/does_not_exist.rpm"})
    assert result.exit_code != 0
    assert not result.ok
