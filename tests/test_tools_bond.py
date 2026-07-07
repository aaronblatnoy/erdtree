"""tests/test_tools_bond.py — Unit tests for core/tools/bond.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without nmcli present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: show=READ; add/modify=WRITE; remove=DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (nonzero) → ok=False, failure summary naming the bond +
    exit code.
  * Command vectors: the exact argv list passed to run_subprocess for
    each operation.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC text.
  * I2 invariant: no AI/LLM/model/agent language in any summary.
  * I9 invariant: execute() NEVER raises — unknown op and missing binary
    (exit 127) both return a well-formed ToolResult.
  * DEFERRED-TO-MOSSAD: live execution against real nmcli on Rocky Linux 9.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.bond  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.bond import BOND_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch run_subprocess in the bond module's namespace."""
    return patch("core.tools.bond.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_bond_registered(self) -> None:
        assert registry.get("bond") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("bond")
        assert spec is not None
        assert spec.name == "bond"

    def test_all_ops_present(self) -> None:
        spec = registry.get("bond")
        assert spec is not None
        assert set(spec.ops.keys()) == {"show", "add", "modify", "remove"}


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    def test_show_is_read(self) -> None:
        cls = registry.permission_class_for("bond", "show")
        assert cls is OpClass.READ

    @pytest.mark.parametrize("op", ["add", "modify"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("bond", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_remove_is_destructive(self) -> None:
        cls = registry.permission_class_for("bond", "remove")
        assert cls is OpClass.DESTRUCTIVE

    def test_spec_permission_class_for(self) -> None:
        assert BOND_SPEC.permission_class_for("show") is OpClass.READ
        assert BOND_SPEC.permission_class_for("remove") is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors — assert the exact argv list passed to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_show_no_bond_arg(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="NAME UUID TYPE DEVICE\n"))
        with patch("core.tools.bond.run_subprocess", mock_fn):
            _execute("show", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "connection", "show"]

    def test_show_with_bond_arg(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="connection.id: bond0\n"))
        with patch("core.tools.bond.run_subprocess", mock_fn):
            _execute("show", {"bond": "bond0"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "connection", "show", "bond0"]

    def test_add_default_mode(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Connection 'bond0' (uuid) successfully added.\n"))
        with patch("core.tools.bond.run_subprocess", mock_fn):
            _execute("add", {"bond": "bond0"})
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "nmcli", "connection", "add",
            "type", "bond",
            "con-name", "bond0",
            "ifname", "bond0",
            "bond.options", "mode=active-backup",
        ]

    def test_add_custom_mode(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Connection 'bond1' (uuid) successfully added.\n"))
        with patch("core.tools.bond.run_subprocess", mock_fn):
            _execute("add", {"bond": "bond1", "mode": "802.3ad"})
        argv = mock_fn.call_args[0][0]
        assert argv[argv.index("bond.options") + 1] == "mode=802.3ad"
        assert "bond1" in argv

    def test_modify_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.bond.run_subprocess", mock_fn):
            _execute("modify", {"bond": "bond0", "property": "bond.options", "value": "mode=802.3ad"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "connection", "modify", "bond0", "bond.options", "mode=802.3ad"]

    def test_remove_command_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Connection 'bond0' successfully deleted.\n"))
        with patch("core.tools.bond.run_subprocess", mock_fn):
            _execute("remove", {"bond": "bond0"})
        argv = mock_fn.call_args[0][0]
        # DESTRUCTIVE: must contain 'connection' 'delete' and the bond name
        assert argv == ["nmcli", "connection", "delete", "bond0"]

    def test_remove_argv_shape_has_delete_verb(self) -> None:
        """The destructive argv shape nmcli connection delete must appear verbatim."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.bond.run_subprocess", mock_fn):
            _execute("remove", {"bond": "bond1"})
        argv = mock_fn.call_args[0][0]
        assert "delete" in argv
        assert "bond1" in argv


# ---------------------------------------------------------------------------
# Exit-code mapping and summary content
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_show_success(self) -> None:
        with _patch(_ok(stdout="bond0 ... bond ...\n")):
            result = _execute("show", {"bond": "bond0"})
        assert result.ok
        assert "bond0" in result.summary

    def test_show_failure(self) -> None:
        with _patch(_fail(exit_code=10, stderr="No such connection 'bond9'")):
            result = _execute("show", {"bond": "bond9"})
        assert not result.ok
        assert result.exit_code == 10
        assert "bond9" in result.summary

    def test_add_success(self) -> None:
        with _patch(_ok(stdout="Connection 'bond0' successfully added.\n")):
            result = _execute("add", {"bond": "bond0"})
        assert result.ok
        assert "bond0" in result.summary
        assert "created" in result.summary.lower()

    def test_add_failure(self) -> None:
        with _patch(_fail(exit_code=2, stderr="invalid bond interface name")):
            result = _execute("add", {"bond": "bad bond"})
        assert not result.ok
        assert result.exit_code == 2
        assert "bad bond" in result.summary

    def test_modify_success(self) -> None:
        with _patch(_ok()):
            result = _execute("modify", {"bond": "bond0", "property": "bond.options", "value": "mode=802.3ad"})
        assert result.ok
        assert "bond0" in result.summary
        assert "updated" in result.summary.lower() or "802.3ad" in result.summary

    def test_modify_failure(self) -> None:
        with _patch(_fail(exit_code=10, stderr="No such connection 'ghost'")):
            result = _execute("modify", {"bond": "ghost", "property": "bond.options", "value": "mode=802.3ad"})
        assert not result.ok
        assert "ghost" in result.summary

    def test_remove_success(self) -> None:
        with _patch(_ok(stdout="Connection 'bond0' successfully deleted.\n")):
            result = _execute("remove", {"bond": "bond0"})
        assert result.ok
        assert "bond0" in result.summary
        assert "deleted" in result.summary.lower()

    def test_remove_failure(self) -> None:
        with _patch(_fail(exit_code=10, stderr="No such connection 'bond99'")):
            result = _execute("remove", {"bond": "bond99"})
        assert not result.ok
        assert "bond99" in result.summary

    def test_show_all_success_summary(self) -> None:
        with _patch(_ok(stdout="NAME UUID TYPE DEVICE\nbond0 ... bond bond0\n")):
            result = _execute("show", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_add_mode_appears_in_summary(self) -> None:
        with _patch(_ok()):
            result = _execute("add", {"bond": "bond0", "mode": "802.3ad"})
        assert "802.3ad" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("show",   {}),
        ("show",   {"bond": "bond0"}),
        ("add",    {"bond": "bond0"}),
        ("add",    {"bond": "bond0", "mode": "802.3ad"}),
        ("modify", {"bond": "bond0", "property": "bond.options", "value": "mode=802.3ad"}),
        ("remove", {"bond": "bond0"}),
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
        ("show",   {"bond": "bond0"}),
        ("add",    {"bond": "bond0"}),
        ("modify", {"bond": "bond0", "property": "p", "value": "v"}),
        ("remove", {"bond": "bond0"}),
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
    AVC_STDERR = (
        "Error: nmcli: AVC avc: denied { write } for pid=4321 "
        "comm=\"nmcli\" name=\"bond0\" dev=sda1"
    )

    @pytest.mark.parametrize("op,args", [
        ("show",   {"bond": "bond0"}),
        ("add",    {"bond": "bond0"}),
        ("modify", {"bond": "bond0", "property": "bond.options", "value": "mode=802.3ad"}),
        ("remove", {"bond": "bond0"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self.AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op='{op}': {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("show",   {"bond": "bond0"}),
        ("add",    {"bond": "bond0"}),
        ("modify", {"bond": "bond0", "property": "bond.options", "value": "v"}),
        ("remove", {"bond": "bond0"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="Error: connection not found.")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary
        assert "AVC" not in result.summary


# ---------------------------------------------------------------------------
# I2 — no AI/LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("show",   {}),
        ("show",   {"bond": "bond0"}),
        ("add",    {"bond": "bond0"}),
        ("add",    {"bond": "bond0", "mode": "802.3ad"}),
        ("modify", {"bond": "bond0", "property": "bond.options", "value": "mode=802.3ad"}),
        ("remove", {"bond": "bond0"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("show",   {"bond": "bond0"}),
        ("add",    {"bond": "bond0"}),
        ("modify", {"bond": "bond0", "property": "p", "value": "v"}),
        ("remove", {"bond": "bond0"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestI9NeverRaises:
    def test_unknown_op_returns_well_formed_result(self) -> None:
        result = _execute("nonexistent_op", {"bond": "bond0"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        assert "nonexistent_op" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        """Simulate nmcli not installed — run_subprocess returns exit 127."""
        mock_result = ToolResult(
            exit_code=127,
            stdout="",
            stderr="bash: nmcli: command not found",
            summary="",
        )
        with patch("core.tools.bond.run_subprocess", return_value=mock_result):
            result = _execute("show", {"bond": "bond0"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("show",   {"bond": "bond0"}),
        ("add",    {"bond": "bond0"}),
        ("modify", {"bond": "bond0", "property": "bond.options", "value": "mode=802.3ad"}),
        ("remove", {"bond": "bond0"}),
    ])
    def test_nonzero_exit_never_raises(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="generic error")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_show(self) -> None:
        with _patch(_ok(stdout="bond0 uuid bond bond0")):
            result = registry.dispatch("bond", "show", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_add(self) -> None:
        with _patch(_ok(stdout="Connection 'bond0' successfully added.")):
            result = registry.dispatch("bond", "add", {"bond": "bond0"})
        assert result.ok

    def test_dispatch_remove(self) -> None:
        with _patch(_ok(stdout="Connection 'bond0' successfully deleted.")):
            result = registry.dispatch("bond", "remove", {"bond": "bond0"})
        assert result.ok

    def test_dispatch_add_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'bond'"):
            registry.dispatch("bond", "add", {})

    def test_dispatch_modify_missing_required_arg_raises(self) -> None:
        # 'property' and 'value' are required
        with pytest.raises(TypeError):
            registry.dispatch("bond", "modify", {"bond": "bond0"})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("bond", "bogus_op", {"bond": "bond0"})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nmcli on Rocky Linux 9")
def test_live_show_all() -> None:
    """Live: nmcli connection show returns a populated connection list."""
    result = _execute("show", {})
    assert result.exit_code == 0
    assert len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nmcli on Rocky Linux 9")
def test_live_show_bond0() -> None:
    """Live: nmcli connection show bond0 returns bond profile details."""
    result = _execute("show", {"bond": "bond0"})
    assert result.exit_code in (0, 10)  # 0=found, 10=not found
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nmcli + root on Rocky Linux 9")
def test_live_add_requires_root() -> None:
    """Live: nmcli connection add requires elevated privileges."""
    result = _execute("add", {"bond": "test-bond-tmp"})
    assert result.exit_code is not None
