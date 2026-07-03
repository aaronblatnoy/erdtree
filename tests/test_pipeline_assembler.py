"""
tests/test_pipeline_assembler.py — Convergence proof for the deterministic assembler.

Coverage
--------
1. Fully-slotted assemble() returns a ParsedCall with the same tool/operation/
   args/permission_class as the native path (Router.route).
2. CONVERGENCE PROOF: assembled ParsedCall, fed through synthesize_command +
   permissions.classify, yields the SAME Gate as the native ParsedCall for EVERY
   core tool op tested — including a destructive op (disk.format -> mkfs.ext4
   /dev/sdb -> DESTRUCTIVE -> CONFIRM_TYPED).
3. Missing required slot -> Unresolved with the slot name in `missing`.
4. ArgSpec.default is applied for absent non-required args.
5. Unknown tool -> Unresolved (missing=[], reason mentions tool name).
6. Unknown operation -> Unresolved (missing=[], reason mentions valid ops).
7. The assembler NEVER emits a shell string (A5).
8. Non-interactive destructive -> REFUSE, proving the assembler does not
   under-state blast radius across execution contexts.

Invariants under test
---------------------
I3  permissions.classify is THE single gate; the assembler merely constructs
    the ParsedCall shape — it never calls classify.
A1  ArgSpec.default applied for absent non-required args.
A5  assemble() returns ParsedCall, not a shell string.
"""

from __future__ import annotations

import json

import pytest

# Side-effect: register all core tools into the module-level registry.
import core.agent.main  # noqa: F401

from core.agent.permissions import ExecContext, Gate, OpClass, classify
from core.agent.pipeline.assembler import Unresolved, assemble
from core.agent.repl import synthesize_command
from core.agent.router import ParsedCall, Router
from core.tools import registry

INTERACTIVE = ExecContext(interactive=True)
NON_INTERACTIVE = ExecContext(interactive=False)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _native_call(tool: str, op: str, args_with_op: dict) -> ParsedCall:
    """Build a ParsedCall via Router.route — the native path reference."""
    router = Router(registry)
    raw = [
        {
            "id": "native-ref",
            "name": tool,
            "arguments": json.dumps(args_with_op),
        }
    ]
    verdict = router.route(tool_calls=raw)
    assert verdict.calls, (
        f"Native path produced no call for {tool}.{op} with {args_with_op}: "
        f"misses={verdict.misses}"
    )
    return verdict.calls[0]


def _gate(call: ParsedCall, ctx: ExecContext) -> Gate:
    """Synthesize the argv and run it through permissions.classify."""
    return classify(synthesize_command(call), ctx).gate


def _op_class(call: ParsedCall) -> OpClass:
    """Classify the synthesized argv (interactive context)."""
    return classify(synthesize_command(call), INTERACTIVE).op_class


# ---------------------------------------------------------------------------
# 1. Fully-slotted assemble() == native ParsedCall (fields, not call_id)
# ---------------------------------------------------------------------------

