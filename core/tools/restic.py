"""core/tools/restic.py — restic backup repository management tool.

Supported operations
--------------------
  snapshots    (READ)        — list snapshots stored in a restic repository.
  backup       (WRITE)       — create a new backup snapshot of one or more paths.
  restore      (WRITE)       — restore a snapshot to a target directory.
  forget       (WRITE)       — remove a specific snapshot from the repository.
  forget_prune (DESTRUCTIVE) — remove old snapshots and prune unreferenced pack data.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.

restic ships via EPEL on Rocky Linux 9.  The binary is assumed present when EPEL
is enabled.  A missing binary produces exit_code=127 from run_subprocess
(FileNotFoundError caught internally) and degrades to a plain ToolResult.
Slow operations (backup, restore, forget_prune) use an extended timeout.
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
# Shared arg specs
# ---------------------------------------------------------------------------

_REPO_ARG = ArgSpec(
    name="repo",
    type=str,
    required=False,
    description=(
        "Path or URI of the restic repository "
        "(overrides RESTIC_REPOSITORY env var if set)."
    ),
    default=None,
)

_TAG_ARG = ArgSpec(
    name="tag",
    type=str,
    required=False,
    description="Filter by tag label.",
    default=None,
)

_HOST_ARG = ArgSpec(
    name="host",
    type=str,
    required=False,
    description="Filter by hostname.",
    default=None,
)


def _repo_flags(args: dict[str, Any]) -> list[str]:
    """Return ['--repo', <repo>] when a repo arg is provided, else []."""
    repo = args.get("repo")
    if repo:
        return ["--repo", str(repo)]
    return []


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_snapshots(args: dict[str, Any]) -> ToolResult:
    """restic snapshots [--repo <repo>] [--tag <tag>] [--host <host>]"""
    cmd = ["restic", "snapshots"] + _repo_flags(args)
    tag = args.get("tag")
    if tag:
        cmd += ["--tag", str(tag)]
    host = args.get("host")
    if host:
        cmd += ["--host", str(host)]
    result = run_subprocess(cmd, timeout=60)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Snapshot list retrieved from the repository."
    else:
        summary = f"Failed to list snapshots (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_backup(args: dict[str, Any]) -> ToolResult:
    """restic backup <path> [--repo <repo>] [--tag <tag>]"""
    path: str = args["path"]
    cmd = ["restic", "backup", path] + _repo_flags(args)
    tag = args.get("tag")
    if tag:
        cmd += ["--tag", str(tag)]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Backup of '{path}' completed successfully."
    else:
        summary = f"Backup of '{path}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_restore(args: dict[str, Any]) -> ToolResult:
    """restic restore <snapshot_id> --target <target> [--repo <repo>]"""
    snapshot_id: str = args["snapshot_id"]
    target: str = args["target"]
    cmd = ["restic", "restore", snapshot_id, "--target", target] + _repo_flags(args)
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Snapshot '{snapshot_id}' restored to '{target}'."
    else:
        summary = (
            f"Restore of snapshot '{snapshot_id}' to '{target}' "
            f"failed (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_forget(args: dict[str, Any]) -> ToolResult:
    """restic forget <snapshot_id> [--repo <repo>]

    Removes the named snapshot from the index.  Pack data is NOT pruned;
    run forget_prune to reclaim storage.
    """
    snapshot_id: str = args["snapshot_id"]
    cmd = ["restic", "forget", snapshot_id] + _repo_flags(args)
    result = run_subprocess(cmd, timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Snapshot '{snapshot_id}' removed from the repository index. "
            "Run forget_prune to reclaim disk space."
        )
    else:
        summary = (
            f"Failed to forget snapshot '{snapshot_id}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_forget_prune(args: dict[str, Any]) -> ToolResult:
    """restic forget --prune [--keep-last <n>] [--repo <repo>] [--host <h>] [--tag <t>]

    Removes snapshots according to the retention policy AND immediately prunes
    unreferenced pack data from the repository.  This permanently deletes backup
    data — DESTRUCTIVE.
    """
    cmd = ["restic", "forget", "--prune"] + _repo_flags(args)

    keep_last = args.get("keep_last")
    if keep_last is not None:
        try:
            n = int(keep_last)
        except (TypeError, ValueError):
            n = None
        if n is not None and n > 0:
            cmd += ["--keep-last", str(n)]

    host = args.get("host")
    if host:
        cmd += ["--host", str(host)]

    tag = args.get("tag")
    if tag:
        cmd += ["--tag", str(tag)]

    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            "Snapshots pruned from the repository; "
            "unreferenced pack data permanently removed."
        )
    else:
        summary = f"Prune operation failed (exit {result.exit_code})."
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
    "snapshots":    _op_snapshots,
    "backup":       _op_backup,
    "restore":      _op_restore,
    "forget":       _op_forget,
    "forget_prune": _op_forget_prune,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a restic operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record.  This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for restic tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

RESTIC_SPEC = ToolSpec(
    name="restic",
    description="Manage restic backup repositories: list, create, restore, and prune snapshots.",
    ops={
        "snapshots": OpSpec(
            op_name="snapshots",
            permission_class=OpClass.READ,
            args=[_REPO_ARG, _TAG_ARG, _HOST_ARG],
            description="List all snapshots stored in the repository.",
        ),
        "backup": OpSpec(
            op_name="backup",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="path",
                    type=str,
                    required=True,
                    description="Filesystem path to back up.",
                ),
                _REPO_ARG,
                _TAG_ARG,
            ],
            description="Create a new backup snapshot of the given path.",
        ),
        "restore": OpSpec(
            op_name="restore",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="snapshot_id",
                    type=str,
                    required=True,
                    description="Snapshot ID (short hash or 'latest') to restore.",
                ),
                ArgSpec(
                    name="target",
                    type=str,
                    required=True,
                    description="Directory path where the snapshot will be restored.",
                ),
                _REPO_ARG,
            ],
            description="Restore a snapshot to a target directory.",
        ),
        "forget": OpSpec(
            op_name="forget",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="snapshot_id",
                    type=str,
                    required=True,
                    description="Snapshot ID to remove from the repository index.",
                ),
                _REPO_ARG,
            ],
            description=(
                "Remove a specific snapshot from the repository index. "
                "Pack data is retained until a prune operation runs."
            ),
        ),
        "forget_prune": OpSpec(
            op_name="forget_prune",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="keep_last",
                    type=int,
                    required=False,
                    description="Number of most-recent snapshots to retain.",
                    default=None,
                ),
                _REPO_ARG,
                _HOST_ARG,
                _TAG_ARG,
            ],
            description=(
                "Remove old snapshots per retention policy AND immediately prune "
                "unreferenced pack data — permanently deletes backup data."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration
# ---------------------------------------------------------------------------

registry.register(RESTIC_SPEC)
