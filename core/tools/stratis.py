"""core/tools/stratis.py — Stratis storage pool and filesystem management tool.

Supported operations
--------------------
  pool-list        (READ)        — list all Stratis storage pools.
  pool-create      (WRITE)       — create a new Stratis pool from one or more block devices.
  pool-destroy     (DESTRUCTIVE) — destroy a Stratis pool and all its filesystems.
  filesystem-list  (READ)        — list filesystems in a Stratis pool.
  filesystem-create (WRITE)      — create a new filesystem in a Stratis pool.
  filesystem-snapshot (WRITE)   — create a snapshot of a Stratis filesystem.
  filesystem-destroy (DESTRUCTIVE) — destroy a Stratis filesystem.

Permission mapping (from Phase-3 plan table):
  READ        : pool-list, filesystem-list
  WRITE       : pool-create, filesystem-create, filesystem-snapshot
  DESTRUCTIVE : pool-destroy, filesystem-destroy

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
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_POOL_ARG = ArgSpec(
    name="pool",
    type=str,
    required=True,
    description="The Stratis pool name.",
)

_FS_ARG = ArgSpec(
    name="filesystem",
    type=str,
    required=True,
    description="The Stratis filesystem name.",
)

# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------


def _op_pool_list(args: dict[str, Any]) -> ToolResult:
    """stratis pool list"""
    result = run_subprocess(["stratis", "pool", "list"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Stratis pool list retrieved successfully."
    else:
        summary = f"Failed to list Stratis pools (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pool_create(args: dict[str, Any]) -> ToolResult:
    """stratis pool create <pool> <blockdev> [blockdev ...]"""
    pool: str = args["pool"]
    blockdev: str = args["blockdev"]
    cmd = ["stratis", "pool", "create", pool, blockdev]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Stratis pool '{pool}' created on device '{blockdev}'."
    else:
        summary = f"Failed to create Stratis pool '{pool}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pool_destroy(args: dict[str, Any]) -> ToolResult:
    """stratis pool destroy <pool>  [DESTRUCTIVE — erases all filesystems in the pool]"""
    pool: str = args["pool"]
    result = run_subprocess(["stratis", "pool", "destroy", pool])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Stratis pool '{pool}' destroyed; all its filesystems and data have been removed."
    else:
        summary = f"Failed to destroy Stratis pool '{pool}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_filesystem_list(args: dict[str, Any]) -> ToolResult:
    """stratis filesystem list [<pool>]"""
    pool: str = args.get("pool", "")
    cmd = ["stratis", "filesystem", "list"]
    if pool:
        cmd.append(pool)
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        if pool:
            summary = f"Stratis filesystems in pool '{pool}' retrieved."
        else:
            summary = "Stratis filesystem list retrieved successfully."
    else:
        if pool:
            summary = f"Failed to list filesystems in Stratis pool '{pool}' (exit {result.exit_code})."
        else:
            summary = f"Failed to list Stratis filesystems (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_filesystem_create(args: dict[str, Any]) -> ToolResult:
    """stratis filesystem create <pool> <filesystem>"""
    pool: str = args["pool"]
    filesystem: str = args["filesystem"]
    result = run_subprocess(["stratis", "filesystem", "create", pool, filesystem])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Stratis filesystem '{filesystem}' created in pool '{pool}'."
    else:
        summary = f"Failed to create filesystem '{filesystem}' in pool '{pool}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_filesystem_snapshot(args: dict[str, Any]) -> ToolResult:
    """stratis filesystem snapshot <pool> <filesystem> <snapshot>"""
    pool: str = args["pool"]
    filesystem: str = args["filesystem"]
    snapshot: str = args["snapshot"]
    result = run_subprocess(
        ["stratis", "filesystem", "snapshot", pool, filesystem, snapshot]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Snapshot '{snapshot}' created from filesystem '{filesystem}' in pool '{pool}'."
        )
    else:
        summary = (
            f"Failed to create snapshot '{snapshot}' from '{filesystem}' in pool '{pool}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_filesystem_destroy(args: dict[str, Any]) -> ToolResult:
    """stratis filesystem destroy <pool> <filesystem>  [DESTRUCTIVE — erases filesystem data]"""
    pool: str = args["pool"]
    filesystem: str = args["filesystem"]
    result = run_subprocess(["stratis", "filesystem", "destroy", pool, filesystem])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Stratis filesystem '{filesystem}' in pool '{pool}' destroyed; data has been removed."
    else:
        summary = (
            f"Failed to destroy filesystem '{filesystem}' in pool '{pool}' "
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
    "pool-list": _op_pool_list,
    "pool-create": _op_pool_create,
    "pool-destroy": _op_pool_destroy,
    "filesystem-list": _op_filesystem_list,
    "filesystem-create": _op_filesystem_create,
    "filesystem-snapshot": _op_filesystem_snapshot,
    "filesystem-destroy": _op_filesystem_destroy,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------


def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a stratis operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9): unknown ops and subprocess errors both degrade to a
    well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for stratis tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

STRATIS_SPEC = ToolSpec(
    name="stratis",
    description="Manage Stratis storage pools and filesystems via the stratis CLI.",
    ops={
        "pool-list": OpSpec(
            op_name="pool-list",
            permission_class=OpClass.READ,
            args=[],
            description="List all Stratis storage pools.",
        ),
        "pool-create": OpSpec(
            op_name="pool-create",
            permission_class=OpClass.WRITE,
            args=[
                _POOL_ARG,
                ArgSpec(
                    name="blockdev",
                    type=str,
                    required=True,
                    description="Block device path to add to the new pool (e.g. '/dev/sdb').",
                ),
            ],
            description="Create a new Stratis pool on a block device.",
        ),
        "pool-destroy": OpSpec(
            op_name="pool-destroy",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_POOL_ARG],
            description="Destroy a Stratis pool and all its filesystems (data loss).",
        ),
        "filesystem-list": OpSpec(
            op_name="filesystem-list",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="pool",
                    type=str,
                    required=False,
                    description="Pool name to filter by (omit to list all pools).",
                    default=None,
                ),
            ],
            description="List Stratis filesystems, optionally filtered to a specific pool.",
        ),
        "filesystem-create": OpSpec(
            op_name="filesystem-create",
            permission_class=OpClass.WRITE,
            args=[_POOL_ARG, _FS_ARG],
            description="Create a new filesystem in a Stratis pool.",
        ),
        "filesystem-snapshot": OpSpec(
            op_name="filesystem-snapshot",
            permission_class=OpClass.WRITE,
            args=[
                _POOL_ARG,
                _FS_ARG,
                ArgSpec(
                    name="snapshot",
                    type=str,
                    required=True,
                    description="Name for the new snapshot filesystem.",
                ),
            ],
            description="Create a snapshot of a Stratis filesystem.",
        ),
        "filesystem-destroy": OpSpec(
            op_name="filesystem-destroy",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_POOL_ARG, _FS_ARG],
            description="Destroy a Stratis filesystem (data loss).",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(STRATIS_SPEC)