class TestAssembleMatchesNative:
    """Assembled ParsedCall has the same tool/op/args/permission_class as Router."""

    def _assert_matches(self, tool: str, op: str, slots: dict) -> None:
        result = assemble(tool, op, slots, registry)
        assert isinstance(result, ParsedCall), (
            f"Expected ParsedCall, got {result!r}"
        )
        native = _native_call(tool, op, {"operation": op, **slots})
        assert result.tool == native.tool, f"{tool}.{op}: tool mismatch"
        assert result.operation == native.operation, f"{tool}.{op}: op mismatch"
        # The assembler may include ADDITIONAL keys from ArgSpec.default (A1);
        # the native path only carries keys the caller supplied.  Assert that
        # every key the native path produced also appears in the assembled args
        # with the same value — assembled is a superset, not a different set.
        for key, val in native.args.items():
            assert result.args.get(key) == val, (
                f"{tool}.{op}: args[{key!r}] mismatch: "
                f"assembled={result.args.get(key)!r}, native={val!r}"
            )
        assert result.permission_class == native.permission_class, (
            f"{tool}.{op}: permission_class mismatch"
        )

    # --- services ---
    def test_services_status(self):
        self._assert_matches("services", "status", {"unit": "nginx.service"})

    def test_services_restart(self):
        self._assert_matches("services", "restart", {"unit": "sshd.service"})

    def test_services_start(self):
        self._assert_matches("services", "start", {"unit": "postgresql.service"})

    def test_services_stop(self):
        self._assert_matches("services", "stop", {"unit": "nginx.service"})

    def test_services_enable(self):
        self._assert_matches("services", "enable", {"unit": "nginx.service"})

    def test_services_disable(self):
        self._assert_matches("services", "disable", {"unit": "nginx.service"})

    def test_services_mask(self):
        self._assert_matches("services", "mask", {"unit": "cups.service"})

    # --- packages ---
    def test_packages_install(self):
        self._assert_matches("packages", "install", {"packages": ["htop"]})

    def test_packages_remove(self):
        self._assert_matches("packages", "remove", {"packages": ["curl"]})

    def test_packages_search(self):
        self._assert_matches("packages", "search", {"keyword": "redis"})

    def test_packages_info(self):
        self._assert_matches("packages", "info", {"package": "nginx"})

    # --- logs ---
    def test_logs_tail(self):
        self._assert_matches("logs", "tail", {"unit": "nginx.service"})

    # --- hardware ---
    def test_hardware_cpu(self):
        self._assert_matches("hardware", "cpu", {})

    def test_hardware_memory(self):
        self._assert_matches("hardware", "memory", {})

    def test_hardware_block(self):
        self._assert_matches("hardware", "block", {})

    # --- disk ---
    def test_disk_usage(self):
        self._assert_matches("disk", "usage", {})

    def test_disk_list(self):
        self._assert_matches("disk", "list", {})

    def test_disk_smart(self):
        self._assert_matches("disk", "smart", {"device": "/dev/sda"})

    def test_disk_mount(self):
        self._assert_matches(
            "disk", "mount", {"device": "/dev/sdb1", "mount_point": "/mnt/data"}
        )

    def test_disk_unmount(self):
        self._assert_matches("disk", "unmount", {"target": "/mnt/data"})

    def test_disk_format_with_fstype(self):
        self._assert_matches(
            "disk", "format", {"device": "/dev/sdb", "fstype": "ext4"}
        )

    def test_disk_wipe(self):
        self._assert_matches("disk", "wipe", {"device": "/dev/sdb"})

    # --- users ---
    def test_users_list(self):
        self._assert_matches("users", "list", {})

    def test_users_info(self):
        self._assert_matches("users", "info", {"user": "alice"})

    def test_users_add(self):
        self._assert_matches("users", "add", {"user": "bob"})

    def test_users_lock(self):
        self._assert_matches("users", "lock", {"user": "mallory"})

    def test_users_delete(self):
        self._assert_matches("users", "delete", {"user": "olduser"})

    # --- firewall ---
    def test_firewall_list(self):
        self._assert_matches("firewall", "list", {})

    def test_firewall_query(self):
        self._assert_matches("firewall", "query", {"service": "http"})

    def test_firewall_add_service(self):
        self._assert_matches("firewall", "add_service", {"service": "https"})

    def test_firewall_panic_on(self):
        self._assert_matches("firewall", "panic_on", {})

    # --- network ---
    def test_network_show(self):
        self._assert_matches("network", "show", {})

    def test_network_status(self):
        self._assert_matches("network", "status", {})


# ---------------------------------------------------------------------------
# 2. Convergence proof: synthesize_command + classify == same gate
# ---------------------------------------------------------------------------

