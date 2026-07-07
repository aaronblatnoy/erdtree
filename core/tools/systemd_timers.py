"""core/tools/systemd_timers.py — systemd timer unit management via systemctl and systemd-run.

Supported operations
--------------------
  list-timers   (READ)  — list all timer units and their next/last trigger times.
  timer-show    (READ)  — show properties of a specific timer unit.
  create        (WRITE) — install a timer unit file to /etc/systemd/system/ and reload.
  enable        (WRITE) — enable a timer unit at boot.
  disable       (WRITE) — disable a timer unit from starting at boot.
  systemd-run   (WRITE) — schedule a one-shot transient command via systemd-run.

Permission mapping:
  READ        : list-timers, timer-show
  WRITE       : create, enable, disable, systemd-run

Note: no DESTRUCTIVE verbs exist for this tool. disable/stop are recoverable.
A disabled timer can be re-enabled; a removed unit file can be recreated.

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
# SELinux hint detection (copy verbatim from services.py)
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

_TIMER_ARG = ArgSpec(
    name="timer",
    type=str,
    required=True,
    description="The systemd timer unit name (e.g. 'backup.timer', 'logrotate.timer').",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list_timers(args: dict[str, Any]) -> ToolResult:
    """systemctl list-timers --all --no-pager"""
    result = run_subprocess(["systemctl", "list-timers", "--all", "--no-pager"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n")
        summary = f"Timer list retrieved ({line_count} output lines)."
    else:
        summary = f"Failed to list timer units (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_timer_show(args: dict[str, Any]) -> ToolResult:
    """systemctl show <timer> --no-pager"""
    timer: str = args["timer"]
    result = run_subprocess(["systemctl", "show", timer, "--no-pager"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Properties for timer unit '{timer}' retrieved."
    else:
        summary = f"Failed to show properties for timer '{timer}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_create(args: dict[str, Any]) -> ToolResult:
    """Write a timer unit file via tee, then run systemctl daemon-reload."""
    timer: str = args["timer"]
    content: str = args["content"]
    unit_path = f"/etc/systemd/system/{timer}"
    # Write unit file via tee (stdin → file); run_subprocess supports input=
    write_result = run_subprocess(
        ["tee", unit_path],
        input=content,
    )
    selinux = _maybe_selinux_hint(write_result.stderr)
    if not write_result.ok:
        summary = f"Failed to write timer unit '{timer}' (exit {write_result.exit_code})."
        return ToolResult(
            exit_code=write_result.exit_code,
            stdout=write_result.stdout,
            stderr=write_result.stderr,
            summary=summary + selinux,
        )
    # Reload systemd so it picks up the new unit
    reload_result = run_subprocess(["systemctl", "daemon-reload"])
    selinux2 = _maybe_selinux_hint(reload_result.stderr)
    if reload_result.ok:
        summary = f"Timer unit '{timer}' created at '{unit_path}' and systemd reloaded."
    else:
        summary = (
            f"Timer unit '{timer}' written but daemon-reload failed "
            f"(exit {reload_result.exit_code})."
        )
    return ToolResult(
        exit_code=reload_result.exit_code,
        stdout=write_result.stdout + reload_result.stdout,
        stderr=write_result.stderr + reload_result.stderr,
        summary=summary + selinux + selinux2,
    )


def _op_enable(args: dict[str, Any]) -> ToolResult:
    """systemctl enable <timer>"""
    timer: str = args["timer"]
    result = run_subprocess(["systemctl", "enable", timer])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Timer unit '{timer}' enabled at boot."
    else:
        summary = f"Failed to enable timer '{timer}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_disable(args: dict[str, Any]) -> ToolResult:
    """systemctl disable <timer>"""
    timer: str = args["timer"]
    result = run_subprocess(["systemctl", "disable", timer])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Timer unit '{timer}' disabled; it will not start automatically at boot."
    else:
        summary = f"Failed to disable timer '{timer}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_systemd_run(args: dict[str, Any]) -> ToolResult:
    """systemd-run [--unit=<name>] [--on-calendar=<spec>] <command...>"""
    command: str = args["command"]
    unit_name: str = args.get("unit_name") or ""
    on_calendar: str = args.get("on_calendar") or ""

    cmd: list[str] = ["systemd-run"]
    if unit_name:
        cmd += ["--unit", unit_name]
    if on_calendar:
        cmd += [f"--on-calendar={on_calendar}"]
    # Append the command tokens; split on whitespace for simple argv construction
    cmd += command.split()

    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        label = unit_name or "transient"
        summary = f"One-shot command scheduled via systemd-run as '{label}' unit."
    else:
        summary = f"systemd-run failed to schedule command (exit {result.exit_code})."
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
    "list-timers": _op_list_timers,
    "timer-show":  _op_timer_show,
    "create":      _op_create,
    "enable":      _op_enable,
    "disable":     _op_disable,
    "systemd-run": _op_systemd_run,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a systemd_timers operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9): unknown ops and all subprocess failures degrade
    gracefully to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for systemd_timers tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

SYSTEMD_TIMERS_SPEC = ToolSpec(
    name="systemd_timers",
    description="Manage systemd timer units via systemctl and schedule one-shot commands via systemd-run.",
    ops={
        "list-timers": OpSpec(
            op_name="list-timers",
            permission_class=OpClass.READ,
            args=[],
            description="List all timer units with their next and last trigger times.",
        ),
        "timer-show": OpSpec(
            op_name="timer-show",
            permission_class=OpClass.READ,
            args=[_TIMER_ARG],
            description="Show the properties of a specific timer unit.",
        ),
        "create": OpSpec(
            op_name="create",
            permission_class=OpClass.WRITE,
            args=[
                _TIMER_ARG,
                ArgSpec(
                    name="content",
                    type=str,
                    required=True,
                    description="Full content of the .timer unit file to install.",
                ),
            ],
            description="Install a new timer unit file and reload systemd.",
        ),
        "enable": OpSpec(
            op_name="enable",
            permission_class=OpClass.WRITE,
            args=[_TIMER_ARG],
            description="Enable a timer unit to start at boot.",
        ),
        "disable": OpSpec(
            op_name="disable",
            permission_class=OpClass.WRITE,
            args=[_TIMER_ARG],
            description="Disable a timer unit from starting at boot.",
        ),
        "systemd-run": OpSpec(
            op_name="systemd-run",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="command",
                    type=str,
                    required=True,
                    description="The command to run as a transient systemd unit.",
                ),
                ArgSpec(
                    name="unit_name",
                    type=str,
                    required=False,
                    description="Optional name for the transient unit.",
                    default=None,
                ),
                ArgSpec(
                    name="on_calendar",
                    type=str,
                    required=False,
                    description="Optional calendar schedule (e.g. 'daily', '*-*-* 02:00:00').",
                    default=None,
                ),
            ],
            description="Schedule a one-shot command as a transient systemd unit.",
        ),
    },
    execute=_execute,
)

# Self-register at import time (LAST line)
registry.register(SYSTEMD_TIMERS_SPEC)
