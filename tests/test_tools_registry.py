"""Tests for the tool registry + uniform interface (core/tools/__init__.py).

These are pure unit tests — no subprocess execution, no model, no network,
no Linux required. Fully green on any host (including macOS dev host).

Coverage:
  * ToolResult structure and .ok property.
  * ArgSpec / OpSpec / ToolSpec descriptor construction.
  * ToolRegistry: register, duplicate-register guard, lookup, list_tools.
  * ToolRegistry.dispatch: round-trip through a stub tool.
  * ToolRegistry.dispatch: unknown tool -> KeyError.
  * ToolRegistry.dispatch: unknown op -> ValueError.
  * ToolRegistry.dispatch: missing required arg -> TypeError.
  * ToolRegistry.dispatch: wrong arg type -> TypeError.
  * ToolRegistry.permission_class_for: correct class returned; unknown -> None.
  * run_subprocess: command-not-found -> ToolResult with exit_code 127.
  * run_subprocess: timeout -> ToolResult with exit_code 124.
  * Stub tool full round-trip: register -> dispatch -> ToolResult with audit
    fields populated correctly.
  * Module-level `registry` singleton is a ToolRegistry instance.
"""

from __future__ import annotations

import sys
import time
from typing import Any
from unittest.mock import patch

import pytest

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolRegistry,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _noop_execute(op: str, args: dict[str, Any]) -> ToolResult:
    """A stub execute function that echoes its inputs back in the summary."""
    return ToolResult(
        exit_code=0,
        stdout=f"op={op}",
        stderr="",
        summary=f"stub executed op={op} args={args}",
    )


def _make_echo_tool(name: str = "echo") -> ToolSpec:
    """Build a minimal stub tool with one read op and one write op."""
    return ToolSpec(
        name=name,
        description="Stub echo tool for tests",
        ops={
            "ping": OpSpec(
                op_name="ping",
                permission_class=OpClass.READ,
                args=[],
                description="A no-arg read op",
            ),
            "set_value": OpSpec(
                op_name="set_value",
                permission_class=OpClass.WRITE,
                args=[
                    ArgSpec(name="key", type=str, required=True, description="key"),
                    ArgSpec(name="value", type=str, required=True, description="val"),
                    ArgSpec(name="ttl", type=int, required=False, description="ttl", default=60),
                ],
                description="A write op with required and optional args",
            ),
        },
        execute=_noop_execute,
    )


@pytest.fixture()
def reg() -> ToolRegistry:
    """Return a FRESH registry (not the module-level singleton) for each test."""
    return ToolRegistry()


@pytest.fixture()
def reg_with_echo(reg: ToolRegistry) -> ToolRegistry:
    reg.register(_make_echo_tool())
    return reg


# ---------------------------------------------------------------------------
# ToolResult
# ---------------------------------------------------------------------------