class TestConvergenceProof:
    """CONVERGENCE: assembled ParsedCall through synthesize_command + classify
    yields the SAME Gate as the native path ParsedCall."""

    def _assert_gate_parity(
        self,
        tool: str,
        op: str,
        slots: dict,
        expected_class: OpClass,
        expected_gate_interactive: Gate,
    ) -> None:
        """Both assembled and native path must land on the same gate."""
        assembled = assemble(tool, op, slots, registry)
        assert isinstance(assembled, ParsedCall), (
            f"Expected ParsedCall for {tool}.{op}, got {assembled!r}"
        )
        native = _native_call(tool, op, {"operation": op, **slots})

        # Class match.
        assert _op_class(assembled) == expected_class, (
            f"{tool}.{op}: expected OpClass.{expected_class.name}, "
            f"got {_op_class(assembled).name}"
        )
        # Gate match — interactive.
        assert _gate(assembled, INTERACTIVE) == expected_gate_interactive, (
            f"{tool}.{op}: interactive gate mismatch"
        )
        # Assembled gate == native gate (the parity property).
        assert _gate(assembled, INTERACTIVE) == _gate(native, INTERACTIVE), (
            f"{tool}.{op}: assembled gate != native gate (interactive)"
        )

    # --- READ -> ALLOW ---

    def test_read_services_status(self):
        self._assert_gate_parity(
            "services", "status", {"unit": "nginx.service"},
            OpClass.READ, Gate.ALLOW,
        )

    def test_read_hardware_cpu(self):
        self._assert_gate_parity("hardware", "cpu", {}, OpClass.READ, Gate.ALLOW)

    def test_read_disk_list(self):
        self._assert_gate_parity("disk", "list", {}, OpClass.READ, Gate.ALLOW)

    def test_read_disk_usage(self):
        self._assert_gate_parity("disk", "usage", {}, OpClass.READ, Gate.ALLOW)

    def test_read_users_list(self):
        self._assert_gate_parity("users", "list", {}, OpClass.READ, Gate.ALLOW)

    def test_read_network_show(self):
        self._assert_gate_parity("network", "show", {}, OpClass.READ, Gate.ALLOW)

    def test_read_firewall_list(self):
        self._assert_gate_parity("firewall", "list", {}, OpClass.READ, Gate.ALLOW)

    # --- WRITE -> CONFIRM (interactive) ---

    def test_write_services_restart(self):
        self._assert_gate_parity(
            "services", "restart", {"unit": "nginx.service"},
            OpClass.WRITE, Gate.CONFIRM,
        )

    def test_write_services_start(self):
        self._assert_gate_parity(
            "services", "start", {"unit": "sshd.service"},
            OpClass.WRITE, Gate.CONFIRM,
        )

    def test_write_packages_install(self):
        self._assert_gate_parity(
            "packages", "install", {"packages": ["curl"]},
            OpClass.WRITE, Gate.CONFIRM,
        )

    def test_write_disk_mount(self):
        self._assert_gate_parity(
            "disk", "mount", {"device": "/dev/sdb1", "mount_point": "/mnt/data"},
            OpClass.WRITE, Gate.CONFIRM,
        )

    # --- DESTRUCTIVE -> CONFIRM_TYPED (interactive) ---

    def test_destructive_disk_format_confirms_typed(self):
        """THE keystone: disk.format -> mkfs.ext4 /dev/sdb -> DESTRUCTIVE ->
        CONFIRM_TYPED.  Proves the assembler does NOT under-state blast radius."""
        assembled = assemble(
            "disk", "format", {"device": "/dev/sdb", "fstype": "ext4"}, registry
        )
        assert isinstance(assembled, ParsedCall)
        native = _native_call(
            "disk", "format",
            {"operation": "format", "device": "/dev/sdb", "fstype": "ext4"},
        )

        # Both must be DESTRUCTIVE.
        assert _op_class(assembled) == OpClass.DESTRUCTIVE, (
            "disk.format assembled path must be DESTRUCTIVE"
        )
        assert _op_class(native) == OpClass.DESTRUCTIVE, (
            "disk.format native path must be DESTRUCTIVE"
        )

        # Both must require the human to type the confirm word (CONFIRM_TYPED).
        assert _gate(assembled, INTERACTIVE) == Gate.CONFIRM_TYPED, (
            "disk.format assembled: interactive gate must be CONFIRM_TYPED"
        )
        assert _gate(native, INTERACTIVE) == Gate.CONFIRM_TYPED, (
            "disk.format native: interactive gate must be CONFIRM_TYPED"
        )

        # Parity: assembled gate == native gate.
        assert _gate(assembled, INTERACTIVE) == _gate(native, INTERACTIVE)

    def test_destructive_non_interactive_refuses(self):
        """Non-interactive destructive -> REFUSE (assembler never auto-confirms)."""
        assembled = assemble(
            "disk", "format", {"device": "/dev/sdb", "fstype": "ext4"}, registry
        )
        assert isinstance(assembled, ParsedCall)
        assert _gate(assembled, NON_INTERACTIVE) == Gate.REFUSE, (
            "disk.format must REFUSE when no human is present (non-interactive)"
        )

    def test_destructive_disk_wipe(self):
        self._assert_gate_parity(
            "disk", "wipe", {"device": "/dev/sdb"},
            OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED,
        )

    def test_destructive_users_delete(self):
        self._assert_gate_parity(
            "users", "delete", {"user": "olduser"},
            OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED,
        )

    def test_destructive_users_lock(self):
        self._assert_gate_parity(
            "users", "lock", {"user": "mallory"},
            OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED,
        )

    def test_destructive_firewall_panic_on(self):
        self._assert_gate_parity(
            "firewall", "panic_on", {},
            OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED,
        )

    def test_destructive_packages_remove(self):
        """packages.remove -> dnf remove -> DESTRUCTIVE (cascade risk)."""
        self._assert_gate_parity(
            "packages", "remove", {"packages": ["sudo"]},
            OpClass.DESTRUCTIVE, Gate.CONFIRM_TYPED,
        )


