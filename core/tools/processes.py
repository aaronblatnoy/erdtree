"""core/tools/processes.py — Process inspection and management tool.

Supported operations
--------------------
  list    (READ)   — list running processes (ps).
  tree    (READ)   — display process tree (ps with ppid / pstree).
  top     (READ)   — snapshot CPU/memory-sorted process list (ps aux --sort).
  info    (READ)   — detailed info on a single PID (ps -p <pid>).
  signal  (WRITE)  — send a signal to a PID ("kill <pid>").  NOTE: when the
                     signal number is -1 (kill all) the synthesized command is
                     "kill -1 <pid>" which the classifier escalates to
                     DESTRUCTIVE (see permissions.py _classify_argv, kill/-1).
  renice  (WRITE)  — change the scheduling priority of a PID (renice).

Permission mapping:
  READ  : list, tree, top, info
  WRITE : signal, renice

Design rules
------------
  I1  No network calls.  All ops shell out via run_subprocess only.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller (REPL) resolves the permission gate BEFORE calling execute().
      This module never calls permissions.classify() internally.
  I4  The caller writes the audit record; this module does not.
  I6  Zero tier/product/model names anywhere in this file.

Subprocess mocking
------------------
  On this dev host ps/kill/renice may differ from Rocky Linux 9.  Every test
  patches ``core.tools.processes.run_subprocess`` so no real process is launched.
"""

from __future__ import annotations

import re
from typing import Any, Optional

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

def _op_list(args: dict[str, Any]) -> ToolResult:
    """ps aux — list all running processes."""
    result = run_subprocess(["ps", "aux"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = max(0, result.stdout.count("\n") - 1)  # subtract header
        summary = f"Listed {line_count} running processes."
    else:
        summary = f"Process list failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_tree(args: dict[str, Any]) -> ToolResult:
    """ps -ejH — show process tree with hierarchy."""
    result = run_subprocess(["ps", "-ejH"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = max(0, result.stdout.count("\n") - 1)
        summary = f"Process tree captured ({line_count} entries)."
    else:
        summary = f"Process tree failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_top(args: dict[str, Any]) -> ToolResult:
    """ps aux --sort=-%cpu — snapshot sorted by CPU usage."""
    result = run_subprocess(["ps", "aux", "--sort=-%cpu"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = max(0, result.stdout.count("\n") - 1)
        summary = f"Top {line_count} processes by CPU captured."
    else:
        summary = f"Process snapshot failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_info(args: dict[str, Any]) -> ToolResult:
    """ps -p <pid> -o pid,ppid,user,stat,pcpu,pmem,comm,args — single-PID detail."""
    pid: str = str(args["pid"])
    result = run_subprocess(
        ["ps", "-p", pid, "-o", "pid,ppid,user,stat,pcpu,pmem,comm,args"]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Process info for PID {pid} retrieved."
    else:
        summary = f"No process found for PID {pid} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_signal(args: dict[str, Any]) -> ToolResult:
    """kill [-<signal>] <pid> — send a signal to a process.

    IMPORTANT: If signal_num is -1 the synthesized command string must be
    "kill -1 <pid>" so the EXISTING classifier (_classify_argv) sees the
    -1 token and escalates to DESTRUCTIVE / CONFIRM_TYPED.  The REPL's
    synthesize_command() is responsible for building that string; this
    execute() function just runs the subprocess.
    """
    pid: str = str(args["pid"])
    sig: Optional[int] = args.get("signal_num")
    selinux_hint = ""

    if sig is not None:
        # Pass signal as "-<n>" for positive values (e.g. -9 for SIGKILL).
        # For negative values like -1 (kill-all), sig is already negative so
        # we use str(sig) directly: str(-1) = "-1" (not "--1").
        sig_flag = str(sig) if sig < 0 else f"-{sig}"
        result = run_subprocess(["kill", sig_flag, pid])
    else:
        result = run_subprocess(["kill", pid])

    selinux_hint = _maybe_selinux_hint(result.stderr)
    if result.ok:
        sig_label = f"-{sig}" if sig is not None else "TERM"
        summary = f"Signal {sig_label} sent to PID {pid}."
    else:
        summary = f"Signal to PID {pid} failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux_hint,
    )


def _op_renice(args: dict[str, Any]) -> ToolResult:
    """renice <priority> -p <pid> — change process scheduling priority."""
    pid: str = str(args["pid"])
    priority: int = int(args["priority"])
    # Clamp priority to the valid nice range [-20, 19].
    priority = max(-20, min(19, priority))
    result = run_subprocess(["renice", str(priority), "-p", pid])
    selinux_hint = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Priority of PID {pid} set to {priority}."
    else:
        summary = f"renice for PID {pid} failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux_hint,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "list": _op_list,
    "tree": _op_tree,
    "top": _op_top,
    "info": _op_info,
    "signal": _op_signal,
    "renice": _op_renice,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a processes operation and return a structured ToolResult.

    The caller (REPL / router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never writes to the audit log itself.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for processes tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_PID_ARG = ArgSpec(
    name="pid",
    type=int,
    required=True,
    description="The process ID (PID) to target.",
)

PROCESSES_SPEC = ToolSpec(
    name="processes",
    description="Inspect and manage running processes via ps, kill, and renice.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[],
            description="List all running processes.",
        ),
        "tree": OpSpec(
            op_name="tree",
            permission_class=OpClass.READ,
            args=[],
            description="Show the process hierarchy tree.",
        ),
        "top": OpSpec(
            op_name="top",
            permission_class=OpClass.READ,
            args=[],
            description="Snapshot processes sorted by CPU usage.",
        ),
        "info": OpSpec(
            op_name="info",
            permission_class=OpClass.READ,
            args=[_PID_ARG],
            description="Show detailed information for a single process by PID.",
        ),
        "signal": OpSpec(
            op_name="signal",
            permission_class=OpClass.WRITE,
            args=[
                _PID_ARG,
                ArgSpec(
                    name="signal_num",
                    type=int,
                    required=False,
                    description=(
                        "Signal number to send (e.g. 9 for SIGKILL, 15 for SIGTERM). "
                        "Default: SIGTERM (15). WARNING: signal_num=-1 targets all "
                        "processes and is treated as DESTRUCTIVE."
                    ),
                    default=None,
                ),
            ],
            description="Send a signal to a process by PID.",
        ),
        "renice": OpSpec(
            op_name="renice",
            permission_class=OpClass.WRITE,
            args=[
                _PID_ARG,
                ArgSpec(
                    name="priority",
                    type=int,
                    required=True,
                    description="New nice value in range [-20, 19] (lower = higher priority).",
                ),
            ],
            description="Change the scheduling priority of a process by PID.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(PROCESSES_SPEC)
