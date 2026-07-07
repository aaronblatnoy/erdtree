"""tests/test_tools_virsh.py — Unit tests for core/tools/virsh.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without virsh or libvirt present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/dominfo/pool-list are READ;
    start/shutdown/define/pool-define are WRITE;
    destroy/undefine/pool-destroy are DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code != 0) → ok=False, failure summary naming the object.
  * Command vectors are correct (argv lists with right binary + subcommand).
  * undefine with remove_storage=True appends --remove-all-storage to argv.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2 compliance: no AI/LLM/model/agent/agentic/neural language in summaries.
  * execute() never raises (I9): unknown op and missing binary both degrade
    to a well-formed ToolResult.
  * DEFERRED-TO-MOSSAD: live execution against real virsh on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.virsh.run_subprocess`` (the name in the virsh module's
  namespace, where ``from core.tools import run_subprocess`` binds it).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration via side-effect import.
import core.tools.virsh  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.virsh import VIRSH_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.virsh.run_subprocess."""
    return patch("core.tools.virsh.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_virsh_registered(self) -> None:
        assert registry.get("virsh") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("virsh")
        assert spec is not None
        assert spec.name == "virsh"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("virsh")
        assert spec is not None
        expected = {
            "list", "dominfo", "start", "shutdown", "define",
            "destroy", "undefine", "pool-list", "pool-define", "pool-destroy",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list", "dominfo", "pool-list"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("virsh", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["start", "shutdown", "define", "pool-define"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("virsh", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["destroy", "undefine", "pool-destroy"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("virsh", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vector tests
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_list_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Id   Name   State\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "list", "--all"]

    def test_dominfo_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Id: 1\nName: centos9-web\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("dominfo", {"domain": "centos9-web"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "dominfo", "centos9-web"]

    def test_start_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Domain 'centos9-web' started\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("start", {"domain": "centos9-web"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "start", "centos9-web"]

    def test_shutdown_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Domain centos9-web is being shutdown\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("shutdown", {"domain": "centos9-web"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "shutdown", "centos9-web"]

    def test_define_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Domain 'newvm' defined from /tmp/vm.xml\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("define", {"xmlfile": "/tmp/vm.xml"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "define", "/tmp/vm.xml"]

    def test_destroy_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Domain centos9-web destroyed\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("destroy", {"domain": "centos9-web"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "destroy", "centos9-web"]

    def test_undefine_argv_no_storage(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Domain centos9-web has been undefined\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("undefine", {"domain": "centos9-web"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "undefine", "centos9-web"]
        assert "--remove-all-storage" not in argv

    def test_undefine_argv_with_storage(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Domain centos9-web has been undefined\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("undefine", {"domain": "centos9-web", "remove_storage": True})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "undefine", "centos9-web", "--remove-all-storage"]

    def test_pool_list_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout=" Name    State\n default active\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("pool-list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "pool-list", "--all"]

    def test_pool_define_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Pool images defined from /tmp/pool.xml\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("pool-define", {"xmlfile": "/tmp/pool.xml"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "pool-define", "/tmp/pool.xml"]

    def test_pool_destroy_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="Pool default destroyed\n"))
        with patch("core.tools.virsh.run_subprocess", mock_fn):
            _execute("pool-destroy", {"pool": "default"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["virsh", "pool-destroy", "default"]


# ---------------------------------------------------------------------------
# Exit-code mapping and summary content
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_list_success(self) -> None:
        with _patch_run(_ok_result(stdout=" Id   Name   State\n")):
            result = _execute("list", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_list_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="libvirt not running")):
            result = _execute("list", {})
        assert not result.ok
        assert "exit 1" in result.summary

    def test_dominfo_success(self) -> None:
        with _patch_run(_ok_result(stdout="Id: 1\nName: centos9-web\n")):
            result = _execute("dominfo", {"domain": "centos9-web"})
        assert result.ok
        assert "centos9-web" in result.summary

    def test_dominfo_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Domain not found")):
            result = _execute("dominfo", {"domain": "ghost-vm"})
        assert not result.ok
        assert "ghost-vm" in result.summary

    def test_start_success(self) -> None:
        with _patch_run(_ok_result(stdout="Domain 'centos9-web' started\n")):
            result = _execute("start", {"domain": "centos9-web"})
        assert result.ok
        assert "centos9-web" in result.summary
        assert "started" in result.summary.lower()

    def test_start_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Domain not found")):
            result = _execute("start", {"domain": "ghost-vm"})
        assert not result.ok
        assert "ghost-vm" in result.summary

    def test_shutdown_success(self) -> None:
        with _patch_run(_ok_result(stdout="Domain centos9-web is being shutdown\n")):
            result = _execute("shutdown", {"domain": "centos9-web"})
        assert result.ok
        assert "centos9-web" in result.summary

    def test_shutdown_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Domain not found")):
            result = _execute("shutdown", {"domain": "ghost-vm"})
        assert not result.ok
        assert "ghost-vm" in result.summary

    def test_define_success(self) -> None:
        with _patch_run(_ok_result(stdout="Domain 'newvm' defined from /tmp/vm.xml\n")):
            result = _execute("define", {"xmlfile": "/tmp/vm.xml"})
        assert result.ok
        assert "/tmp/vm.xml" in result.summary

    def test_define_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="No such file")):
            result = _execute("define", {"xmlfile": "/tmp/missing.xml"})
        assert not result.ok
        assert "/tmp/missing.xml" in result.summary

    def test_destroy_success(self) -> None:
        with _patch_run(_ok_result(stdout="Domain centos9-web destroyed\n")):
            result = _execute("destroy", {"domain": "centos9-web"})
        assert result.ok
        assert "centos9-web" in result.summary
        assert "powered off" in result.summary.lower() or "destroyed" in result.summary.lower()

    def test_destroy_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Domain not found")):
            result = _execute("destroy", {"domain": "ghost-vm"})
        assert not result.ok
        assert "ghost-vm" in result.summary
        assert "exit 1" in result.summary

    def test_undefine_success_no_storage(self) -> None:
        with _patch_run(_ok_result(stdout="Domain centos9-web has been undefined\n")):
            result = _execute("undefine", {"domain": "centos9-web"})
        assert result.ok
        assert "centos9-web" in result.summary
        assert "undefined" in result.summary.lower()

    def test_undefine_success_with_storage(self) -> None:
        with _patch_run(_ok_result(stdout="Domain centos9-web has been undefined\nVolume removed.\n")):
            result = _execute("undefine", {"domain": "centos9-web", "remove_storage": True})
        assert result.ok
        assert "centos9-web" in result.summary
        assert "storage" in result.summary.lower()

    def test_undefine_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Domain not found")):
            result = _execute("undefine", {"domain": "ghost-vm"})
        assert not result.ok
        assert "ghost-vm" in result.summary

    def test_pool_list_success(self) -> None:
        with _patch_run(_ok_result(stdout=" Name    State\n default active\n")):
            result = _execute("pool-list", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_pool_list_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="libvirt not running")):
            result = _execute("pool-list", {})
        assert not result.ok
        assert "exit 1" in result.summary

    def test_pool_define_success(self) -> None:
        with _patch_run(_ok_result(stdout="Pool images defined from /tmp/pool.xml\n")):
            result = _execute("pool-define", {"xmlfile": "/tmp/pool.xml"})
        assert result.ok
        assert "/tmp/pool.xml" in result.summary

    def test_pool_define_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="No such file")):
            result = _execute("pool-define", {"xmlfile": "/tmp/missing.xml"})
        assert not result.ok
        assert "/tmp/missing.xml" in result.summary

    def test_pool_destroy_success(self) -> None:
        with _patch_run(_ok_result(stdout="Pool default destroyed\n")):
            result = _execute("pool-destroy", {"pool": "default"})
        assert result.ok
        assert "default" in result.summary
        assert "destroyed" in result.summary.lower()

    def test_pool_destroy_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Pool not found")):
            result = _execute("pool-destroy", {"pool": "ghost-pool"})
        assert not result.ok
        assert "ghost-pool" in result.summary
        assert "exit 1" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list",         {}),
        ("dominfo",      {"domain": "centos9-web"}),
        ("start",        {"domain": "centos9-web"}),
        ("shutdown",     {"domain": "centos9-web"}),
        ("define",       {"xmlfile": "/tmp/vm.xml"}),
        ("destroy",      {"domain": "centos9-web"}),
        ("undefine",     {"domain": "centos9-web"}),
        ("pool-list",    {}),
        ("pool-define",  {"xmlfile": "/tmp/pool.xml"}),
        ("pool-destroy", {"pool": "default"}),
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
        ("list",         {}),
        ("dominfo",      {"domain": "centos9-web"}),
        ("start",        {"domain": "centos9-web"}),
        ("shutdown",     {"domain": "centos9-web"}),
        ("define",       {"xmlfile": "/tmp/vm.xml"}),
        ("destroy",      {"domain": "centos9-web"}),
        ("undefine",     {"domain": "centos9-web"}),
        ("pool-list",    {}),
        ("pool-define",  {"xmlfile": "/tmp/pool.xml"}),
        ("pool-destroy", {"pool": "default"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("list",         {}),
        ("dominfo",      {"domain": "centos9-web"}),
        ("start",        {"domain": "centos9-web"}),
        ("shutdown",     {"domain": "centos9-web"}),
        ("define",       {"xmlfile": "/tmp/vm.xml"}),
        ("destroy",      {"domain": "centos9-web"}),
        ("undefine",     {"domain": "centos9-web"}),
        ("pool-list",    {}),
        ("pool-define",  {"xmlfile": "/tmp/pool.xml"}),
        ("pool-destroy", {"pool": "default"}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=4321 "
            "comm=\"virsh\" name=\"qemu\" scontext=system_u:system_r:svirt_t:s0"
        )
        with _patch_run(_fail_result(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint not surfaced for op='{op}': {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Domain not found.")):
            result = _execute("dominfo", {"domain": "ghost-vm"})
        assert "ausearch" not in result.summary

    def test_selinux_keyword_in_stderr_surfaces_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="selinux policy denies access")):
            result = _execute("start", {"domain": "centos9-web"})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# I2 compliance — no AI/LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent/agentic/neural language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("list",         {}),
        ("dominfo",      {"domain": "centos9-web"}),
        ("start",        {"domain": "centos9-web"}),
        ("shutdown",     {"domain": "centos9-web"}),
        ("define",       {"xmlfile": "/tmp/vm.xml"}),
        ("destroy",      {"domain": "centos9-web"}),
        ("undefine",     {"domain": "centos9-web"}),
        ("undefine",     {"domain": "centos9-web", "remove_storage": True}),
        ("pool-list",    {}),
        ("pool-define",  {"xmlfile": "/tmp/pool.xml"}),
        ("pool-destroy", {"pool": "default"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("list",         {}),
        ("dominfo",      {"domain": "centos9-web"}),
        ("destroy",      {"domain": "centos9-web"}),
        ("pool-destroy", {"pool": "default"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error occurred")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """Simulate a missing virsh binary (run_subprocess returns exit 127)."""
        missing = ToolResult(
            exit_code=127,
            stdout="",
            stderr="virsh: command not found",
            summary="",
        )
        with patch("core.tools.virsh.run_subprocess", return_value=missing):
            result = _execute("list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_dominfo_exit_127(self) -> None:
        missing = ToolResult(
            exit_code=127,
            stdout="",
            stderr="virsh: command not found",
            summary="",
        )
        with patch("core.tools.virsh.run_subprocess", return_value=missing):
            result = _execute("dominfo", {"domain": "centos9-web"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_unknown_op_summary_not_empty(self) -> None:
        result = _execute("bogus_operation", {})
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}

    def test_undefine_optional_arg_missing_does_not_raise(self) -> None:
        """remove_storage is optional; omitting it must not cause a KeyError."""
        with _patch_run(_ok_result(stdout="Domain x has been undefined\n")):
            result = _execute("undefine", {"domain": "x"})
        assert isinstance(result, ToolResult)
        assert result.ok


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_list(self) -> None:
        with _patch_run(_ok_result(stdout="Id   Name   State\n")):
            result = registry.dispatch("virsh", "list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_dominfo(self) -> None:
        with _patch_run(_ok_result(stdout="Id: 1\n")):
            result = registry.dispatch("virsh", "dominfo", {"domain": "centos9-web"})
        assert result.ok

    def test_dispatch_destroy(self) -> None:
        with _patch_run(_ok_result(stdout="Domain centos9-web destroyed\n")):
            result = registry.dispatch("virsh", "destroy", {"domain": "centos9-web"})
        assert result.ok

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument"):
            registry.dispatch("virsh", "dominfo", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("virsh", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real virsh + libvirt on Rocky Linux 9")
def test_live_list_all() -> None:
    """Live: virsh list --all returns a populated ToolResult."""
    result = _execute("list", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real virsh + libvirt on Rocky Linux 9")
def test_live_pool_list() -> None:
    """Live: virsh pool-list --all returns storage pool information."""
    result = _execute("pool-list", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real virsh + libvirt on Rocky Linux 9 with root/qemu")
def test_live_destroy_requires_privileges() -> None:
    """Live: virsh destroy requires libvirt privileges.

    Without qemu:///system access this should return non-zero exit.
    The test verifies that execute() still returns a well-formed ToolResult
    rather than raising an exception.
    """
    result = _execute("destroy", {"domain": "test-vm"})
    assert result.exit_code is not None
    assert isinstance(result, ToolResult)
