"""core/tools/nfs.py — NFS share management via exportfs, showmount, and mount.

Supported operations
--------------------
  showmount        (READ)        — show exports advertised by a remote NFS server.
  exportfs_list    (READ)        — list currently active NFS exports on this host.
  exportfs_add     (WRITE)       — re-read /etc/exports and publish all exports.
  exportfs_unexport (DESTRUCTIVE) — revoke a specific NFS export (access loss).
  exports_view     (READ)        — display /etc/exports configuration.
  nfs_start        (WRITE)       — start the nfs-server systemd service.
  nfs_stop         (WRITE)       — stop the nfs-server systemd service.
  mount_client     (WRITE)       — mount a remote NFS share on this host.

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
# SELinux hint detection (copy VERBATIM from services.py — §4)
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

def _op_showmount(args: dict[str, Any]) -> ToolResult:
    """showmount -e <server> — list exports on a remote NFS server."""
    server: str = args["server"]
    result = run_subprocess(["showmount", "-e", server])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Retrieved NFS export list from '{server}'."
    else:
        summary = (
            f"Could not retrieve exports from '{server}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_exportfs_list(args: dict[str, Any]) -> ToolResult:
    """exportfs -v — list currently active NFS exports on this host."""
    result = run_subprocess(["exportfs", "-v"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Active NFS exports listed successfully."
    else:
        summary = f"Failed to list NFS exports (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_exportfs_add(args: dict[str, Any]) -> ToolResult:
    """exportfs -r — re-read /etc/exports and publish all configured exports."""
    result = run_subprocess(["exportfs", "-r"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "NFS exports reloaded from /etc/exports and published."
    else:
        summary = f"Failed to reload NFS exports (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_exportfs_unexport(args: dict[str, Any]) -> ToolResult:
    """exportfs -u <target> — revoke a specific NFS export (DESTRUCTIVE).

    target: the client:/path specification to unexport, e.g. '192.168.1.0/24:/srv/nfs'.
    Revoking an export cuts off NFS clients that depend on the share.
    """
    target: str = args["target"]
    result = run_subprocess(["exportfs", "-u", target])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"NFS export '{target}' revoked; clients can no longer access this share."
    else:
        summary = (
            f"Failed to revoke NFS export '{target}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_exports_view(args: dict[str, Any]) -> ToolResult:
    """cat /etc/exports — display the NFS exports configuration file."""
    result = run_subprocess(["cat", "/etc/exports"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "NFS exports configuration displayed from /etc/exports."
    else:
        summary = f"Failed to read /etc/exports (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_nfs_start(args: dict[str, Any]) -> ToolResult:
    """systemctl start nfs-server — start the NFS server service."""
    result = run_subprocess(["systemctl", "start", "nfs-server"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "NFS server service started."
    else:
        summary = f"Failed to start the NFS server service (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_nfs_stop(args: dict[str, Any]) -> ToolResult:
    """systemctl stop nfs-server — stop the NFS server service."""
    result = run_subprocess(["systemctl", "stop", "nfs-server"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "NFS server service stopped."
    else:
        summary = f"Failed to stop the NFS server service (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_mount_client(args: dict[str, Any]) -> ToolResult:
    """mount -t nfs <server>:<path> <mountpoint> — mount a remote NFS share."""
    server: str = args["server"]
    path: str = args["path"]
    mountpoint: str = args["mountpoint"]
    source = f"{server}:{path}"
    result = run_subprocess(["mount", "-t", "nfs", source, mountpoint])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"NFS share '{source}' mounted at '{mountpoint}'."
    else:
        summary = (
            f"Failed to mount NFS share '{source}' at '{mountpoint}' "
            f"(exit {result.exit_code})."
        )
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
    "showmount":          _op_showmount,
    "exportfs_list":      _op_exportfs_list,
    "exportfs_add":       _op_exportfs_add,
    "exportfs_unexport":  _op_exportfs_unexport,
    "exports_view":       _op_exports_view,
    "nfs_start":          _op_nfs_start,
    "nfs_stop":           _op_nfs_stop,
    "mount_client":       _op_mount_client,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an NFS operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never writes to the audit log (I4) and never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for nfs tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_SERVER_ARG = ArgSpec(
    name="server",
    type=str,
    required=True,
    description="Hostname or IP address of the NFS server.",
)

NFS_SPEC = ToolSpec(
    name="nfs",
    description="Manage NFS exports and client mounts via exportfs, showmount, and mount.",
    ops={
        "showmount": OpSpec(
            op_name="showmount",
            permission_class=OpClass.READ,
            args=[_SERVER_ARG],
            description="List NFS exports advertised by a remote server.",
        ),
        "exportfs_list": OpSpec(
            op_name="exportfs_list",
            permission_class=OpClass.READ,
            args=[],
            description="List currently active NFS exports on this host.",
        ),
        "exportfs_add": OpSpec(
            op_name="exportfs_add",
            permission_class=OpClass.WRITE,
            args=[],
            description="Re-read /etc/exports and publish all configured NFS exports.",
        ),
        "exportfs_unexport": OpSpec(
            op_name="exportfs_unexport",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="target",
                    type=str,
                    required=True,
                    description=(
                        "Export specification to revoke, e.g. '192.168.1.0/24:/srv/nfs'. "
                        "Revoking cuts off clients that depend on the share."
                    ),
                ),
            ],
            description="Revoke a specific NFS export, cutting off client access to that share.",
        ),
        "exports_view": OpSpec(
            op_name="exports_view",
            permission_class=OpClass.READ,
            args=[],
            description="Display the contents of /etc/exports.",
        ),
        "nfs_start": OpSpec(
            op_name="nfs_start",
            permission_class=OpClass.WRITE,
            args=[],
            description="Start the nfs-server systemd service.",
        ),
        "nfs_stop": OpSpec(
            op_name="nfs_stop",
            permission_class=OpClass.WRITE,
            args=[],
            description="Stop the nfs-server systemd service.",
        ),
        "mount_client": OpSpec(
            op_name="mount_client",
            permission_class=OpClass.WRITE,
            args=[
                _SERVER_ARG,
                ArgSpec(
                    name="path",
                    type=str,
                    required=True,
                    description="Exported path on the NFS server, e.g. '/srv/nfs/data'.",
                ),
                ArgSpec(
                    name="mountpoint",
                    type=str,
                    required=True,
                    description="Local directory to mount the NFS share onto.",
                ),
            ],
            description="Mount a remote NFS share at a local mountpoint.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(NFS_SPEC)
