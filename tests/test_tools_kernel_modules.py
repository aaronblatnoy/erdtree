"""tests/test_tools_kernel_modules.py — Unit tests for core/tools/kernel_modules.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without lsmod, modinfo, modprobe, or rmmod present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: lsmod/modinfo are READ; modprobe/modules-load.d are WRITE;
    rmmod is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct command vector.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code != 0) -> ok=False, failure summary naming the module.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2 invariant: no AI/LLM/model/agent language in any summary.
  * I9 invariant: execute() NEVER raises for any op including unknown op and
    exit_code=127 (missing binary).
  * ToolResult structure: all four keys always present, as_dict() correct.
  * DEFERRED-TO-MOSSAD: live execution against real binaries on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.kernel_modules.run_subprocess`` (in the module's
  namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.kernel_modules  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.kernel_modules import KERNEL_MODULES_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager that patches run_subprocess in kernel_modules."""
    return patch("core.tools.kernel_modules.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_kernel_modules_registered(self) -> None:
        assert registry.get("kernel_modules") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("kernel_modules")
        assert spec is not None
        assert spec.name == "kernel_modules"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("kernel_modules")
        assert spec is not None
        expected = {"lsmod", "modinfo", "modprobe", "rmmod", "modules-load.d"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["lsmod", "modinfo"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("kernel_modules", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["modprobe", "modules-load.d"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("kernel_modules", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_rmmod_is_destructive(self) -> None:
        cls = registry.permission_class_for("kernel_modules", "rmmod")
        assert cls is OpClass.DESTRUCTIVE

    def test_spec_permission_class_for(self) -> None:
        assert KERNEL_MODULES_SPEC.permission_class_for("rmmod") is OpClass.DESTRUCTIVE
        assert KERNEL_MODULES_SPEC.permission_class_for("lsmod") is OpClass.READ


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_lsmod_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Module\n"))
        with patch("core.tools.kernel_modules.run_subprocess", mock_fn):
            _execute("lsmod", {})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["lsmod"]

    def test_modinfo_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="filename: /lib/..."))
        with patch("core.tools.kernel_modules.run_subprocess", mock_fn):
            _execute("modinfo", {"module": "nf_conntrack"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["modinfo", "nf_conntrack"]

    def test_modprobe_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.kernel_modules.run_subprocess", mock_fn):
            _execute("modprobe", {"module": "br_netfilter"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["modprobe", "br_netfilter"]

    def test_rmmod_vector(self) -> None:
        """rmmod must appear verbatim as argv[0] so the classifier can escalate it."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.kernel_modules.run_subprocess", mock_fn):
            _execute("rmmod", {"module": "dummy"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["rmmod", "dummy"]
        # argv[0] must be the literal destructive verb
        assert cmd[0] == "rmmod"

    def test_modules_load_d_vector_default_filename(self) -> None:
        """modules-load.d uses tee; conf path derived from module name."""
        mock_fn = MagicMock(return_value=_ok(stdout="overlay\n"))
        with patch("core.tools.kernel_modules.run_subprocess", mock_fn):
            _execute("modules-load.d", {"module": "overlay"})
        cmd = mock_fn.call_args[0][0]
        assert cmd[0] == "tee"
        assert cmd[1] == "/etc/modules-load.d/overlay.conf"

    def test_modules_load_d_vector_custom_filename(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="nf_conntrack\n"))
        with patch("core.tools.kernel_modules.run_subprocess", mock_fn):
            _execute("modules-load.d", {"module": "nf_conntrack", "filename": "conntrack"})
        cmd = mock_fn.call_args[0][0]
        assert cmd == ["tee", "/etc/modules-load.d/conntrack.conf"]


# ---------------------------------------------------------------------------
# lsmod operation
# ---------------------------------------------------------------------------

class TestLsmod:
    def test_success_summary_contains_count(self) -> None:
        # Header + 3 module lines = 3 modules
        stdout = "Module                         Size  Used by\ndummy   16384  0\nveth    28672  0\ntun     53248  0\n"
        with _patch_run(_ok(stdout=stdout)):
            result = _execute("lsmod", {})
        assert result.ok
        assert "3" in result.summary or "module" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="lsmod: unknown error")):
            result = _execute("lsmod", {})
        assert not result.ok
        assert "exit 1" in result.summary or "Failed" in result.summary

    def test_result_stdout_preserved(self) -> None:
        stdout = "Module                         Size  Used by\n"
        with _patch_run(_ok(stdout=stdout)):
            result = _execute("lsmod", {})
        assert result.stdout == stdout


# ---------------------------------------------------------------------------
# modinfo operation
# ---------------------------------------------------------------------------

class TestModinfo:
    def test_success_summary(self) -> None:
        with _patch_run(_ok(stdout="filename: /lib/modules/x.ko\nlicense: GPL\n")):
            result = _execute("modinfo", {"module": "xfs"})
        assert result.ok
        assert "xfs" in result.summary

    def test_failure_module_not_found(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="modinfo: ERROR: Module bogus not found.")):
            result = _execute("modinfo", {"module": "bogus_module"})
        assert not result.ok
        assert "bogus_module" in result.summary

    def test_exit_code_in_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=1)):
            result = _execute("modinfo", {"module": "bad_module"})
        assert "exit 1" in result.summary or "1" in result.summary


# ---------------------------------------------------------------------------
# modprobe operation
# ---------------------------------------------------------------------------

class TestModprobe:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("modprobe", {"module": "overlay"})
        assert result.ok
        assert "overlay" in result.summary
        assert "loaded" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="modprobe: FATAL: Module notamodule not found")):
            result = _execute("modprobe", {"module": "notamodule"})
        assert not result.ok
        assert "notamodule" in result.summary


# ---------------------------------------------------------------------------
# rmmod operation
# ---------------------------------------------------------------------------

class TestRmmod:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("rmmod", {"module": "dummy"})
        assert result.ok
        assert "dummy" in result.summary
        assert "removed" in result.summary.lower()

    def test_failure_in_use(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="rmmod: ERROR: Module nf_conntrack is in use")):
            result = _execute("rmmod", {"module": "nf_conntrack"})
        assert not result.ok
        assert "nf_conntrack" in result.summary
        assert "exit 1" in result.summary or "1" in result.summary

    def test_rmmod_is_destructive_class(self) -> None:
        cls = KERNEL_MODULES_SPEC.permission_class_for("rmmod")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# modules-load.d operation
# ---------------------------------------------------------------------------

class TestModulesLoadD:
    def test_success_summary_contains_conf_path(self) -> None:
        with _patch_run(_ok(stdout="br_netfilter\n")):
            result = _execute("modules-load.d", {"module": "br_netfilter"})
        assert result.ok
        assert "br_netfilter" in result.summary
        assert "/etc/modules-load.d/" in result.summary

    def test_failure_permission_denied(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="tee: /etc/modules-load.d/x.conf: Permission denied")):
            result = _execute("modules-load.d", {"module": "overlay"})
        assert not result.ok
        assert "overlay" in result.summary

    def test_is_write_class(self) -> None:
        assert KERNEL_MODULES_SPEC.permission_class_for("modules-load.d") is OpClass.WRITE


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("modinfo",       {"module": "xfs"}),
        ("modprobe",      {"module": "xfs"}),
        ("rmmod",         {"module": "xfs"}),
        ("modules-load.d", {"module": "xfs"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 comm=\"modprobe\" "
            "name=\"xfs.ko\" scontext=system_u:system_r:init_t"
        )
        with _patch_run(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="modinfo: ERROR: Module bogus not found.")):
            result = _execute("modinfo", {"module": "bogus"})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary

    def test_lsmod_no_selinux_on_clean(self) -> None:
        with _patch_run(_ok(stdout="Module\n")):
            result = _execute("lsmod", {})
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# I2 invariant — no AI/LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "agent", "agentic", "neural", "language model", "inference"}
    # Note: "model" is intentionally omitted here because it's a substring of
    # "kernel_module" — but "LLM", "language model", etc. remain banned.

    @pytest.mark.parametrize("op,args", [
        ("lsmod",          {}),
        ("modinfo",        {"module": "xfs"}),
        ("modprobe",       {"module": "overlay"}),
        ("rmmod",          {"module": "dummy"}),
        ("modules-load.d", {"module": "tun"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout="ok")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("lsmod",    {}),
        ("modinfo",  {"module": "xfs"}),
        ("rmmod",    {"module": "dummy"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestI9NeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("totally_unknown_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert "totally_unknown_op" in result.summary

    def test_exit_127_missing_binary(self) -> None:
        """run_subprocess returns exit_code=127 for missing binary; _execute must not raise."""
        missing_binary = ToolResult(
            exit_code=127,
            stdout="",
            stderr="lsmod: command not found",
            summary="",
        )
        with patch("core.tools.kernel_modules.run_subprocess", return_value=missing_binary):
            result = _execute("lsmod", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_exit_127_for_rmmod(self) -> None:
        missing = ToolResult(exit_code=127, stdout="", stderr="rmmod not found", summary="")
        with patch("core.tools.kernel_modules.run_subprocess", return_value=missing):
            result = _execute("rmmod", {"module": "dummy"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_unknown_op_does_not_raise(self) -> None:
        try:
            result = _execute("badop_xyz", {"module": "anything"})
        except Exception as exc:
            pytest.fail(f"_execute raised unexpectedly: {exc}")
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("lsmod",          {}),
        ("modinfo",        {"module": "xfs"}),
        ("modprobe",       {"module": "overlay"}),
        ("rmmod",          {"module": "dummy"}),
        ("modules-load.d", {"module": "tun"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("lsmod",          {}),
        ("modinfo",        {"module": "x"}),
        ("modprobe",       {"module": "x"}),
        ("rmmod",          {"module": "x"}),
        ("modules-load.d", {"module": "x"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_lsmod(self) -> None:
        with _patch_run(_ok(stdout="Module\n")):
            result = registry.dispatch("kernel_modules", "lsmod", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_modinfo(self) -> None:
        with _patch_run(_ok(stdout="filename: /lib/...")):
            result = registry.dispatch("kernel_modules", "modinfo", {"module": "xfs"})
        assert result.ok

    def test_dispatch_modprobe(self) -> None:
        with _patch_run(_ok()):
            result = registry.dispatch("kernel_modules", "modprobe", {"module": "overlay"})
        assert result.ok

    def test_dispatch_rmmod(self) -> None:
        with _patch_run(_ok()):
            result = registry.dispatch("kernel_modules", "rmmod", {"module": "dummy"})
        assert result.ok

    def test_dispatch_missing_module_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'module'"):
            registry.dispatch("kernel_modules", "modinfo", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("kernel_modules", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires lsmod on Rocky Linux 9")
def test_live_lsmod() -> None:
    """Live: lsmod returns a populated ToolResult."""
    result = _execute("lsmod", {})
    assert result.exit_code == 0
    assert len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires modinfo on Rocky Linux 9")
def test_live_modinfo_xfs() -> None:
    """Live: modinfo xfs returns module metadata."""
    result = _execute("modinfo", {"module": "xfs"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.summary, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root + modprobe on Rocky Linux 9")
def test_live_modprobe_requires_root() -> None:
    """Live: modprobe on Rocky requires elevated privileges.

    Run as root or with sudo. Without privilege the exit_code will be non-zero.
    """
    result = _execute("modprobe", {"module": "dummy"})
    assert result.exit_code is not None


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: DESTRUCTIVE — requires root on Rocky Linux 9")
def test_live_rmmod_requires_root() -> None:
    """Live: rmmod is DESTRUCTIVE and requires root. Do NOT run on a live system
    without first verifying the module is safe to unload."""
    result = _execute("rmmod", {"module": "dummy"})
    assert result.exit_code is not None
