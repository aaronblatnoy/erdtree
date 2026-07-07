"""tests/test_tools_grub.py — Unit tests for core/tools/grub.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without grubby or grub2-mkconfig present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: info/default-kernel are READ; set-default/args-add/
    args-remove/set-password are WRITE; mkconfig/remove-kernel are DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code=1) → ok=False, failure summary naming key fields.
  * Command vectors: correct argv lists are passed to run_subprocess.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2 invariant: no AI/LLM/model/agent language in any summary.
  * execute() never raises (I9): unknown op and missing binary (exit 127) both
    return a well-formed ToolResult without raising.
  * DEFERRED-TO-MOSSAD: live execution against real grubby on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.grub.run_subprocess`` (the function in the grub
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.grub  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.grub import GRUB_SPEC, _execute

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

_KERNEL = "/boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64"
_KERNEL_ARGS = "quiet splash"
_OUTPUT_FILE = "/boot/grub2/grub.cfg"


def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.grub.run_subprocess."""
    return patch("core.tools.grub.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_grub_registered_in_module_registry(self) -> None:
        assert registry.get("grub") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("grub")
        assert spec is not None
        assert spec.name == "grub"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("grub")
        assert spec is not None
        expected = {
            "info", "default-kernel", "set-default",
            "args-add", "args-remove",
            "mkconfig", "set-password", "remove-kernel",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# 2. Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["info", "default-kernel"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("grub", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["set-default", "args-add", "args-remove", "set-password"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("grub", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["mkconfig", "remove-kernel"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("grub", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# 3. Command vectors (argv assertions)
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_info_argv_default_all(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="index=0\nkernel=\"" + _KERNEL + "\"\n"))
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("info", {"kernel": "ALL"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grubby", "--info=ALL"]

    def test_info_argv_specific_kernel(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="index=0\n"))
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("info", {"kernel": _KERNEL})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grubby", f"--info={_KERNEL}"]

    def test_default_kernel_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout=_KERNEL + "\n"))
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("default-kernel", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grubby", "--default-kernel"]

    def test_set_default_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("set-default", {"kernel": _KERNEL})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grubby", f"--set-default={_KERNEL}"]

    def test_args_add_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("args-add", {"kernel": _KERNEL, "kernel_args": _KERNEL_ARGS})
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "grubby",
            f"--update-kernel={_KERNEL}",
            f"--args={_KERNEL_ARGS}",
        ]

    def test_args_remove_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("args-remove", {"kernel": _KERNEL, "kernel_args": _KERNEL_ARGS})
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "grubby",
            f"--update-kernel={_KERNEL}",
            f"--remove-args={_KERNEL_ARGS}",
        ]

    def test_mkconfig_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result(stdout="done\n"))
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("mkconfig", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grub2-mkconfig", "-o", _OUTPUT_FILE]

    def test_mkconfig_argv_custom_output(self) -> None:
        custom = "/boot/efi/EFI/redhat/grub.cfg"
        mock_fn = MagicMock(return_value=_ok_result(stdout="done\n"))
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("mkconfig", {"output_file": custom})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grub2-mkconfig", "-o", custom]

    def test_set_password_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("set-password", {"password": "s3cr3t"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grub2-setpassword"]
        # password must NOT appear in argv
        assert "s3cr3t" not in " ".join(argv)

    def test_remove_kernel_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("remove-kernel", {"kernel": _KERNEL})
        argv = mock_fn.call_args[0][0]
        assert argv == ["grubby", f"--remove-kernel={_KERNEL}"]


# ---------------------------------------------------------------------------
# 4. Exit-code mapping — success and failure summaries
# ---------------------------------------------------------------------------

class TestInfo:
    def test_success_summary_contains_kernel(self) -> None:
        with _patch_run(_ok_result(stdout="index=0\nkernel=\"" + _KERNEL + "\"\n")):
            result = _execute("info", {"kernel": _KERNEL})
        assert result.ok
        assert _KERNEL in result.summary

    def test_failure_summary_contains_kernel_and_exit_code(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error: could not find kernel")):
            result = _execute("info", {"kernel": _KERNEL})
        assert not result.ok
        assert _KERNEL in result.summary
        assert "1" in result.summary


class TestDefaultKernel:
    def test_success_summary_contains_path(self) -> None:
        with _patch_run(_ok_result(stdout=_KERNEL + "\n")):
            result = _execute("default-kernel", {})
        assert result.ok
        assert _KERNEL in result.summary

    def test_failure_summary(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error")):
            result = _execute("default-kernel", {})
        assert not result.ok
        assert "default" in result.summary.lower() or "kernel" in result.summary.lower()


class TestSetDefault:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("set-default", {"kernel": _KERNEL})
        assert result.ok
        assert _KERNEL in result.summary
        assert "default" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="could not find kernel")):
            result = _execute("set-default", {"kernel": _KERNEL})
        assert not result.ok
        assert _KERNEL in result.summary
        assert "1" in result.summary


class TestArgsAdd:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("args-add", {"kernel": _KERNEL, "kernel_args": "quiet"})
        assert result.ok
        assert "quiet" in result.summary
        assert "added" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="could not find kernel")):
            result = _execute("args-add", {"kernel": _KERNEL, "kernel_args": "quiet"})
        assert not result.ok
        assert "1" in result.summary


class TestArgsRemove:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("args-remove", {"kernel": _KERNEL, "kernel_args": "rhgb"})
        assert result.ok
        assert "rhgb" in result.summary
        assert "removed" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="could not find kernel")):
            result = _execute("args-remove", {"kernel": _KERNEL, "kernel_args": "rhgb"})
        assert not result.ok
        assert "1" in result.summary


