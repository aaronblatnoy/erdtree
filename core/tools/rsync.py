"""core/tools/rsync.py — file synchronisation and transfer tool via rsync.

Supported operations
--------------------
  dry-run      (READ)        — preview which files would be transferred, no changes made.
  sync         (WRITE)       — copy/synchronise files from source to destination.
  sync-delete  (DESTRUCTIVE) — sync and remove destination files absent from source.
  progress     (READ)        — show estimated transfer size and statistics without copying.

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
# Shared arg specs
# ---------------------------------------------------------------------------

_SRC_ARG = ArgSpec(
    name="src",
    type=str,
    required=True,
    description="Source path (local directory or file, e.g. '/data/backups/').",
)

_DEST_ARG = ArgSpec(
    name="dest",
    type=str,
    required=True,
    description="Destination path (local directory or file, e.g. '/mnt/archive/').",
)

# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------


def _op_dry_run(args: dict[str, Any]) -> ToolResult:
    """rsync --dry-run --itemize-changes <src> <dest>"""
    src: str = args["src"]
    dest: str = args["dest"]
    result = run_subprocess(["rsync", "--dry-run", "--itemize-changes", src, dest])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        changed = sum(1 for line in result.stdout.splitlines() if line.strip())
        summary = f"Dry run complete: {changed} file(s) would be transferred from '{src}' to '{dest}'."
    else:
        summary = (
            f"Dry run from '{src}' to '{dest}' failed (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_sync(args: dict[str, Any]) -> ToolResult:
    """rsync -a <src> <dest>"""
    src: str = args["src"]
    dest: str = args["dest"]
    result = run_subprocess(["rsync", "-a", src, dest], timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Sync from '{src}' to '{dest}' completed successfully."
    else:
        summary = (
            f"Sync from '{src}' to '{dest}' failed (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_sync_delete(args: dict[str, Any]) -> ToolResult:
    """rsync -a --delete <src> <dest>  (DESTRUCTIVE — removes extraneous destination files)"""
    src: str = args["src"]
    dest: str = args["dest"]
    result = run_subprocess(["rsync", "-a", "--delete", src, dest], timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Sync with delete from '{src}' to '{dest}' completed; "
            "files absent from source were removed from destination."
        )
    else:
        summary = (
            f"Sync with delete from '{src}' to '{dest}' failed (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_progress(args: dict[str, Any]) -> ToolResult:
    """rsync --dry-run --progress --stats <src> <dest>"""
    src: str = args["src"]
    dest: str = args["dest"]
    result = run_subprocess(
        ["rsync", "--dry-run", "--progress", "--stats", src, dest],
        timeout=120,
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Transfer estimate for '{src}' to '{dest}' completed; "
            "see output for file counts and size totals."
        )
    else:
        summary = (
            f"Transfer estimate from '{src}' to '{dest}' failed (exit {result.exit_code})."
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
    "dry-run": _op_dry_run,
    "sync": _op_sync,
    "sync-delete": _op_sync_delete,
    "progress": _op_progress,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------


def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an rsync operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record. This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for rsync tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

RSYNC_SPEC = ToolSpec(
    name="rsync",
    description="Synchronise files and directories between local paths using rsync.",
    ops={
        "dry-run": OpSpec(
            op_name="dry-run",
            permission_class=OpClass.READ,
            args=[_SRC_ARG, _DEST_ARG],
            description="Preview which files would be transferred without making any changes.",
        ),
        "sync": OpSpec(
            op_name="sync",
            permission_class=OpClass.WRITE,
            args=[_SRC_ARG, _DEST_ARG],
            description="Copy and synchronise files from source to destination (archive mode).",
        ),
        "sync-delete": OpSpec(
            op_name="sync-delete",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_SRC_ARG, _DEST_ARG],
            description=(
                "Sync files and remove destination files absent from source (--delete). "
                "Irreversible: files deleted from destination cannot be recovered."
            ),
        ),
        "progress": OpSpec(
            op_name="progress",
            permission_class=OpClass.READ,
            args=[_SRC_ARG, _DEST_ARG],
            description="Show estimated transfer size and file counts without copying any data.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(RSYNC_SPEC)