# ---------------------------------------------------------------------------
# 3. Missing required slot -> Unresolved
# ---------------------------------------------------------------------------

class TestMissingRequiredSlot:
    """A required arg absent from slot_values must return Unresolved."""

    def test_services_status_missing_unit(self):
        result = assemble("services", "status", {}, registry)
        assert isinstance(result, Unresolved), "Expected Unresolved when 'unit' missing"
        assert "unit" in result.missing

    def test_services_restart_missing_unit(self):
        result = assemble("services", "restart", {}, registry)
        assert isinstance(result, Unresolved)
        assert "unit" in result.missing

    def test_disk_smart_missing_device(self):
        result = assemble("disk", "smart", {}, registry)
        assert isinstance(result, Unresolved)
        assert "device" in result.missing

    def test_disk_mount_missing_device_and_mount_point(self):
        result = assemble("disk", "mount", {}, registry)
        assert isinstance(result, Unresolved)
        # Both required args are missing.
        assert "device" in result.missing
        assert "mount_point" in result.missing

    def test_disk_mount_missing_one_required(self):
        result = assemble("disk", "mount", {"device": "/dev/sdb1"}, registry)
        assert isinstance(result, Unresolved)
        assert "mount_point" in result.missing
        assert "device" not in result.missing

    def test_disk_format_missing_device(self):
        """Required arg absent even for a destructive op -> Unresolved."""
        result = assemble("disk", "format", {}, registry)
        assert isinstance(result, Unresolved)
        assert "device" in result.missing

    def test_unresolved_reason_is_informative(self):
        """Reason string mentions the operation and missing slot (I2-clean)."""
        result = assemble("services", "status", {}, registry)
        assert isinstance(result, Unresolved)
        assert result.reason, "reason must be non-empty"
        # No AI/LLM/model/agent language (I2).
        for forbidden in ("AI", "LLM", "model", "agent"):
            assert forbidden.lower() not in result.reason.lower(), (
                f"I2 violation: reason contains {forbidden!r}"
            )


# ---------------------------------------------------------------------------
# 4. ArgSpec.default applied for absent non-required args
# ---------------------------------------------------------------------------

class TestDefaultApplied:
    """ArgSpec.default fills absent non-required slots before validation."""

    def test_disk_format_default_fstype(self):
        """disk.format: fstype is not required; default 'ext4' must be applied."""
        result = assemble("disk", "format", {"device": "/dev/sdb"}, registry)
        assert isinstance(result, ParsedCall), (
            f"Expected ParsedCall with default fstype, got {result!r}"
        )
        assert result.args.get("fstype") == "ext4", (
            "default fstype='ext4' must be present in assembled args"
        )

    def test_disk_dd_write_default_bs(self):
        """disk.dd_write: bs is not required; default '4M' must be applied."""
        result = assemble(
            "disk", "dd_write",
            {"source": "/path/to/image.iso", "device": "/dev/sdb"},
            registry,
        )
        assert isinstance(result, ParsedCall), (
            f"Expected ParsedCall with default bs, got {result!r}"
        )
        assert result.args.get("bs") == "4M", (
            "default bs='4M' must be present in assembled args"
        )

    def test_services_logs_default_lines(self):
        """services.logs: lines is not required; default 50 must be applied."""
        result = assemble(
            "services", "logs", {"unit": "nginx.service"}, registry
        )
        assert isinstance(result, ParsedCall), (
            f"Expected ParsedCall with default lines, got {result!r}"
        )
        assert result.args.get("lines") == 50, (
            "default lines=50 must be present in assembled args"
        )

    def test_explicit_value_overrides_default(self):
        """An explicitly supplied slot value takes precedence over ArgSpec.default."""
        result = assemble(
            "services", "logs",
            {"unit": "sshd.service", "lines": 200},
            registry,
        )
        assert isinstance(result, ParsedCall)
        assert result.args.get("lines") == 200, (
            "explicit lines=200 must override the default of 50"
        )

    def test_disk_format_explicit_fstype_overrides_default(self):
        result = assemble(
            "disk", "format",
            {"device": "/dev/nvme0n1", "fstype": "xfs"},
            registry,
        )
        assert isinstance(result, ParsedCall)
        assert result.args.get("fstype") == "xfs"


