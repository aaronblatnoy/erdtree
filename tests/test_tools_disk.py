"""tests/test_tools_disk.py — stdlib unittest tests for core/tools/disk.py.

Run with::

    python3 -m unittest tests.test_tools_disk

Every subprocess call is mocked by patching ``core.tools.disk.run_subprocess``
so NO real process runs and no real device is touched (the binaries
mkfs/parted/wipefs/smartctl are absent on this Linux dev host anyway).

Coverage:
  * registry.get("disk") is present after import (self-registration).
  * Every declared op dispatches and returns a well-formed ToolResult.
  * READ ops (usage/list/smart) classify ALLOW (no gate) via the EXISTING
    classifier when their synthesized command line is fed to classify().
  * WRITE ops (mount/unmount) classify CONFIRM.
  * DESTRUCTIVE ops (format/partition/wipe/dd_write) classify
    CONFIRM_TYPED interactively and REFUSE non-interactively — the data-loss
    keystone (SC-P6.2).
  * Each op builds the EXPECTED command vector (the real dangerous shape for
    destructive ops, so the classifier sees the true blast radius).
  * The I2 filter (core/agent/prompt.py _FORBIDDEN_AI_TERMS) passes on every
    ToolSpec/OpSpec description AND every ToolResult.summary.
  * No tier/product names (I6) in the module source.
  * No network/URL-like tokens in any command vector (I1).
  * disk imports no forbidden device/disk Python libraries (I1 / classifier-
    visibility rule).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

import core.tools.disk as disk_mod
from core.tools.disk import (
    TOOL_SPEC,
    _execute,
    _DISPATCH,
)
from core.tools import registry, ToolResult
from core.agent.permissions import (
    classify,
    ExecContext,
    Gate,
    OpClass,
)
from core.agent.prompt import _FORBIDDEN_AI_TERMS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "", exit_code: int = 0) -> ToolResult:
    return ToolResult(
        exit_code=exit_code, stdout=stdout, stderr=stderr, summary="stub"
    )


def _patch_run(stdout: str = "", stderr: str = "", exit_code: int = 0):
    """Patch core.tools.disk.run_subprocess to return a canned ToolResult and
    capture the command vector it was called with."""
    return patch.object(
        disk_mod,
        "run_subprocess",
        return_value=_ok_result(stdout=stdout, stderr=stderr, exit_code=exit_code),
    )


# Whole-word I2 matcher built from the canonical forbidden-term list.
_I2_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _FORBIDDEN_AI_TERMS) + r")\b",
    re.IGNORECASE,
)


def _assert_i2_clean(testcase: unittest.TestCase, text: str, label: str) -> None:
    m = _I2_PATTERN.search(text)
    testcase.assertIsNone(
        m,
        f"I2 violation in {label}: {text!r} contains forbidden term "
        f"{m.group() if m else ''!r}",
    )


# Minimal valid args per op (so _execute can run each one).
_OP_ARGS: dict[str, dict[str, Any]] = {
    "usage": {},
    "list": {},
    "smart": {"device": "/dev/sdb"},
    "mount": {"device": "/dev/sdb1", "mount_point": "/mnt/data"},
    "unmount": {"target": "/mnt/data"},
    "format": {"device": "/dev/sdb1", "fstype": "ext4"},
    "partition": {"device": "/dev/sdb", "command": ["mklabel", "gpt"]},
    "wipe": {"device": "/dev/sdb1"},
    "dd_write": {"source": "/tmp/image.img", "device": "/dev/sdb"},
}

# The literal command line the REPL's synthesize_command() renders for the
# classifier per the Phase 6 spec. The tool builds the matching argv; here we
# feed the rendered string straight through the EXISTING classifier (we do NOT
# re-implement classification — we only verify the synthesized shape fires it).
_SYNTH: dict[str, str] = {
    "usage": "df -h",
    "list": "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT",
    "smart": "smartctl -H -A /dev/sdb",
    "mount": "mount /dev/sdb1 /mnt/data",
    "unmount": "umount /mnt/data",
    "format": "mkfs.ext4 /dev/sdb1",
    "partition": "parted /dev/sdb mklabel gpt",
    "wipe": "wipefs -a /dev/sdb1",
    "dd_write": "dd if=/tmp/image.img of=/dev/sdb bs=4M",
}

_READ_OPS = {"usage", "list", "smart"}
_WRITE_OPS = {"mount", "unmount"}
_DESTRUCTIVE_OPS = {"format", "partition", "wipe", "dd_write"}


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

class TestRegistration(unittest.TestCase):
    def test_disk_registered(self) -> None:
        self.assertIsNotNone(
            registry.get("disk"), "disk tool must self-register on import"
        )

    def test_tool_name(self) -> None:
        self.assertEqual(TOOL_SPEC.name, "disk")

    def test_all_ops_present(self) -> None:
        expected = {
            "usage", "list", "smart", "mount", "unmount",
            "format", "partition", "wipe", "dd_write",
        }
        self.assertEqual(set(TOOL_SPEC.ops.keys()), expected)
        self.assertEqual(set(_DISPATCH.keys()), expected)

    def test_permission_classes(self) -> None:
        for op in _READ_OPS:
            self.assertIs(TOOL_SPEC.ops[op].permission_class, OpClass.READ, op)
        for op in _WRITE_OPS:
            self.assertIs(TOOL_SPEC.ops[op].permission_class, OpClass.WRITE, op)
        for op in _DESTRUCTIVE_OPS:
            self.assertIs(
                TOOL_SPEC.ops[op].permission_class, OpClass.DESTRUCTIVE, op
            )

    def test_registry_permission_class_for(self) -> None:
        for op in TOOL_SPEC.ops:
            self.assertIs(
                registry.permission_class_for("disk", op),
                TOOL_SPEC.ops[op].permission_class,
            )


# ---------------------------------------------------------------------------
# 2. Each op dispatches and returns a well-formed ToolResult
# ---------------------------------------------------------------------------

class TestDispatch(unittest.TestCase):
    def test_each_op_returns_tool_result(self) -> None:
        for op, args in _OP_ARGS.items():
            with _patch_run(stdout="line1\nline2\n"):
                result = _execute(op, args)
            self.assertIsInstance(result, ToolResult, op)
            self.assertIsInstance(result.summary, str, op)
            self.assertTrue(result.summary, f"{op} summary must be non-empty")

    def test_unknown_op_degrades(self) -> None:
        # I9: never raise — degrade to a well-formed error ToolResult.
        result = _execute("no_such_op", {})
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("unknown operation", result.summary.lower())

    def test_failure_path_returns_result(self) -> None:
        for op, args in _OP_ARGS.items():
            with _patch_run(stderr="some error", exit_code=1):
                result = _execute(op, args)
            self.assertIsInstance(result, ToolResult, op)
            self.assertEqual(result.exit_code, 1, op)
            self.assertFalse(result.ok, op)


# ---------------------------------------------------------------------------
# 3. Command-vector shape — destructive ops emit the REAL dangerous form
# ---------------------------------------------------------------------------

class TestCommandVectors(unittest.TestCase):
    def _cmd_for(self, op: str, args: dict[str, Any]) -> list[str]:
        with _patch_run() as mock_run:
            _execute(op, args)
        self.assertTrue(mock_run.called, f"{op} must call run_subprocess")
        return list(mock_run.call_args[0][0])

    def test_read_vectors(self) -> None:
        self.assertEqual(self._cmd_for("usage", _OP_ARGS["usage"])[0], "df")
        self.assertEqual(self._cmd_for("list", _OP_ARGS["list"])[0], "lsblk")
        smart = self._cmd_for("smart", _OP_ARGS["smart"])
        self.assertEqual(smart[0], "smartctl")
        self.assertIn("/dev/sdb", smart)

    def test_write_vectors(self) -> None:
        mount = self._cmd_for("mount", _OP_ARGS["mount"])
        self.assertEqual(mount, ["mount", "/dev/sdb1", "/mnt/data"])
        umount = self._cmd_for("unmount", _OP_ARGS["unmount"])
        self.assertEqual(umount, ["umount", "/mnt/data"])

    def test_format_uses_mkfs_fstype(self) -> None:
        cmd = self._cmd_for("format", _OP_ARGS["format"])
        self.assertEqual(cmd[0], "mkfs.ext4")
        self.assertIn("/dev/sdb1", cmd)

    def test_partition_uses_parted(self) -> None:
        cmd = self._cmd_for("partition", _OP_ARGS["partition"])
        self.assertEqual(cmd[0], "parted")
        self.assertIn("/dev/sdb", cmd)
        self.assertIn("mklabel", cmd)

    def test_wipe_uses_wipefs_a(self) -> None:
        cmd = self._cmd_for("wipe", _OP_ARGS["wipe"])
        self.assertEqual(cmd[:2], ["wipefs", "-a"])
        self.assertIn("/dev/sdb1", cmd)

    def test_dd_write_uses_of_device(self) -> None:
        cmd = self._cmd_for("dd_write", _OP_ARGS["dd_write"])
        self.assertEqual(cmd[0], "dd")
        self.assertIn("of=/dev/sdb", cmd)
        self.assertIn("if=/tmp/image.img", cmd)


# ---------------------------------------------------------------------------
# 4. Permission gate via the EXISTING hardened classifier (SC-P6.2)
# ---------------------------------------------------------------------------

class TestPermissionGate(unittest.TestCase):
    def test_read_ops_allow_no_gate(self) -> None:
        for op in _READ_OPS:
            decision = classify(_SYNTH[op], ExecContext())
            self.assertIs(
                decision.gate, Gate.ALLOW, f"{op} -> {_SYNTH[op]!r}"
            )
            self.assertIs(decision.op_class, OpClass.READ, op)
            self.assertTrue(decision.auto_ok, op)

    def test_write_ops_confirm(self) -> None:
        for op in _WRITE_OPS:
            decision = classify(_SYNTH[op], ExecContext())
            self.assertIs(
                decision.gate, Gate.CONFIRM, f"{op} -> {_SYNTH[op]!r}"
            )
            self.assertFalse(decision.auto_ok, op)

    def test_destructive_ops_confirm_typed_interactive(self) -> None:
        for op in _DESTRUCTIVE_OPS:
            decision = classify(_SYNTH[op], ExecContext(interactive=True))
            self.assertIs(
                decision.op_class, OpClass.DESTRUCTIVE, f"{op} -> {_SYNTH[op]!r}"
            )
            self.assertIs(
                decision.gate, Gate.CONFIRM_TYPED, f"{op} -> {_SYNTH[op]!r}"
            )
            self.assertTrue(decision.requires_typed_word, op)
            self.assertFalse(decision.auto_ok, op)

    def test_destructive_ops_refuse_non_interactive(self) -> None:
        for op in _DESTRUCTIVE_OPS:
            decision = classify(_SYNTH[op], ExecContext(interactive=False))
            self.assertIs(
                decision.gate, Gate.REFUSE, f"{op} -> {_SYNTH[op]!r}"
            )
            self.assertFalse(decision.auto_ok, op)


# ---------------------------------------------------------------------------
# 5. I2 — no forbidden language in any user-facing string
# ---------------------------------------------------------------------------

class TestI2Filter(unittest.TestCase):
    def test_tool_and_op_descriptions_clean(self) -> None:
        _assert_i2_clean(self, TOOL_SPEC.description, "TOOL_SPEC.description")
        for name, op_spec in TOOL_SPEC.ops.items():
            _assert_i2_clean(self, op_spec.description, f"op '{name}' description")
            for arg in op_spec.args:
                _assert_i2_clean(
                    self, arg.description, f"op '{name}' arg '{arg.name}'"
                )

    def test_all_summaries_clean(self) -> None:
        # Exercise both success and failure summaries for every op.
        for op, args in _OP_ARGS.items():
            with _patch_run(stdout="a\nb\n", exit_code=0):
                ok = _execute(op, args)
            _assert_i2_clean(self, ok.summary, f"{op} success summary")
            with _patch_run(stderr="boom", exit_code=1):
                fail = _execute(op, args)
            _assert_i2_clean(self, fail.summary, f"{op} failure summary")

    def test_selinux_hint_summary_clean(self) -> None:
        avc = "type=AVC avc:  denied  { write } for pid=1 comm=\"mkfs\""
        for op, args in _OP_ARGS.items():
            with _patch_run(stderr=avc, exit_code=1):
                result = _execute(op, args)
            _assert_i2_clean(self, result.summary, f"{op} selinux summary")

    def test_unknown_op_summary_clean(self) -> None:
        _assert_i2_clean(self, _execute("bogus", {}).summary, "unknown-op summary")


# ---------------------------------------------------------------------------
# 6. I6 — no tier/product names in module source
# ---------------------------------------------------------------------------

class TestNoTierNames(unittest.TestCase):
    FORBIDDEN = ("marika", "radagon", "radahn", "starscourge")

    def test_no_tier_names_in_source(self) -> None:
        source = Path(disk_mod.__file__).read_text(encoding="utf-8").lower()
        for name in self.FORBIDDEN:
            self.assertNotIn(name, source, f"tier/product name '{name}' in disk.py")


# ---------------------------------------------------------------------------
# 7. I1 — no network egress; no forbidden device libraries imported
# ---------------------------------------------------------------------------

class TestEgressAndImports(unittest.TestCase):
    def test_no_url_like_tokens_in_command_vectors(self) -> None:
        captured: list[list[str]] = []

        def _capture(cmd, **kwargs):
            captured.append(list(cmd))
            return _ok_result()

        with patch.object(disk_mod, "run_subprocess", side_effect=_capture):
            for op, args in _OP_ARGS.items():
                _execute(op, args)

        self.assertEqual(len(captured), len(_OP_ARGS))
        for cmd in captured:
            for token in cmd:
                self.assertNotIn("://", token, f"URL-like token in {cmd}")

    def test_no_forbidden_libraries_imported(self) -> None:
        source = Path(disk_mod.__file__).read_text(encoding="utf-8")
        for banned in ("psutil", "pyroute2", "shutil.rmtree", "os.remove",
                       "os.rmdir", "os.unlink"):
            self.assertNotIn(
                banned, source,
                f"disk.py must not use {banned!r} — shell out via run_subprocess only",
            )


# ---------------------------------------------------------------------------
# 8. Registry dispatch round-trip
# ---------------------------------------------------------------------------

class TestRegistryDispatch(unittest.TestCase):
    def test_dispatch_read_op(self) -> None:
        with _patch_run(stdout="x\ny\n"):
            result = registry.dispatch("disk", "list", {})
        self.assertIsInstance(result, ToolResult)

    def test_dispatch_destructive_op(self) -> None:
        with _patch_run(stdout=""):
            result = registry.dispatch(
                "disk", "format", {"device": "/dev/sdb1", "fstype": "ext4"}
            )
        self.assertIsInstance(result, ToolResult)

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with self.assertRaises(TypeError):
            registry.dispatch("disk", "smart", {})


if __name__ == "__main__":
    unittest.main()
