"""tests/test_tools_hardware.py — Unit tests for core/tools/hardware.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the Linux dev host without lscpu/lspci/lsusb/free/sensors present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * All 7 ops (cpu/memory/pci/usb/block/sensors/summary) are READ class.
  * Each operation produces a well-formed ToolResult.
  * Success (exit_code=0) -> ok=True, non-empty summary without AI language.
  * Failure (exit_code!=0) -> ok=False, failure summary.
  * summary op combines three subprocess calls into one ToolResult; worst
    exit code propagated; combined stdout contains section headers.
  * SELinux AVC hint surfaces in summary when stderr contains AVC language.
  * I2 filter: every description and summary is free of forbidden AI terms
    (imported from core.agent.prompt._FORBIDDEN_AI_TERMS — the canonical list).
  * registry.get("hardware") is present after import.
  * READ ops get Gate.ALLOW via permissions.classify() on the synthesized
    command strings.
  * DEFERRED-TO-MOSSAD: live execution on real Rocky Linux 9 hardware.
"""

from __future__ import annotations

import re
import unittest
from typing import Any
from unittest.mock import MagicMock, patch, call

# Trigger self-registration at import time.
import core.tools.hardware  # noqa: F401
from core.agent.permissions import Gate, OpClass, classify
from core.agent.prompt import _FORBIDDEN_AI_TERMS
from core.tools import ToolResult, registry
from core.tools.hardware import HARDWARE_SPEC, _execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Patch core.tools.hardware.run_subprocess with a fixed return value."""
    return patch("core.tools.hardware.run_subprocess", return_value=return_value)


def _i2_check(text: str, label: str = "") -> None:
    """Assert that *text* contains no I2-forbidden terms (case-insensitive whole word)."""
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in _FORBIDDEN_AI_TERMS) + r")\b",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    if match:
        raise AssertionError(
            f"I2 violation in {label!r}: found forbidden term "
            f"{match.group()!r} at position {match.start()}. Text: {text!r}"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration(unittest.TestCase):

    def test_hardware_registered(self) -> None:
        self.assertIsNotNone(registry.get("hardware"))

    def test_spec_name(self) -> None:
        spec = registry.get("hardware")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.name, "hardware")

    def test_all_ops_present(self) -> None:
        spec = registry.get("hardware")
        self.assertIsNotNone(spec)
        expected = {"cpu", "memory", "pci", "usb", "block", "sensors", "summary"}
        self.assertEqual(set(spec.ops.keys()), expected)


# ---------------------------------------------------------------------------
# Permission classes — ALL READ
# ---------------------------------------------------------------------------

class TestPermissionClasses(unittest.TestCase):

    def _check_read(self, op: str) -> None:
        cls = registry.permission_class_for("hardware", op)
        self.assertIs(cls, OpClass.READ, f"Expected READ for '{op}', got {cls}")

    def test_cpu_is_read(self) -> None:
        self._check_read("cpu")

    def test_memory_is_read(self) -> None:
        self._check_read("memory")

    def test_pci_is_read(self) -> None:
        self._check_read("pci")

    def test_usb_is_read(self) -> None:
        self._check_read("usb")

    def test_block_is_read(self) -> None:
        self._check_read("block")

    def test_sensors_is_read(self) -> None:
        self._check_read("sensors")

    def test_summary_is_read(self) -> None:
        self._check_read("summary")


# ---------------------------------------------------------------------------
# Permission gate integration — READ -> ALLOW via permissions.classify
# ---------------------------------------------------------------------------

class TestPermissionGateIntegration(unittest.TestCase):
    """Verify synthesized command strings for hardware ops classify as READ/ALLOW."""

    _OP_CMDS = [
        ("cpu",     "lscpu"),
        ("memory",  "free -h"),
        ("pci",     "lspci"),
        ("usb",     "lsusb"),
        ("block",   "lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"),
        ("sensors", "sensors"),
    ]

    def test_read_ops_get_allow_gate(self) -> None:
        for op, cmd in self._OP_CMDS:
            with self.subTest(op=op, cmd=cmd):
                decision = classify(cmd)
                self.assertIs(
                    decision.gate, Gate.ALLOW,
                    f"Op '{op}' cmd '{cmd}' expected ALLOW, got {decision.gate}"
                )
                self.assertTrue(decision.auto_ok)


# ---------------------------------------------------------------------------
# cpu operation
# ---------------------------------------------------------------------------

class TestCpu(unittest.TestCase):

    def test_success(self) -> None:
        with _patch_run(_ok(stdout="Architecture: x86_64\nCPU(s): 8\n")):
            result = _execute("cpu", {})
        self.assertTrue(result.ok)
        self.assertIn("CPU", result.summary)

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=127)):
            result = _execute("cpu", {})
        self.assertFalse(result.ok)
        self.assertEqual(result.exit_code, 127)

    def test_stdout_preserved(self) -> None:
        with _patch_run(_ok(stdout="Architecture: x86_64")):
            result = _execute("cpu", {})
        self.assertEqual(result.stdout, "Architecture: x86_64")


# ---------------------------------------------------------------------------
# memory operation
# ---------------------------------------------------------------------------

class TestMemory(unittest.TestCase):

    def test_success(self) -> None:
        with _patch_run(_ok(stdout="              total        used        free\nMem:           15Gi       3.2Gi        10Gi\n")):
            result = _execute("memory", {})
        self.assertTrue(result.ok)
        self.assertIn("emory", result.summary)  # "Memory" or "memory"

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1)):
            result = _execute("memory", {})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# pci operation
# ---------------------------------------------------------------------------

class TestPci(unittest.TestCase):

    def test_success_count(self) -> None:
        pci_out = (
            "00:00.0 Host bridge: Intel\n"
            "00:02.0 VGA compatible controller: Intel\n"
            "00:1f.6 Ethernet controller: Intel\n"
        )
        with _patch_run(_ok(stdout=pci_out)):
            result = _execute("pci", {})
        self.assertTrue(result.ok)
        self.assertIn("3", result.summary)

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1)):
            result = _execute("pci", {})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# usb operation
# ---------------------------------------------------------------------------

class TestUsb(unittest.TestCase):

    def test_success_count(self) -> None:
        usb_out = (
            "Bus 001 Device 001: ID 1d6b:0002 Linux Foundation 2.0 root hub\n"
            "Bus 001 Device 002: ID 8087:0024 Intel Corp. Integrated Rate Matching Hub\n"
        )
        with _patch_run(_ok(stdout=usb_out)):
            result = _execute("usb", {})
        self.assertTrue(result.ok)
        self.assertIn("2", result.summary)

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1)):
            result = _execute("usb", {})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# block operation
# ---------------------------------------------------------------------------

class TestBlock(unittest.TestCase):

    def test_success(self) -> None:
        blk_out = (
            "NAME   SIZE TYPE FSTYPE MOUNTPOINT\n"
            "sda    500G disk\n"
            "├─sda1   1G part vfat   /boot/efi\n"
            "└─sda2 499G part ext4   /\n"
        )
        with _patch_run(_ok(stdout=blk_out)):
            result = _execute("block", {})
        self.assertTrue(result.ok)
        self.assertIn("3", result.summary)  # 4 lines minus header = 3

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1)):
            result = _execute("block", {})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# sensors operation
# ---------------------------------------------------------------------------

class TestSensors(unittest.TestCase):

    def test_success(self) -> None:
        with _patch_run(_ok(stdout="coretemp-isa-0000\nCore 0: +42.0°C\n")):
            result = _execute("sensors", {})
        self.assertTrue(result.ok)
        self.assertIn("sensor", result.summary.lower())

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="No sensors found")):
            result = _execute("sensors", {})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# summary operation (three subprocess calls)
# ---------------------------------------------------------------------------

class TestSummary(unittest.TestCase):

    def _make_sequence(self, cpu_rc=0, mem_rc=0, blk_rc=0):
        """Build a side_effect list of ToolResult for the three run_subprocess calls."""
        return [
            ToolResult(exit_code=cpu_rc, stdout="CPU info", stderr="", summary=""),
            ToolResult(exit_code=mem_rc, stdout="Mem info", stderr="", summary=""),
            ToolResult(exit_code=blk_rc, stdout="NAME SIZE\nsda 500G", stderr="", summary=""),
        ]

    def test_all_success(self) -> None:
        mock_fn = MagicMock(side_effect=self._make_sequence())
        with patch("core.tools.hardware.run_subprocess", mock_fn):
            result = _execute("summary", {})
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(result.ok)
        self.assertIn("CPU", result.stdout)
        self.assertIn("MEMORY", result.stdout)
        self.assertIn("BLOCK", result.stdout)
        self.assertEqual(mock_fn.call_count, 3)

    def test_worst_exit_code_propagated(self) -> None:
        mock_fn = MagicMock(side_effect=self._make_sequence(cpu_rc=0, mem_rc=2, blk_rc=1))
        with patch("core.tools.hardware.run_subprocess", mock_fn):
            result = _execute("summary", {})
        self.assertEqual(result.exit_code, 2)

    def test_partial_failure_summary(self) -> None:
        mock_fn = MagicMock(side_effect=self._make_sequence(blk_rc=1))
        with patch("core.tools.hardware.run_subprocess", mock_fn):
            result = _execute("summary", {})
        self.assertFalse(result.ok)
        self.assertIn("1", result.summary)


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint(unittest.TestCase):

    _AVC_STDERR = (
        "AVC avc: denied { read } for pid=1234 "
        "comm=\"lscpu\" name=\"cpuinfo\""
    )

    def test_avc_in_stderr_surfaces_hint(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute("cpu", {})
        self.assertTrue(
            "SELinux" in result.summary or "ausearch" in result.summary,
            f"Expected SELinux hint in summary: {result.summary!r}"
        )

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="command not found")):
            result = _execute("cpu", {})
        self.assertNotIn("ausearch", result.summary)


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure(unittest.TestCase):

    _OPS = ["cpu", "memory", "pci", "usb", "block", "sensors"]

    def test_result_has_required_fields(self) -> None:
        for op in self._OPS:
            with self.subTest(op=op):
                with _patch_run(_ok(stdout=f"{op} output")):
                    result = _execute(op, {})
                self.assertIsInstance(result, ToolResult)
                self.assertIsNotNone(result.exit_code)
                self.assertIsInstance(result.stdout, str)
                self.assertIsInstance(result.stderr, str)
                self.assertIsInstance(result.summary, str)
                self.assertGreater(len(result.summary), 0)

    def test_as_dict_has_four_keys(self) -> None:
        for op in self._OPS:
            with self.subTest(op=op):
                with _patch_run(_ok()):
                    result = _execute(op, {})
                self.assertEqual(
                    set(result.as_dict().keys()),
                    {"exit_code", "stdout", "stderr", "summary"},
                )

    def test_unknown_op_returns_error_result(self) -> None:
        result = _execute("nonexistent_op", {})
        self.assertFalse(result.ok)
        self.assertIn("nonexistent_op", result.summary)


# ---------------------------------------------------------------------------
# I2 filter — no forbidden AI terms in descriptions or summaries
# ---------------------------------------------------------------------------

class TestI2Filter(unittest.TestCase):
    """Invariant I2: every description and summary must clear the forbidden-term filter."""

    def test_tool_description_clean(self) -> None:
        _i2_check(HARDWARE_SPEC.description, label="HARDWARE_SPEC.description")

    def test_all_op_descriptions_clean(self) -> None:
        for op_name, op_spec in HARDWARE_SPEC.ops.items():
            _i2_check(op_spec.description, label=f"OpSpec[{op_name}].description")

    def test_success_summaries_clean(self) -> None:
        ops = ["cpu", "memory", "pci", "usb", "block", "sensors"]
        for op in ops:
            with self.subTest(op=op):
                with _patch_run(_ok(stdout="some output line\n")):
                    result = _execute(op, {})
                _i2_check(result.summary, label=f"success summary for op={op}")

    def test_failure_summaries_clean(self) -> None:
        ops = ["cpu", "memory", "pci", "usb", "block", "sensors"]
        for op in ops:
            with self.subTest(op=op):
                with _patch_run(_fail(exit_code=1)):
                    result = _execute(op, {})
                _i2_check(result.summary, label=f"failure summary for op={op}")

    def test_summary_op_summaries_clean(self) -> None:
        for cpu_rc, mem_rc, blk_rc, label in [
            (0, 0, 0, "all_ok"),
            (1, 0, 0, "cpu_fail"),
            (0, 2, 1, "partial_fail"),
        ]:
            with self.subTest(label=label):
                seq = [
                    ToolResult(exit_code=cpu_rc, stdout="CPU", stderr="", summary=""),
                    ToolResult(exit_code=mem_rc, stdout="Mem", stderr="", summary=""),
                    ToolResult(exit_code=blk_rc, stdout="Blk", stderr="", summary=""),
                ]
                mock_fn = MagicMock(side_effect=seq)
                with patch("core.tools.hardware.run_subprocess", mock_fn):
                    result = _execute("summary", {})
                _i2_check(result.summary, label=f"summary op [{label}]")


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch(unittest.TestCase):

    def test_dispatch_cpu(self) -> None:
        with _patch_run(_ok(stdout="Architecture: x86_64")):
            result = registry.dispatch("hardware", "cpu", {})
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.exit_code, 0)

    def test_dispatch_memory(self) -> None:
        with _patch_run(_ok(stdout="Mem: 15Gi")):
            result = registry.dispatch("hardware", "memory", {})
        self.assertTrue(result.ok)

    def test_dispatch_unknown_op_raises(self) -> None:
        with self.assertRaises(ValueError):
            registry.dispatch("hardware", "no_such_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

# The following are intentionally SKIPPED on the dev host.
# They must be run on mossad (Rocky Linux 9, lscpu/lspci/lsusb/free/sensors
# all present).

@unittest.skip("DEFERRED-TO-MOSSAD: requires real lscpu on Rocky Linux 9")
class TestLiveExecution(unittest.TestCase):

    def test_live_cpu(self) -> None:
        result = _execute("cpu", {})
        self.assertIn(result.exit_code, (0,))
        self.assertGreater(len(result.stdout), 0)

    def test_live_memory(self) -> None:
        result = _execute("memory", {})
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Mem:", result.stdout)

    def test_live_summary(self) -> None:
        result = _execute("summary", {})
        self.assertEqual(result.exit_code, 0)
        self.assertIn("CPU", result.stdout)


if __name__ == "__main__":
    unittest.main()
