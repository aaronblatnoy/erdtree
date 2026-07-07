"""core/tools/tuned.py — tuned-adm profile management tool.

Supported operations
--------------------
  list       (READ)  — list all available tuned profiles.
  active     (READ)  — show the currently active tuned profile.
  recommend  (READ)  — show the recommended tuned profile for this system.
  profile    (WRITE) — switch to a named tuned profile.
  off        (WRITE) — disable the active tuned profile (deactivate tuning).

Permission mapping (advisory, per Phase 7 F plan table):
  READ  : list, active, recommend
  WRITE : profile, off

Note on 'off'
  Disabling the active profile is recoverable (re-apply any profile to restore
  tuning). The DESTRUCTIVE-VERB-MANIFEST explicitly labels it WRITE with a note;
  no DESTRUCTIVE OpClass entry is required for tuned.

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
# SELinux hint detection (copy VERBATIM from services.py)
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
    """tuned-adm list — list all available profiles."""
    result = run_subprocess(["tuned-adm", "list"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Available tuned profiles listed successfully."
    else:
        summary = f"Failed to list tuned profiles (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_active(args: dict[str, Any]) -> ToolResult:
    """tuned-adm active — show the currently active profile."""
    result = run_subprocess(["tuned-adm", "active"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Currently active tuned profile retrieved."
    else:
        summary = f"Failed to retrieve active tuned profile (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_recommend(args: dict[str, Any]) -> ToolResult:
    """tuned-adm recommend — show the recommended profile for this system."""
    result = run_subprocess(["tuned-adm", "recommend"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Recommended tuned profile for this system retrieved."
    else:
        summary = f"Failed to retrieve recommended tuned profile (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_profile(args: dict[str, Any]) -> ToolResult:
    """tuned-adm profile <name> — switch to the named profile."""
    profile: str = args["profile"]
    result = run_subprocess(["tuned-adm", "profile", profile])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Tuned profile switched to '{profile}'."
    else:
        summary = f"Failed to switch tuned profile to '{profile}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_off(args: dict[str, Any]) -> ToolResult:
    """tuned-adm off — disable the active tuned profile."""
    result = run_subprocess(["tuned-adm", "off"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Tuned profile deactivated; no profile is now active."
    else:
        summary = f"Failed to deactivate tuned profile (exit {result.exit_code})."
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
    "list":      _op_list,
    "active":    _op_active,
    "recommend": _op_recommend,
    "profile":   _op_profile,
    "off":       _op_off,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a tuned operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9): unknown ops and missing binaries both degrade gracefully.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for tuned tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_PROFILE_ARG = ArgSpec(
    name="profile",
    type=str,
    required=True,
    description="Name of the tuned profile to activate (e.g. 'throughput-performance', 'latency-performance').",
)

TUNED_SPEC = ToolSpec(
    name="tuned",
    description="Manage system performance tuning profiles via tuned-adm.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[],
            description="List all available tuned profiles.",
        ),
        "active": OpSpec(
            op_name="active",
            permission_class=OpClass.READ,
            args=[],
            description="Show the currently active tuned profile.",
        ),
        "recommend": OpSpec(
            op_name="recommend",
            permission_class=OpClass.READ,
            args=[],
            description="Show the recommended tuned profile for this system.",
        ),
        "profile": OpSpec(
            op_name="profile",
            permission_class=OpClass.WRITE,
            args=[_PROFILE_ARG],
            description="Switch the active tuned profile to the specified profile name.",
        ),
        "off": OpSpec(
            op_name="off",
            permission_class=OpClass.WRITE,
            args=[],
            description="Deactivate the current tuned profile; no tuning will be active until a profile is applied.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(TUNED_SPEC)