# ---------------------------------------------------------------------------
# 5. Unknown tool -> Unresolved
# ---------------------------------------------------------------------------

class TestUnknownTool:
    def test_unknown_tool_returns_unresolved(self):
        result = assemble("no_such_tool_xyz", "status", {}, registry)
        assert isinstance(result, Unresolved)
        assert result.missing == []
        assert "no_such_tool_xyz" in result.reason

    def test_unknown_tool_reason_not_empty(self):
        result = assemble("nonexistent", "op", {}, registry)
        assert isinstance(result, Unresolved)
        assert result.reason


# ---------------------------------------------------------------------------
# 6. Unknown operation -> Unresolved
# ---------------------------------------------------------------------------

class TestUnknownOperation:
    def test_unknown_op_returns_unresolved(self):
        result = assemble("services", "teleport", {}, registry)
        assert isinstance(result, Unresolved)
        assert result.missing == []
        assert "teleport" in result.reason

    def test_unknown_op_reason_mentions_valid_ops(self):
        result = assemble("disk", "vaporize", {}, registry)
        assert isinstance(result, Unresolved)
        # Valid ops should be hinted (format, list, mount, …)
        assert "format" in result.reason or "list" in result.reason


# ---------------------------------------------------------------------------
# 7. Assembler NEVER emits a shell string (A5)
# ---------------------------------------------------------------------------

class TestNoShellString:
    """The assembler must return ParsedCall or Unresolved, never a raw string."""

    @pytest.mark.parametrize("tool,op,slots", [
        ("services", "restart", {"unit": "nginx.service"}),
        ("disk", "format", {"device": "/dev/sdb"}),
        ("packages", "install", {"packages": ["curl"]}),
        ("users", "delete", {"user": "bob"}),
        ("firewall", "panic_on", {}),
    ])
    def test_result_is_not_a_string(self, tool, op, slots):
        result = assemble(tool, op, slots, registry)
        assert not isinstance(result, str), (
            f"assemble({tool!r}, {op!r}) returned a string (A5 violation): {result!r}"
        )


# ---------------------------------------------------------------------------
# 8. permission_class matches spec declaration (never under-stated)
# ---------------------------------------------------------------------------

class TestPermissionClassParity:
    """assembled.permission_class == spec.permission_class_for(op)."""

    @pytest.mark.parametrize("tool,op,slots,expected_class", [
        ("services", "status", {"unit": "sshd.service"}, OpClass.READ),
        ("services", "restart", {"unit": "sshd.service"}, OpClass.WRITE),
        ("disk", "list", {}, OpClass.READ),
        ("disk", "mount", {"device": "/dev/sdb1", "mount_point": "/mnt/x"}, OpClass.WRITE),
        ("disk", "format", {"device": "/dev/sdb"}, OpClass.DESTRUCTIVE),
        ("disk", "wipe", {"device": "/dev/sdb"}, OpClass.DESTRUCTIVE),
        ("users", "list", {}, OpClass.READ),
        ("users", "lock", {"user": "bob"}, OpClass.DESTRUCTIVE),
        ("firewall", "list", {}, OpClass.READ),
        ("firewall", "panic_on", {}, OpClass.DESTRUCTIVE),
    ])
    def test_permission_class(self, tool, op, slots, expected_class):
        result = assemble(tool, op, slots, registry)
        assert isinstance(result, ParsedCall), (
            f"Expected ParsedCall for {tool}.{op}, got {result!r}"
        )
        assert result.permission_class == expected_class, (
            f"{tool}.{op}: expected {expected_class.name}, "
            f"got {result.permission_class.name}"
        )
