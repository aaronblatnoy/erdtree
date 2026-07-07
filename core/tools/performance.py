"""core/tools/performance.py — System performance metrics via sysstat and procps utilities.

Supported operations
--------------------
  sar     (READ) — CPU, I/O, and system resource utilization via sar.
  iostat  (READ) — Disk I/O statistics via iostat.
  vmstat  (READ) — Virtual memory and system statistics via vmstat.
  mpstat  (READ) — Per-CPU and aggregate CPU statistics via mpstat.
  uptime  (READ) — System uptime and load averages via uptime.
  load    (READ) — Current load averages from /proc/loadavg.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.
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
# SELinux hint detection (verbatim from services.py)
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
# Shared optional args
# ---------------------------------------------------------------------------

_INTERVAL_ARG = ArgSpec(
    name="interval",
    type=int,
    required=False,
    description="Sampling interval in seconds (default 1).",
    default=1,
)

_COUNT_ARG = ArgSpec(
    name="count",
    type=int,
    required=False,
    description="Number of samples to collect (default 1).",
    default=1,
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_sar(args: dict[str, Any]) -> ToolResult:
    """sar -u [interval] [count] — CPU utilization report."""
    raw_interval = args.get("interval")
    raw_count = args.get("count")
    interval: int = int(raw_interval) if raw_interval is not None else 1
    count: int = int(raw_count) if raw_count is not None else 1
    interval = max(1, interval)
    count = max(1, min(count, 60))
    cmd = ["sar", "-u", str(interval), str(count)]
    result = run_subprocess(cmd, timeout=max(30, interval * count + 5))
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"CPU utilization report collected ({count} sample(s) at {interval}s interval)."
        )
    else:
        summary = (
            f"sar failed to collect CPU statistics (exit {result.exit_code}). "
            "Ensure the sysstat package is installed."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_iostat(args: dict[str, Any]) -> ToolResult:
    """iostat -x [interval] [count] — Extended disk I/O statistics."""
    raw_interval = args.get("interval")
    raw_count = args.get("count")
    interval: int = int(raw_interval) if raw_interval is not None else 1
    count: int = int(raw_count) if raw_count is not None else 1
    interval = max(1, interval)
    count = max(1, min(count, 60))
    cmd = ["iostat", "-x", str(interval), str(count)]
    result = run_subprocess(cmd, timeout=max(30, interval * count + 5))
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Disk I/O statistics collected ({count} sample(s) at {interval}s interval)."
        )
    else:
        summary = (
            f"iostat failed to collect disk statistics (exit {result.exit_code}). "
            "Ensure the sysstat package is installed."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_vmstat(args: dict[str, Any]) -> ToolResult:
    """vmstat [interval] [count] — Virtual memory and system statistics."""
    raw_interval = args.get("interval")
    raw_count = args.get("count")
    interval: int = int(raw_interval) if raw_interval is not None else 1
    count: int = int(raw_count) if raw_count is not None else 1
    interval = max(1, interval)
    count = max(1, min(count, 60))
    cmd = ["vmstat", str(interval), str(count)]
    result = run_subprocess(cmd, timeout=max(30, interval * count + 5))
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Virtual memory statistics collected ({count} sample(s) at {interval}s interval)."
        )
    else:
        summary = (
            f"vmstat failed to collect memory statistics (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_mpstat(args: dict[str, Any]) -> ToolResult:
    """mpstat -P ALL [interval] [count] — Per-CPU utilization statistics."""
    raw_interval = args.get("interval")
    raw_count = args.get("count")
    interval: int = int(raw_interval) if raw_interval is not None else 1
    count: int = int(raw_count) if raw_count is not None else 1
    interval = max(1, interval)
    count = max(1, min(count, 60))
    cmd = ["mpstat", "-P", "ALL", str(interval), str(count)]
    result = run_subprocess(cmd, timeout=max(30, interval * count + 5))
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Per-CPU statistics collected ({count} sample(s) at {interval}s interval)."
        )
    else:
        summary = (
            f"mpstat failed to collect CPU statistics (exit {result.exit_code}). "
            "Ensure the sysstat package is installed."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_uptime(args: dict[str, Any]) -> ToolResult:
    """uptime — Show system uptime and load averages."""
    result = run_subprocess(["uptime"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "System uptime and load averages retrieved."
    else:
        summary = f"uptime command failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_load(args: dict[str, Any]) -> ToolResult:
    """cat /proc/loadavg — Read current load averages from the kernel."""
    result = run_subprocess(["cat", "/proc/loadavg"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "System load averages (1m, 5m, 15m) retrieved from /proc/loadavg."
    else:
        summary = f"Failed to read load averages (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "sar":    _op_sar,
    "iostat": _op_iostat,
    "vmstat": _op_vmstat,
    "mpstat": _op_mpstat,
    "uptime": _op_uptime,
    "load":   _op_load,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a performance operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9): unknown ops and binary failures both degrade gracefully.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for performance tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

PERFORMANCE_SPEC = ToolSpec(
    name="performance",
    description="Collect system performance metrics via sysstat (sar/iostat/mpstat) and procps (vmstat/uptime).",
    ops={
        "sar": OpSpec(
            op_name="sar",
            permission_class=OpClass.READ,
            args=[_INTERVAL_ARG, _COUNT_ARG],
            description="Report CPU utilization statistics using sar.",
        ),
        "iostat": OpSpec(
            op_name="iostat",
            permission_class=OpClass.READ,
            args=[_INTERVAL_ARG, _COUNT_ARG],
            description="Report disk I/O statistics using iostat.",
        ),
        "vmstat": OpSpec(
            op_name="vmstat",
            permission_class=OpClass.READ,
            args=[_INTERVAL_ARG, _COUNT_ARG],
            description="Report virtual memory and system statistics using vmstat.",
        ),
        "mpstat": OpSpec(
            op_name="mpstat",
            permission_class=OpClass.READ,
            args=[_INTERVAL_ARG, _COUNT_ARG],
            description="Report per-CPU utilization statistics using mpstat.",
        ),
        "uptime": OpSpec(
            op_name="uptime",
            permission_class=OpClass.READ,
            args=[],
            description="Show system uptime and current load averages.",
        ),
        "load": OpSpec(
            op_name="load",
            permission_class=OpClass.READ,
            args=[],
            description="Read 1-minute, 5-minute, and 15-minute load averages from /proc/loadavg.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(PERFORMANCE_SPEC)
