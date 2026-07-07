"""core/tools/perf.py — Linux perf tool for CPU performance profiling.

Supported operations
--------------------
  stat    (READ)  — run 'perf stat' to count hardware events for a command.
  top     (READ)  — show live CPU performance counter data via 'perf top'.
  record  (WRITE) — record performance data to perf.data via 'perf record'.

Permission mapping:
  READ  : stat, top
  WRITE : record

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
# SELinux hint detection (VERBATIM from services.py)
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
# Shared ArgSpecs
# ---------------------------------------------------------------------------

_COMMAND_ARG = ArgSpec(
    name="command",
    type=str,
    required=True,
    description="The command (and optional arguments) to profile, e.g. 'sleep 1' or 'ls -la'.",
)

_DURATION_ARG = ArgSpec(
    name="duration",
    type=int,
    required=False,
    description="Duration in seconds to collect data (default 10, max 300).",
    default=10,
)

_OUTPUT_ARG = ArgSpec(
    name="output",
    type=str,
    required=False,
    description="Output file path for perf record (default: perf.data).",
    default="perf.data",
)

_EVENTS_ARG = ArgSpec(
    name="events",
    type=str,
    required=False,
    description="Comma-separated perf event list, e.g. 'cycles,instructions' (default: system default).",
    default="",
)

_PID_ARG = ArgSpec(
    name="pid",
    type=int,
    required=False,
    description="Process ID to attach to instead of running a new command.",
    default=0,
)

# ---------------------------------------------------------------------------
# Operation implementations
# ---------------------------------------------------------------------------


def _op_stat(args: dict[str, Any]) -> ToolResult:
    """perf stat [-e events] [--] command"""
    command: str = args["command"]
    events: str = args.get("events", "") or ""
    repeats_raw = args.get("repeats")
    repeats: int = int(repeats_raw) if repeats_raw is not None else 1
    repeats = max(1, min(repeats, 10))

    cmd = ["perf", "stat"]
    if events:
        cmd += ["-e", events]
    if repeats > 1:
        cmd += ["-r", str(repeats)]
    cmd += ["--"] + command.split()

    result = run_subprocess(cmd, timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"perf stat completed for command '{command}'."
    else:
        summary = f"perf stat failed for command '{command}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_top(args: dict[str, Any]) -> ToolResult:
    """perf top -d <duration> [--stdio] [--sort key]"""
    duration_raw = args.get("duration")
    duration: int = int(duration_raw) if duration_raw is not None else 10
    duration = max(1, min(duration, 300))
    sort: str = args.get("sort", "") or ""
    events: str = args.get("events", "") or ""

    cmd = ["perf", "top", "--stdio", "-d", str(duration)]
    if events:
        cmd += ["-e", events]
    if sort:
        cmd += ["--sort", sort]

    result = run_subprocess(cmd, timeout=duration + 15)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"perf top ran for {duration}s and returned CPU profiling data."
    else:
        summary = f"perf top failed after {duration}s (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_record(args: dict[str, Any]) -> ToolResult:
    """perf record [-e events] [-o output] [--pid pid | -- command]"""
    output: str = args.get("output", "") or "perf.data"
    events: str = args.get("events", "") or ""
    pid_raw = args.get("pid")
    pid: int = int(pid_raw) if pid_raw is not None else 0
    command: str = args.get("command", "") or ""
    duration_raw = args.get("duration")
    duration: int = int(duration_raw) if duration_raw is not None else 10
    duration = max(1, min(duration, 300))

    cmd = ["perf", "record", "-o", output]
    if events:
        cmd += ["-e", events]

    if pid and pid > 0:
        cmd += ["-p", str(pid), "sleep", str(duration)]
    elif command:
        cmd += ["--"] + command.split()
    else:
        cmd += ["sleep", str(duration)]

    result = run_subprocess(cmd, timeout=duration + 30)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"perf record completed; data written to '{output}'."
    else:
        summary = f"perf record failed (exit {result.exit_code}); data may not have been written to '{output}'."
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
    "stat": _op_stat,
    "top": _op_top,
    "record": _op_record,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a perf operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never raises (I9): unknown ops and subprocess failures
    both return a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for perf tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

PERF_SPEC = ToolSpec(
    name="perf",
    description="Collect CPU performance counters and profiling data via the perf tool.",
    ops={
        "stat": OpSpec(
            op_name="stat",
            permission_class=OpClass.READ,
            args=[
                _COMMAND_ARG,
                _EVENTS_ARG,
                ArgSpec(
                    name="repeats",
                    type=int,
                    required=False,
                    description="Number of times to repeat the measurement for statistics (default 1, max 10).",
                    default=1,
                ),
            ],
            description="Run perf stat to count hardware performance events for a command.",
        ),
        "top": OpSpec(
            op_name="top",
            permission_class=OpClass.READ,
            args=[
                _DURATION_ARG,
                _EVENTS_ARG,
                ArgSpec(
                    name="sort",
                    type=str,
                    required=False,
                    description="Sort key for perf top output, e.g. 'cpu' or 'overhead,dso'.",
                    default="",
                ),
            ],
            description="Show live CPU hotspot data using perf top in stdio mode.",
        ),
        "record": OpSpec(
            op_name="record",
            permission_class=OpClass.WRITE,
            args=[
                _OUTPUT_ARG,
                _EVENTS_ARG,
                _PID_ARG,
                ArgSpec(
                    name="command",
                    type=str,
                    required=False,
                    description="Command to profile (mutually exclusive with pid).",
                    default="",
                ),
                _DURATION_ARG,
            ],
            description="Record perf events to a perf.data file for later analysis.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(PERF_SPEC)