class TestMkconfig:
    def test_success(self) -> None:
        with _patch_run(_ok_result(stdout="Generating grub configuration file ...\ndone\n")):
            result = _execute("mkconfig", {})
        assert result.ok
        assert "grub" in result.summary.lower() or "configuration" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="failed to get canonical path")):
            result = _execute("mkconfig", {})
        assert not result.ok
        assert "1" in result.summary

    def test_destructive_permission_class(self) -> None:
        cls = GRUB_SPEC.permission_class_for("mkconfig")
        assert cls is OpClass.DESTRUCTIVE


class TestSetPassword:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("set-password", {"password": "correcthorsebatterystaple"})
        assert result.ok
        assert "password" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="failed to open user.cfg")):
            result = _execute("set-password", {"password": "correcthorsebatterystaple"})
        assert not result.ok
        assert "password" in result.summary.lower()

    def test_password_not_in_argv(self) -> None:
        """Password must never appear in the subprocess argv (passes via stdin)."""
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.grub.run_subprocess", mock_fn):
            _execute("set-password", {"password": "topsecret99"})
        argv = mock_fn.call_args[0][0]
        assert "topsecret99" not in " ".join(argv)


class TestRemoveKernel:
    def test_success(self) -> None:
        with _patch_run(_ok_result()):
            result = _execute("remove-kernel", {"kernel": _KERNEL})
        assert result.ok
        assert _KERNEL in result.summary
        assert "removed" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="could not find kernel")):
            result = _execute("remove-kernel", {"kernel": _KERNEL})
        assert not result.ok
        assert _KERNEL in result.summary
        assert "1" in result.summary

    def test_destructive_permission_class(self) -> None:
        cls = GRUB_SPEC.permission_class_for("remove-kernel")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# 5. I2-clean summaries — no AI/LLM/model/agent language
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("info",           {"kernel": "ALL"}),
        ("default-kernel", {}),
        ("set-default",    {"kernel": _KERNEL}),
        ("args-add",       {"kernel": _KERNEL, "kernel_args": "quiet"}),
        ("args-remove",    {"kernel": _KERNEL, "kernel_args": "rhgb"}),
        ("mkconfig",       {}),
        ("set-password",   {"password": "s3cr3t"}),
        ("remove-kernel",  {"kernel": _KERNEL}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("info",           {"kernel": _KERNEL}),
        ("set-default",    {"kernel": _KERNEL}),
        ("args-add",       {"kernel": _KERNEL, "kernel_args": "quiet"}),
        ("mkconfig",       {}),
        ("remove-kernel",  {"kernel": _KERNEL}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# 6. SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "Failed to run grubby: "
        "AVC avc: denied { read } for pid=1234 "
        "comm=\"grubby\" name=\"grub2\"  "
        "scontext=system_u:system_r:bootloader_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("info",           {"kernel": "ALL"}),
        ("set-default",    {"kernel": _KERNEL}),
        ("args-add",       {"kernel": _KERNEL, "kernel_args": "quiet"}),
        ("args-remove",    {"kernel": _KERNEL, "kernel_args": "rhgb"}),
        ("mkconfig",       {}),
        ("set-password",   {"password": "s3cr3t"}),
        ("remove-kernel",  {"kernel": _KERNEL}),
    ])
    def test_avc_denial_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op='{op}': {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="error: could not find kernel")):
            result = _execute("info", {"kernel": _KERNEL})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# 7. execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        """An unknown op must not raise — it must return a well-formed ToolResult."""
        result = _execute("nonexistent_op_xyz", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """run_subprocess returning exit 127 (binary not found) must not raise."""
        not_found = ToolResult(
            exit_code=127, stdout="", stderr="grubby: command not found", summary=""
        )
        with patch("core.tools.grub.run_subprocess", return_value=not_found):
            result = _execute("info", {"kernel": "ALL"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    @pytest.mark.parametrize("op,args", [
        ("info",           {"kernel": "ALL"}),
        ("default-kernel", {}),
        ("set-default",    {"kernel": _KERNEL}),
        ("args-add",       {"kernel": _KERNEL, "kernel_args": "quiet"}),
        ("args-remove",    {"kernel": _KERNEL, "kernel_args": "rhgb"}),
        ("mkconfig",       {}),
        ("set-password",   {"password": "s3cr3t"}),
        ("remove-kernel",  {"kernel": _KERNEL}),
    ])
    def test_execute_does_not_raise_for_any_op(self, op: str, args: dict) -> None:
        not_found = ToolResult(exit_code=127, stdout="", stderr="command not found", summary="")
        with patch("core.tools.grub.run_subprocess", return_value=not_found):
            try:
                result = _execute(op, args)
            except Exception as exc:
                pytest.fail(f"_execute('{op}', ...) raised unexpectedly: {exc!r}")
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# 8. ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("info",           {"kernel": "ALL"}),
        ("default-kernel", {}),
        ("set-default",    {"kernel": _KERNEL}),
        ("args-add",       {"kernel": _KERNEL, "kernel_args": "quiet"}),
        ("args-remove",    {"kernel": _KERNEL, "kernel_args": "rhgb"}),
        ("mkconfig",       {}),
        ("set-password",   {"password": "s3cr3t"}),
        ("remove-kernel",  {"kernel": _KERNEL}),
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
        ("info",           {"kernel": "ALL"}),
        ("default-kernel", {}),
        ("set-default",    {"kernel": _KERNEL}),
        ("args-add",       {"kernel": _KERNEL, "kernel_args": "quiet"}),
        ("args-remove",    {"kernel": _KERNEL, "kernel_args": "rhgb"}),
        ("mkconfig",       {}),
        ("set-password",   {"password": "s3cr3t"}),
        ("remove-kernel",  {"kernel": _KERNEL}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok_result()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# 9. Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_info(self) -> None:
        with _patch_run(_ok_result(stdout="index=0\n")):
            result = registry.dispatch("grub", "info", {"kernel": "ALL"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_default_kernel(self) -> None:
        with _patch_run(_ok_result(stdout=_KERNEL + "\n")):
            result = registry.dispatch("grub", "default-kernel", {})
        assert result.ok

    def test_dispatch_mkconfig(self) -> None:
        with _patch_run(_ok_result(stdout="done\n")):
            result = registry.dispatch("grub", "mkconfig", {})
        assert result.ok

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("grub", "nonexistent_op", {})

    def test_dispatch_set_default_missing_kernel_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'kernel'"):
            registry.dispatch("grub", "set-default", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real grubby on Rocky Linux 9")
def test_live_info_all() -> None:
    """Live: grubby --info=ALL returns populated ToolResult."""
    result = _execute("info", {"kernel": "ALL"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real grubby on Rocky Linux 9")
def test_live_default_kernel() -> None:
    """Live: grubby --default-kernel returns a kernel path."""
    result = _execute("default-kernel", {})
    assert result.exit_code == 0
    assert result.stdout.strip().startswith("/boot/vmlinuz-")


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root + real grub2-mkconfig on Rocky Linux 9")
def test_live_mkconfig_requires_root() -> None:
    """Live: grub2-mkconfig -o /boot/grub2/grub.cfg requires root privileges.

    Expected to fail gracefully (non-zero exit) when run as a non-root user;
    should succeed and produce a populated grub.cfg when run as root.
    """
    result = _execute("mkconfig", {})
    assert result.exit_code is not None
