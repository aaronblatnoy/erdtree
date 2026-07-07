"""core/tools/chrony.py — NTP clock synchronisation management via chronyc and chronyd.

Supported operations
--------------------
  tracking   (READ)  — show current clock tracking statistics via chronyc.
  sources    (READ)  — list configured NTP sources and their reachability.
  status     (READ)  — show the systemd status of the chronyd daemon.
  makestep   (WRITE) — immediately step the system clock to the NTP reference.
  conf_view  (READ)  — display the active /etc/chrony.conf configuration.
  conf_edit  (WRITE) — overwrite /etc/chrony.conf with supplied content.

Permission mapping:
  READ  : tracking, sources, status, conf_view
  WRITE : makestep, conf_edit

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
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_tracking(args: dict[str, Any]) -> ToolResult:
    """chronyc tracking — show current clock tracking statistics."""
    result = run_subprocess(["chronyc", "tracking"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Clock tracking statistics retrieved from chronyc."
    else:
        summary = f"Failed to retrieve clock tracking statistics (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_sources(args: dict[str, Any]) -> ToolResult:
    """chronyc sources — list NTP sources and their reachability."""
    result = run_subprocess(["chronyc", "sources"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "NTP source list retrieved from chronyc."
    else:
        summary = f"Failed to retrieve NTP source list (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status --no-pager chronyd — show chronyd daemon status."""
    result = run_subprocess(["systemctl", "status", "--no-pager", "chronyd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "chronyd service is active and running."
    else:
        summary = f"chronyd service reported a non-zero status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_makestep(args: dict[str, Any]) -> ToolResult:
    """chronyc makestep — step the system clock immediately to NTP reference."""
    result = run_subprocess(["chronyc", "makestep"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "System clock stepped to the NTP reference time."
    else:
        summary = f"Clock step failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_conf_view(args: dict[str, Any]) -> ToolResult:
    """cat /etc/chrony.conf — display the active chrony configuration."""
    result = run_subprocess(["cat", "/etc/chrony.conf"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Contents of /etc/chrony.conf retrieved."
    else:
        summary = f"Failed to read /etc/chrony.conf (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_conf_edit(args: dict[str, Any]) -> ToolResult:
    """tee /etc/chrony.conf — overwrite chrony.conf with the supplied content."""
    content: str = args["content"]
    result = run_subprocess(["tee", "/etc/chrony.conf"], input=content)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Configuration written to /etc/chrony.conf."
    else:
        summary = f"Failed to write /etc/chrony.conf (exit {result.exit_code})."
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
    "tracking": _op_tracking,
    "sources": _op_sources,
    "status": _op_status,
    "makestep": _op_makestep,
    "conf_view": _op_conf_view,
    "conf_edit": _op_conf_edit,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a chrony operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record. This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for chrony tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

CHRONY_SPEC = ToolSpec(
    name="chrony",
    description="Manage NTP clock synchronisation via chronyc and chronyd.",
    ops={
        "tracking": OpSpec(
            op_name="tracking",
            permission_class=OpClass.READ,
            args=[],
            description="Show current clock tracking statistics.",
        ),
        "sources": OpSpec(
            op_name="sources",
            permission_class=OpClass.READ,
            args=[],
            description="List configured NTP sources and their reachability.",
        ),
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the systemd status of the chronyd daemon.",
        ),
        "makestep": OpSpec(
            op_name="makestep",
            permission_class=OpClass.WRITE,
            args=[],
            description="Immediately step the system clock to the NTP reference time.",
        ),
        "conf_view": OpSpec(
            op_name="conf_view",
            permission_class=OpClass.READ,
            args=[],
            description="Display the contents of /etc/chrony.conf.",
        ),
        "conf_edit": OpSpec(
            op_name="conf_edit",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="content",
                    type=str,
                    required=True,
                    description="Full text content to write to /etc/chrony.conf.",
                ),
            ],
            description="Overwrite /etc/chrony.conf with the supplied configuration text.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(CHRONY_SPEC)
