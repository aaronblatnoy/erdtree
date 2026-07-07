"""tests/test_tools_lvm.py — Unit tests for core/tools/lvm.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without any lvm2 binaries present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: pvdisplay/vgdisplay/lvdisplay are READ;
    pvcreate/vgcreate/lvcreate/lvextend/vgextend are WRITE;
    pvremove/vgremove/lvremove/lvreduce are DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code=1) -> ok=False, failure summary naming the object.
  * Command vectors: argv lists are exactly as expected per the tool spec.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises (I9): unknown op and missing binary (exit 127) both
    return well-formed ToolResult, no exception.
  * I2: no AI/LLM/model/agent language in any summary.
  * ToolResult.as_dict() yields exactly the four required keys.
  * DEFERRED-TO-MOSSAD: live execution against real lvm2 on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.lvm.run_subprocess`` (the function bound in the lvm
  module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration into the module-level registry.
import core.tools.lvm  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.lvm import LVM_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.lvm.run_subprocess."""
    return patch("core.tools.lvm.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_lvm_registered(self) -> None:
        assert registry.get("lvm") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("lvm")
        assert spec is not None
        assert spec.name == "lvm"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("lvm")
        assert spec is not None
        expected = {
            "pvdisplay", "vgdisplay", "lvdisplay",
            "pvcreate", "vgcreate", "lvcreate", "lvextend", "vgextend",
            "pvremove", "vgremove", "lvremove", "lvreduce",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["pvdisplay", "vgdisplay", "lvdisplay"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("lvm", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["pvcreate", "vgcreate", "lvcreate", "lvextend", "vgextend"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("lvm", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["pvremove", "vgremove", "lvremove", "lvreduce"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("lvm", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_pvdisplay_no_arg(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("pvdisplay", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["pvdisplay"]

    def test_pvdisplay_with_pv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("pvdisplay", {"pv": "/dev/sdb"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["pvdisplay", "/dev/sdb"]

    def test_vgdisplay_no_arg(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("vgdisplay", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["vgdisplay"]

    def test_vgdisplay_with_vg(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("vgdisplay", {"vg": "vg_data"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["vgdisplay", "vg_data"]

    def test_lvdisplay_no_arg(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("lvdisplay", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["lvdisplay"]

    def test_lvdisplay_with_lv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("lvdisplay", {"lv": "/dev/vg_data/lv_home"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["lvdisplay", "/dev/vg_data/lv_home"]

    def test_pvcreate_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("pvcreate", {"pv": "/dev/sdc"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["pvcreate", "/dev/sdc"]

    def test_vgcreate_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("vgcreate", {"vg": "vg_data", "pv": "/dev/sdb"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["vgcreate", "vg_data", "/dev/sdb"]

    def test_lvcreate_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("lvcreate", {"lv_name": "lv_home", "vg": "vg_data", "size": "10G"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["lvcreate", "-L", "10G", "-n", "lv_home", "vg_data"]

    def test_lvextend_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("lvextend", {"lv": "/dev/vg_data/lv_home", "size": "+5G"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["lvextend", "-L", "+5G", "/dev/vg_data/lv_home"]

    def test_vgextend_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("vgextend", {"vg": "vg_data", "pv": "/dev/sdc"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["vgextend", "vg_data", "/dev/sdc"]

    def test_pvremove_argv(self) -> None:
        """pvremove argv must use the real binary name so the classifier sees it."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("pvremove", {"pv": "/dev/sdb"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["pvremove", "/dev/sdb"]
        assert argv[0] == "pvremove"

    def test_vgremove_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("vgremove", {"vg": "vg_data"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["vgremove", "vg_data"]
        assert argv[0] == "vgremove"

    def test_lvremove_argv_includes_force_flag(self) -> None:
        """lvremove must include -f so the real destructive shape is visible."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("lvremove", {"lv": "/dev/vg_data/lv_home"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["lvremove", "-f", "/dev/vg_data/lv_home"]
        assert argv[0] == "lvremove"
        assert "-f" in argv

    def test_lvreduce_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.lvm.run_subprocess", mock_fn):
            _execute("lvreduce", {"lv": "/dev/vg_data/lv_home", "size": "5G"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["lvreduce", "-L", "5G", "/dev/vg_data/lv_home"]
        assert argv[0] == "lvreduce"


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("pvdisplay", {}),
        ("vgdisplay", {"vg": "vg_data"}),
        ("lvdisplay", {"lv": "/dev/vg_data/lv_home"}),
        ("pvcreate",  {"pv": "/dev/sdb"}),
        ("vgcreate",  {"vg": "vg_data", "pv": "/dev/sdb"}),
        ("lvcreate",  {"lv_name": "lv_home", "vg": "vg_data", "size": "10G"}),
        ("lvextend",  {"lv": "/dev/vg_data/lv_home", "size": "+5G"}),
        ("vgextend",  {"vg": "vg_data", "pv": "/dev/sdc"}),
        ("pvremove",  {"pv": "/dev/sdb"}),
        ("vgremove",  {"vg": "vg_data"}),
        ("lvremove",  {"lv": "/dev/vg_data/lv_home"}),
        ("lvreduce",  {"lv": "/dev/vg_data/lv_home", "size": "5G"}),
    ])
    def test_success_ok_true(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("pvdisplay", {"pv": "/dev/sdb"}),
        ("vgdisplay", {"vg": "vg_data"}),
        ("pvcreate",  {"pv": "/dev/sdb"}),
        ("vgcreate",  {"vg": "vg_data", "pv": "/dev/sdb"}),
        ("lvcreate",  {"lv_name": "lv_home", "vg": "vg_data", "size": "10G"}),
        ("pvremove",  {"pv": "/dev/sdb"}),
        ("vgremove",  {"vg": "vg_data"}),
        ("lvremove",  {"lv": "/dev/vg_data/lv_home"}),
        ("lvreduce",  {"lv": "/dev/vg_data/lv_home", "size": "5G"}),
    ])
    def test_failure_ok_false(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=5, stderr="object not found")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 5

    def test_failure_summary_names_object_pvremove(self) -> None:
        with _patch(_fail(exit_code=1, stderr="PV not found")):
            result = _execute("pvremove", {"pv": "/dev/sdb"})
        assert "/dev/sdb" in result.summary

    def test_failure_summary_names_object_vgremove(self) -> None:
        with _patch(_fail(exit_code=1, stderr="VG not found")):
            result = _execute("vgremove", {"vg": "vg_data"})
        assert "vg_data" in result.summary

    def test_failure_summary_names_object_lvremove(self) -> None:
        with _patch(_fail(exit_code=1, stderr="LV not found")):
            result = _execute("lvremove", {"lv": "/dev/vg_data/lv_home"})
        assert "/dev/vg_data/lv_home" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        with _patch(_fail(exit_code=127, stderr="command not found")):
            result = _execute("pvdisplay", {})
        assert not result.ok
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("pvdisplay", {}),
        ("vgdisplay", {}),
        ("lvdisplay", {}),
        ("pvcreate",  {"pv": "/dev/sdb"}),
        ("vgcreate",  {"vg": "vg_data", "pv": "/dev/sdb"}),
        ("lvcreate",  {"lv_name": "lv_home", "vg": "vg_data", "size": "10G"}),
        ("lvextend",  {"lv": "/dev/vg_data/lv_home", "size": "+5G"}),
        ("vgextend",  {"vg": "vg_data", "pv": "/dev/sdc"}),
        ("pvremove",  {"pv": "/dev/sdb"}),
        ("vgremove",  {"vg": "vg_data"}),
        ("lvremove",  {"lv": "/dev/vg_data/lv_home"}),
        ("lvreduce",  {"lv": "/dev/vg_data/lv_home", "size": "5G"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("pvdisplay", {}),
        ("pvremove",  {"pv": "/dev/sdb"}),
        ("lvreduce",  {"lv": "/dev/vg_data/lv_home", "size": "5G"}),
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
    @pytest.mark.parametrize("op,args", [
        ("pvdisplay", {}),
        ("pvcreate",  {"pv": "/dev/sdb"}),
        ("vgcreate",  {"vg": "vg_data", "pv": "/dev/sdb"}),
        ("lvcreate",  {"lv_name": "lv_home", "vg": "vg_data", "size": "10G"}),
        ("pvremove",  {"pv": "/dev/sdb"}),
        ("lvremove",  {"lv": "/dev/vg_data/lv_home"}),
        ("lvreduce",  {"lv": "/dev/vg_data/lv_home", "size": "5G"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { open } for pid=4321 "
            "comm=\"pvremove\" name=\"sdb\" scontext=system_u:system_r:lvm_t:s0"
        )
        with _patch(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op={op!r}: {result.summary!r}"

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Volume group not found.")):
            result = _execute("vgdisplay", {"vg": "missing_vg"})
        assert "ausearch" not in result.summary
        assert "SELinux may be" not in result.summary

    def test_selinux_keyword_in_stderr(self) -> None:
        with _patch(_fail(exit_code=1, stderr="selinux policy prevented access")):
            result = _execute("lvremove", {"lv": "/dev/vg_data/lv_home"})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# I2: No AI/LLM language in summaries
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("pvdisplay", {}),
        ("vgdisplay", {}),
        ("lvdisplay", {}),
        ("pvcreate",  {"pv": "/dev/sdb"}),
        ("vgcreate",  {"vg": "vg_data", "pv": "/dev/sdb"}),
        ("lvcreate",  {"lv_name": "lv_home", "vg": "vg_data", "size": "10G"}),
        ("lvextend",  {"lv": "/dev/vg_data/lv_home", "size": "+5G"}),
        ("vgextend",  {"vg": "vg_data", "pv": "/dev/sdc"}),
        ("pvremove",  {"pv": "/dev/sdb"}),
        ("vgremove",  {"vg": "vg_data"}),
        ("lvremove",  {"lv": "/dev/vg_data/lv_home"}),
        ("lvreduce",  {"lv": "/dev/vg_data/lv_home", "size": "5G"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op={op!r}: {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("pvremove",  {"pv": "/dev/sdb"}),
        ("vgremove",  {"vg": "vg_data"}),
        ("lvremove",  {"lv": "/dev/vg_data/lv_home"}),
        ("lvreduce",  {"lv": "/dev/vg_data/lv_home", "size": "5G"}),
        ("pvcreate",  {"pv": "/dev/sdb"}),
        ("lvcreate",  {"lv_name": "lv_home", "vg": "vg_data", "size": "10G"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op={op!r}: {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# I9: execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("completely_unknown_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_no_raise(self) -> None:
        with _patch(_fail(exit_code=127, stderr="command not found: pvremove")):
            result = _execute("pvremove", {"pv": "/dev/sdb"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_empty_args_optional_display_ops_no_raise(self) -> None:
        """Display ops with optional args must not raise when args is {}."""
        for op in ("pvdisplay", "vgdisplay", "lvdisplay"):
            with _patch(_ok()):
                result = _execute(op, {})
            assert isinstance(result, ToolResult)
            assert result.exit_code == 0

    def test_timeout_exit_124_no_raise(self) -> None:
        with _patch(_fail(exit_code=124, stderr="timeout")):
            result = _execute("vgdisplay", {"vg": "vg_data"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_pvdisplay(self) -> None:
        with _patch(_ok(stdout="PV info")):
            result = registry.dispatch("lvm", "pvdisplay", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_lvremove(self) -> None:
        with _patch(_ok()):
            result = registry.dispatch("lvm", "lvremove", {"lv": "/dev/vg_data/lv_home"})
        assert result.ok

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("lvm", "nonexistent_op", {})

    def test_dispatch_lvcreate_missing_required_arg_raises(self) -> None:
        # lv_name, vg, and size are all required — omitting them should raise
        with pytest.raises(TypeError):
            registry.dispatch("lvm", "lvcreate", {})

    def test_lvm_spec_permission_class_for(self) -> None:
        assert LVM_SPEC.permission_class_for("pvremove") is OpClass.DESTRUCTIVE
        assert LVM_SPEC.permission_class_for("pvcreate") is OpClass.WRITE
        assert LVM_SPEC.permission_class_for("lvdisplay") is OpClass.READ


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real lvm2 on Rocky Linux 9")
def test_live_pvdisplay() -> None:
    """Live: pvdisplay returns a populated ToolResult."""
    result = _execute("pvdisplay", {})
    assert result.exit_code in (0, 5)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real lvm2 on Rocky Linux 9")
def test_live_vgdisplay() -> None:
    """Live: vgdisplay returns attributes for all VGs."""
    result = _execute("vgdisplay", {})
    assert result.exit_code == 0
    assert "VG Name" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires root + lvm2 on Rocky Linux 9")
def test_live_pvcreate_requires_root() -> None:
    """Live: pvcreate on a real device requires root; without it returns non-zero."""
    result = _execute("pvcreate", {"pv": "/dev/sdb"})
    assert result.exit_code is not None
