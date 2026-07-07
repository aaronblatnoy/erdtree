"""core/tools/hostname.py — hostname and /etc/hosts management via hostnamectl and system utilities.

Supported operations
--------------------
  status      (READ)  — show the current hostname and related system identity info.
  set-hostname (WRITE) — set the system hostname persistently via hostnamectl.
  hosts-view  (READ)  — display the contents of /etc/hosts.
  hosts-edit  (WRITE) — append an entry to /etc/hosts (e.g. "192.168.1.10 myhost.local").

Permission mapping:
  READ  : status, hosts-view
  WRITE : set-hostname, hosts-edit

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
# SELinux hint detection (copied VERBATIM from services.py)
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
    """hostnamectl status — show hostname and system identity."""
    result = run_subprocess(["hostnamectl", "status"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "System hostname and identity information retrieved."
    else:
        summary = f"Failed to retrieve hostname status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_hostname(args: dict[str, Any]) -> ToolResult:
    """hostnamectl set-hostname <name> — set the system hostname."""
    name: str = args["name"]
    result = run_subprocess(["hostnamectl", "set-hostname", name])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"System hostname set to '{name}'."
    else:
        summary = f"Failed to set hostname to '{name}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_hosts_view(args: dict[str, Any]) -> ToolResult:
    """cat /etc/hosts — display the current hosts file."""
    result = run_subprocess(["cat", "/etc/hosts"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n")
        summary = f"Hosts file contains {line_count} lines."
    else:
        summary = f"Failed to read /etc/hosts (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_hosts_edit(args: dict[str, Any]) -> ToolResult:
    """Append an entry to /etc/hosts via tee -a."""
    entry: str = args["entry"]
    # Ensure the entry ends with a newline so it appends cleanly.
    if not entry.endswith("\n"):
        entry = entry + "\n"
    result = run_subprocess(["tee", "-a", "/etc/hosts"], input=entry)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Appended entry to /etc/hosts: '{args['entry'].strip()}'."
    else:
        summary = f"Failed to append entry to /etc/hosts (exit {result.exit_code})."
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
    "set-hostname": _op_set_hostname,
    "hosts-view": _op_hosts_view,
    "hosts-edit": _op_hosts_edit,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a hostname operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9). Unknown ops degrade to a ToolResult with
    exit_code=1 so the caller always gets a well-formed response.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for hostname tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_NAME_ARG = ArgSpec(
    name="name",
    type=str,
    required=True,
    description="The new hostname to set (e.g. 'webserver-01.example.com').",
)

_ENTRY_ARG = ArgSpec(
    name="entry",
    type=str,
    required=True,
    description=(
        "A hosts file entry line to append (e.g. '192.168.1.10 myhost.local myhost')."
    ),
)

HOSTNAME_SPEC = ToolSpec(
    name="hostname",
    description="Manage system hostname and /etc/hosts entries via hostnamectl.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current system hostname and identity information.",
        ),
        "set-hostname": OpSpec(
            op_name="set-hostname",
            permission_class=OpClass.WRITE,
            args=[_NAME_ARG],
            description="Set the system hostname persistently.",
        ),
        "hosts-view": OpSpec(
            op_name="hosts-view",
            permission_class=OpClass.READ,
            args=[],
            description="Display the contents of /etc/hosts.",
        ),
        "hosts-edit": OpSpec(
            op_name="hosts-edit",
            permission_class=OpClass.WRITE,
            args=[_ENTRY_ARG],
            description="Append an entry line to /etc/hosts.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(HOSTNAME_SPEC)
