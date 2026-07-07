"""core/tools/at.py — at/atq/atrm job scheduling tool.

Supported operations
--------------------
  atq       (READ)        — list pending at jobs in the queue.
  schedule  (WRITE)       — schedule a command to run at a given time via at(1).
  atrm      (DESTRUCTIVE) — remove a queued at job by job number.

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
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_atq(args: dict[str, Any]) -> ToolResult:
    """atq [-q <queue>] — list pending at jobs."""
    queue: str = args.get("queue", "")
    cmd = ["atq"]
    if queue:
        cmd += ["-q", queue]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        job_count = len([l for l in result.stdout.splitlines() if l.strip()])
        if job_count == 0:
            summary = "No pending at jobs in the queue."
        else:
            summary = f"Found {job_count} pending at job(s) in the queue."
    else:
        summary = f"Failed to list at jobs (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_schedule(args: dict[str, Any]) -> ToolResult:
    """at <time> — schedule a command to run at a given time (command via stdin)."""
    time_spec: str = args["time"]
    command: str = args["command"]
    result = run_subprocess(["at", time_spec], input=command)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        # at(1) writes "job N at <time>" to stderr on success
        summary = f"Job scheduled to run at '{time_spec}'."
    else:
        summary = f"Failed to schedule job at '{time_spec}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_atrm(args: dict[str, Any]) -> ToolResult:
    """atrm <job_id> — remove a queued at job."""
    job_id: str = args["job_id"]
    result = run_subprocess(["atrm", job_id])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"At job {job_id} removed from the queue."
    else:
        summary = f"Failed to remove at job {job_id} (exit {result.exit_code})."
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
    "atq": _op_atq,
    "schedule": _op_schedule,
    "atrm": _op_atrm,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an at operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for at tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

AT_SPEC = ToolSpec(
    name="at",
    description="Schedule, list, and remove one-off deferred jobs using at(1), atq(1), and atrm(1).",
    ops={
        "atq": OpSpec(
            op_name="atq",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="queue",
                    type=str,
                    required=False,
                    description="Optional queue letter (a–z) to filter the job list.",
                    default="",
                ),
            ],
            description="List pending at jobs in the spool queue.",
        ),
        "schedule": OpSpec(
            op_name="schedule",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="time",
                    type=str,
                    required=True,
                    description=(
                        "Time specification accepted by at(1) — e.g. 'now + 1 hour', "
                        "'22:30', 'midnight', 'noon tomorrow'."
                    ),
                ),
                ArgSpec(
                    name="command",
                    type=str,
                    required=True,
                    description="Shell command to run at the given time.",
                ),
            ],
            description="Schedule a one-off command to run at a specified time.",
        ),
        "atrm": OpSpec(
            op_name="atrm",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="job_id",
                    type=str,
                    required=True,
                    description="Job number to remove, as shown by atq.",
                ),
            ],
            description="Remove a queued at job by job number (irreversible).",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(AT_SPEC)
