"""core/tools/hardware.py — hardware inspection tool.

Supported operations (ALL READ — no gate friction)
---------------------------------------------------
  cpu      — processor topology and capability flags (lscpu).
  memory   — RAM and swap usage summary (free -h).
  pci      — PCI bus device list (lspci).
  usb      — USB device list (lsusb).
  block    — block device topology (lsblk).
  sensors  — hardware sensor readings: temperature, fan speed, voltage (sensors).
  summary  — combined one-shot snapshot: cpu + memory + block (three calls).

Permission mapping
------------------
  ALL ops: READ — no confirmation required.

Design rules
------------
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller (router / REPL) resolves the permission gate BEFORE calling
      execute(); this module does NOT call permissions.classify() internally.
  I4  The caller writes the audit record; this module does not.
  I6  Zero tier/product/model names anywhere in this file.

Subprocess mocking
------------------
  On hosts where lscpu/lspci/lsusb/free/sensors/dmidecode are absent, every
  test patches ``core.tools.hardware.run_subprocess`` so no real process is
  launched.  The tool is fully portable.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint detection
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_cpu(args: dict[str, Any]) -> ToolResult:
    """lscpu — processor topology and flags."""
    result = run_subprocess(["lscpu"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "CPU topology retrieved."
    else:
        summary = f"CPU topology query failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_memory(args: dict[str, Any]) -> ToolResult:
    """free -h — RAM and swap usage."""
    result = run_subprocess(["free", "-h"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Memory and swap usage retrieved."
    else:
        summary = f"Memory usage query failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pci(args: dict[str, Any]) -> ToolResult:
    """lspci — PCI bus device list."""
    result = run_subprocess(["lspci"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        count = len([l for l in result.stdout.splitlines() if l.strip()])
        summary = f"PCI device list retrieved ({count} device(s))."
    else:
        summary = f"PCI device query failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_usb(args: dict[str, Any]) -> ToolResult:
    """lsusb — USB device list."""
    result = run_subprocess(["lsusb"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        count = len([l for l in result.stdout.splitlines() if l.strip()])
        summary = f"USB device list retrieved ({count} device(s))."
    else:
        summary = f"USB device query failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_block(args: dict[str, Any]) -> ToolResult:
    """lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT — block device topology."""
    result = run_subprocess(
        ["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        count = len([l for l in result.stdout.splitlines() if l.strip()])
        # Subtract header line if present
        count = max(0, count - 1)
        summary = f"Block device topology retrieved ({count} device(s))."
    else:
        summary = f"Block device query failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_sensors(args: dict[str, Any]) -> ToolResult:
    """sensors — hardware sensor readings (temperature, fan speed, voltage)."""
    result = run_subprocess(["sensors"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Hardware sensor readings retrieved."
    else:
        summary = f"Sensor readings failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_summary(args: dict[str, Any]) -> ToolResult:
    """Combined snapshot: cpu + memory + block device topology."""
    cpu_r = run_subprocess(["lscpu"])
    mem_r = run_subprocess(["free", "-h"])
    blk_r = run_subprocess(["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"])

    parts = []
    if cpu_r.stdout.strip():
        parts.append("=== CPU ===\n" + cpu_r.stdout.rstrip())
    if mem_r.stdout.strip():
        parts.append("=== MEMORY ===\n" + mem_r.stdout.rstrip())
    if blk_r.stdout.strip():
        parts.append("=== BLOCK DEVICES ===\n" + blk_r.stdout.rstrip())

    combined_stdout = "\n\n".join(parts)
    combined_stderr = "\n".join(
        s for s in [cpu_r.stderr, mem_r.stderr, blk_r.stderr] if s.strip()
    )
    selinux = _maybe_selinux_hint(combined_stderr)

    # Use the worst exit code of the three.
    worst = max(
        (r.exit_code or 0) for r in [cpu_r, mem_r, blk_r]
    )

    if worst == 0:
        summary = "Hardware summary retrieved (CPU, memory, block devices)."
    else:
        summary = f"Hardware summary partially failed (worst exit {worst})."

    return ToolResult(
        exit_code=worst,
        stdout=combined_stdout,
        stderr=combined_stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "cpu":     _op_cpu,
    "memory":  _op_memory,
    "pci":     _op_pci,
    "usb":     _op_usb,
    "block":   _op_block,
    "sensors": _op_sensors,
    "summary": _op_summary,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a hardware operation and return a structured ToolResult.

    The caller (Phase 4 router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never writes to the audit log itself (I4 is the caller's responsibility).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for hardware tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

HARDWARE_SPEC = ToolSpec(
    name="hardware",
    description="Inspect hardware: CPU, memory, PCI devices, USB devices, block devices, and sensors.",
    ops={
        "cpu": OpSpec(
            op_name="cpu",
            permission_class=OpClass.READ,
            args=[],
            description="Show processor topology and capability information.",
        ),
        "memory": OpSpec(
            op_name="memory",
            permission_class=OpClass.READ,
            args=[],
            description="Show RAM and swap usage.",
        ),
        "pci": OpSpec(
            op_name="pci",
            permission_class=OpClass.READ,
            args=[],
            description="List PCI bus devices.",
        ),
        "usb": OpSpec(
            op_name="usb",
            permission_class=OpClass.READ,
            args=[],
            description="List USB devices.",
        ),
        "block": OpSpec(
            op_name="block",
            permission_class=OpClass.READ,
            args=[],
            description="Show block device topology (disks, partitions, mount points).",
        ),
        "sensors": OpSpec(
            op_name="sensors",
            permission_class=OpClass.READ,
            args=[],
            description="Show hardware sensor readings: temperature, fan speed, voltage.",
        ),
        "summary": OpSpec(
            op_name="summary",
            permission_class=OpClass.READ,
            args=[],
            description="Show a combined hardware snapshot: CPU, memory, and block devices.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(HARDWARE_SPEC)