class TestToolResult:
    def test_ok_true_on_zero_exit(self) -> None:
        r = ToolResult(exit_code=0, stdout="hello", stderr="", summary="done")
        assert r.ok is True

    def test_ok_false_on_nonzero_exit(self) -> None:
        r = ToolResult(exit_code=1, stdout="", stderr="err", summary="failed")
        assert r.ok is False

    def test_ok_false_on_none_exit(self) -> None:
        r = ToolResult(exit_code=None, stdout="", stderr="", summary="skipped")
        assert r.ok is False

    def test_as_dict_keys(self) -> None:
        r = ToolResult(exit_code=0, stdout="a", stderr="b", summary="c")
        d = r.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}
        assert d["exit_code"] == 0
        assert d["stdout"] == "a"
        assert d["stderr"] == "b"
        assert d["summary"] == "c"

    def test_frozen(self) -> None:
        r = ToolResult(exit_code=0, stdout="", stderr="", summary="")
        with pytest.raises((AttributeError, TypeError)):
            r.exit_code = 1  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ToolRegistry — registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_register_and_list(self, reg: ToolRegistry) -> None:
        reg.register(_make_echo_tool("alpha"))
        reg.register(_make_echo_tool("beta"))
        assert reg.list_tools() == ["alpha", "beta"]

    def test_list_sorted(self, reg: ToolRegistry) -> None:
        reg.register(_make_echo_tool("z_tool"))
        reg.register(_make_echo_tool("a_tool"))
        assert reg.list_tools() == ["a_tool", "z_tool"]

    def test_duplicate_raises(self, reg: ToolRegistry) -> None:
        reg.register(_make_echo_tool("dup"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(_make_echo_tool("dup"))

    def test_get_registered(self, reg_with_echo: ToolRegistry) -> None:
        spec = reg_with_echo.get("echo")
        assert spec is not None
        assert spec.name == "echo"

    def test_get_missing_returns_none(self, reg: ToolRegistry) -> None:
        assert reg.get("nonexistent") is None

    def test_unregister(self, reg_with_echo: ToolRegistry) -> None:
        reg_with_echo.unregister("echo")
        assert reg_with_echo.get("echo") is None
        assert "echo" not in reg_with_echo.list_tools()

    def test_unregister_missing_raises(self, reg: ToolRegistry) -> None:
        with pytest.raises(KeyError):
            reg.unregister("ghost")


# ---------------------------------------------------------------------------
# ToolRegistry — permission_class_for
# ---------------------------------------------------------------------------

class TestPermissionClass:
    def test_known_read_op(self, reg_with_echo: ToolRegistry) -> None:
        cls = reg_with_echo.permission_class_for("echo", "ping")
        assert cls is OpClass.READ

    def test_known_write_op(self, reg_with_echo: ToolRegistry) -> None:
        cls = reg_with_echo.permission_class_for("echo", "set_value")
        assert cls is OpClass.WRITE

    def test_unknown_tool_returns_none(self, reg: ToolRegistry) -> None:
        assert reg.permission_class_for("ghost", "ping") is None

    def test_unknown_op_returns_none(self, reg_with_echo: ToolRegistry) -> None:
        assert reg_with_echo.permission_class_for("echo", "nonexistent_op") is None

    def test_tool_spec_permission_class_for(self) -> None:
        spec = _make_echo_tool()
        assert spec.permission_class_for("ping") is OpClass.READ
        assert spec.permission_class_for("set_value") is OpClass.WRITE
        assert spec.permission_class_for("__missing__") is None


# ---------------------------------------------------------------------------
# ToolRegistry — dispatch (the core round-trip)
# ---------------------------------------------------------------------------

class TestDispatch:
    def test_read_op_round_trip(self, reg_with_echo: ToolRegistry) -> None:
        result = reg_with_echo.dispatch("echo", "ping", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0
        assert result.ok is True
        assert "ping" in result.summary

    def test_write_op_with_args(self, reg_with_echo: ToolRegistry) -> None:
        result = reg_with_echo.dispatch(
            "echo", "set_value", {"key": "colour", "value": "blue"}
        )
        assert result.exit_code == 0
        assert "set_value" in result.summary
        assert "colour" in result.summary or "colour" in result.stdout

    def test_write_op_with_optional_arg(self, reg_with_echo: ToolRegistry) -> None:
        result = reg_with_echo.dispatch(
            "echo", "set_value", {"key": "x", "value": "y", "ttl": 120}
        )
        assert result.ok

    def test_unknown_tool_raises_key_error(self, reg: ToolRegistry) -> None:
        with pytest.raises(KeyError, match="ghost"):
            reg.dispatch("ghost", "ping", {})

    def test_unknown_op_raises_value_error(self, reg_with_echo: ToolRegistry) -> None:
        with pytest.raises(ValueError, match="no operation"):
            reg_with_echo.dispatch("echo", "nonexistent", {})

    def test_missing_required_arg_raises_type_error(
        self, reg_with_echo: ToolRegistry
    ) -> None:
        with pytest.raises(TypeError, match="requires argument 'key'"):
            reg_with_echo.dispatch("echo", "set_value", {"value": "v"})

    def test_wrong_arg_type_raises_type_error(
        self, reg_with_echo: ToolRegistry
    ) -> None:
        with pytest.raises(TypeError, match="must be int"):
            reg_with_echo.dispatch(
                "echo", "set_value", {"key": "k", "value": "v", "ttl": "oops"}
            )

    def test_extra_args_are_silently_accepted(
        self, reg_with_echo: ToolRegistry
    ) -> None:
        # Forward-compat: unknown extra keys do not raise.
        result = reg_with_echo.dispatch(
            "echo", "ping", {"future_field": "ignored"}
        )
        assert result.ok


# ---------------------------------------------------------------------------
# Full round-trip: stub tool with destructive op + audit field check
# ---------------------------------------------------------------------------

class TestFullRoundTrip:
    """Simulate the exact lifecycle a Phase 4 router would follow.

    1. Build a ToolSpec with a DESTRUCTIVE op.
    2. Register it.
    3. Look up the permission class (would drive the gate prompt in Phase 4).
    4. Dispatch (pretending the gate was cleared).
    5. Verify ToolResult fields are suitable for audit.write().
    """

    def test_destructive_op_workflow(self, reg: ToolRegistry) -> None:
        calls: list[dict[str, Any]] = []

        def _execute(op: str, args: dict[str, Any]) -> ToolResult:
            calls.append({"op": op, "args": dict(args)})
            return ToolResult(
                exit_code=0,
                stdout="unit wiped",
                stderr="",
                summary=f"masked {args.get('unit', '?')} successfully",
            )

        mask_spec = ToolSpec(
            name="systemd_ctrl",
            description="Stub systemd control for tests",
            ops={
                "mask": OpSpec(
                    op_name="mask",
                    permission_class=OpClass.DESTRUCTIVE,
                    args=[ArgSpec(name="unit", type=str, required=True)],
                    description="Mask a systemd unit",
                ),
            },
            execute=_execute,
        )
        reg.register(mask_spec)

        # Step 1: router looks up the permission class before prompting user.
        cls = reg.permission_class_for("systemd_ctrl", "mask")
        assert cls is OpClass.DESTRUCTIVE

        # Step 2: (in production) permissions.classify() + gate resolution
        #         happens here. We skip it in the unit test — the registry
        #         trusts the caller has done it.

        # Step 3: dispatch (gate assumed cleared).
        result = reg.dispatch("systemd_ctrl", "mask", {"unit": "crond"})

        # Step 4: verify ToolResult fields are audit-ready.
        assert result.exit_code == 0
        assert result.ok is True
        assert "crond" in result.summary
        assert result.stdout == "unit wiped"
        assert result.stderr == ""
        assert "summary" in result.as_dict()

        # Confirm execute was called exactly once with correct args.
        assert len(calls) == 1
        assert calls[0] == {"op": "mask", "args": {"unit": "crond"}}


# ---------------------------------------------------------------------------
# run_subprocess — mocked to avoid real subprocesses in CI
# ---------------------------------------------------------------------------

class TestRunSubprocess:
    def test_success(self) -> None:
        import subprocess as sp

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = sp.CompletedProcess(
                args=["true"], returncode=0, stdout="hello\n", stderr=""
            )
            result = run_subprocess(["true"])

        assert result.exit_code == 0
        assert result.ok is True
        assert result.stdout == "hello\n"
        assert result.stderr == ""
        assert "successfully" in result.summary

    def test_nonzero_exit(self) -> None:
        import subprocess as sp

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = sp.CompletedProcess(
                args=["false"], returncode=1, stdout="", stderr="error"
            )
            result = run_subprocess(["false"])

        assert result.exit_code == 1
        assert result.ok is False
        assert "exited 1" in result.summary

    def test_timeout(self) -> None:
        import subprocess as sp

        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="sleep", timeout=1)):
            result = run_subprocess(["sleep", "999"], timeout=1)

        assert result.exit_code == 124
        assert "timed out" in result.summary

    def test_command_not_found(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError("not found")):
            result = run_subprocess(["__no_such_cmd__"])

        assert result.exit_code == 127
        assert "not found" in result.summary

    def test_os_error(self) -> None:
        with patch("subprocess.run", side_effect=OSError("permission denied")):
            result = run_subprocess(["/dev/null"])

        assert result.exit_code == 1
        assert "OS error" in result.summary


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

class TestModuleLevelRegistry:
    def test_registry_is_tool_registry_instance(self) -> None:
        assert isinstance(registry, ToolRegistry)

    def test_registry_is_importable_from_core_tools(self) -> None:
        # Verify the import path works; the registry object should exist.
        from core.tools import registry as r
        assert r is not None
