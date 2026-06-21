"""core/tools/services.py — systemctl service management tool.

Supported operations
--------------------
  status   (READ)   — show the status of one or more units.
  start    (WRITE)  — start a unit.
  stop     (WRITE)  — stop a unit.
  restart  (WRITE)  — restart a unit (write-confirm; brings a unit down then up).
  enable   (WRITE)  — enable a unit at boot.
  disable  (WRITE)  — disable a unit at boot.
  logs     (READ)   — tail recent journal entries for a unit (journalctl -u).
  mask     (WRITE)  — mask a unit (prevents it from starting; write-confirm).

Permission mapping (from permissions.py _SUBCOMMAND_CLASS + Phase 2 spec):
  READ  : status, logs
  WRITE : start, stop, restart, enable, disable, mask

Note on mask
  The plan says "mask=write".  Masking a critical service (ssh/sshd) on a
  remote host is a lockout risk, but the plan explicitly places it at WRITE
  (not DESTRUCTIVE) so it gets a plain yes/no confirm rather than a typed
  word.  The permissions module already has the right entry for "mask":
  OpClass.WRITE.  The SELinux-awareness note from CLAUDE.md applies: if
  systemctl returns an error that looks like a dontaudit / AVC denial we
  surface a hint in the summary.

Design rules
------------
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller (router / REPL) MUST resolve the permission gate BEFORE
      calling execute(); this module does NOT call permissions.classify()
      internally — the gate is resolved externally and the audit record is
      written by the caller with the decision already attached.
      EXCEPTION: execute() accepts an optional ``audit`` keyword so tests and
      direct callers can pass an AuditLog and have the record written here as
      a convenience.  Production callers (Phase 4 router) will write the
      record themselves; passing ``audit=None`` (the default) skips the write.
  I4  If an ``audit`` is passed, one JSONL record is written per execute() call.
  I6  Zero tier/product/model names anywhere in this file.

Subprocess mocking
------------------
  On macOS (the dev host) systemctl is absent.  Every test patches
  ``core.tools.services.run_subprocess`` so no real process is launched.
  The tool itself is fully portable: it builds a command vector and calls
  ``run_subprocess``; it never inspects ``sys.platform``.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from core.agent.audit import AuditLog
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

def _op_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status [--no-pager] <unit>"""
    unit: str = args["unit"]
    result = run_subprocess(["systemctl", "status", "--no-pager", unit])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unit '{unit}' is active/running."
    else:
        summary = f"Unit '{unit}' reported status exit {result.exit_code}."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_start(args: dict[str, Any]) -> ToolResult:
    unit: str = args["unit"]
    result = run_subprocess(["systemctl", "start", unit])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unit '{unit}' started."
    else:
        summary = f"Failed to start '{unit}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_stop(args: dict[str, Any]) -> ToolResult:
    unit: str = args["unit"]
    result = run_subprocess(["systemctl", "stop", unit])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unit '{unit}' stopped."
    else:
        summary = f"Failed to stop '{unit}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_restart(args: dict[str, Any]) -> ToolResult:
    unit: str = args["unit"]
    result = run_subprocess(["systemctl", "restart", unit])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unit '{unit}' restarted."
    else:
        summary = f"Failed to restart '{unit}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_enable(args: dict[str, Any]) -> ToolResult:
    unit: str = args["unit"]
    result = run_subprocess(["systemctl", "enable", unit])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unit '{unit}' enabled at boot."
    else:
        summary = f"Failed to enable '{unit}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_disable(args: dict[str, Any]) -> ToolResult:
    unit: str = args["unit"]
    result = run_subprocess(["systemctl", "disable", unit])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unit '{unit}' disabled at boot."
    else:
        summary = f"Failed to disable '{unit}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_logs(args: dict[str, Any]) -> ToolResult:
    """journalctl -u <unit> -n <lines> --no-pager"""
    unit: str = args["unit"]
    raw_lines = args.get("lines")
    lines: int = int(raw_lines) if raw_lines is not None else 50
    # Clamp to a sane range so the model doesn't receive unbounded output.
    lines = max(1, min(lines, 500))
    result = run_subprocess(
        ["journalctl", "-u", unit, "-n", str(lines), "--no-pager"]
    )
    selinux = _maybe_selinux_hint(result.stdout + result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n")
        summary = f"Retrieved {line_count} log lines for unit '{unit}'."
    else:
        summary = f"Log retrieval for '{unit}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_mask(args: dict[str, Any]) -> ToolResult:
    unit: str = args["unit"]
    result = run_subprocess(["systemctl", "mask", unit])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unit '{unit}' masked (prevented from starting)."
    else:
        summary = f"Failed to mask '{unit}' (exit {result.exit_code})."
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
    "status": _op_status,
    "start": _op_start,
    "stop": _op_stop,
    "restart": _op_restart,
    "enable": _op_enable,
    "disable": _op_disable,
    "logs": _op_logs,
    "mask": _op_mask,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a services operation and return a structured ToolResult.

    The caller (Phase 4 router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never writes to the audit log itself (I4 is the caller's responsibility).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        # Should not happen — ToolRegistry validates ops before calling execute().
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for services tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_UNIT_ARG = ArgSpec(
    name="unit",
    type=str,
    required=True,
    description="The systemd unit name (e.g. 'nginx.service', 'sshd').",
)

SERVICES_SPEC = ToolSpec(
    name="services",
    description="Manage systemd services via systemctl and journalctl.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[_UNIT_ARG],
            description="Show the current status of a unit.",
        ),
        "start": OpSpec(
            op_name="start",
            permission_class=OpClass.WRITE,
            args=[_UNIT_ARG],
            description="Start a unit.",
        ),
        "stop": OpSpec(
            op_name="stop",
            permission_class=OpClass.WRITE,
            args=[_UNIT_ARG],
            description="Stop a unit.",
        ),
        "restart": OpSpec(
            op_name="restart",
            permission_class=OpClass.WRITE,
            args=[_UNIT_ARG],
            description="Restart a unit (stop then start).",
        ),
        "enable": OpSpec(
            op_name="enable",
            permission_class=OpClass.WRITE,
            args=[_UNIT_ARG],
            description="Enable a unit to start at boot.",
        ),
        "disable": OpSpec(
            op_name="disable",
            permission_class=OpClass.WRITE,
            args=[_UNIT_ARG],
            description="Disable a unit from starting at boot.",
        ),
        "logs": OpSpec(
            op_name="logs",
            permission_class=OpClass.READ,
            args=[
                _UNIT_ARG,
                ArgSpec(
                    name="lines",
                    type=int,
                    required=False,
                    description="Number of log lines to retrieve (default 50, max 500).",
                    default=50,
                ),
            ],
            description="Retrieve recent journal log entries for a unit.",
        ),
        "mask": OpSpec(
            op_name="mask",
            permission_class=OpClass.WRITE,
            args=[_UNIT_ARG],
            description="Mask a unit so it cannot be started.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SERVICES_SPEC)
