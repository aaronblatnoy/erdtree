"""core/tools/tar.py — tar archive management (create, list, extract, verify, compressed variants).

Supported operations
--------------------
  list       (READ)  — list the contents of a tar archive.
  create     (WRITE) — create an uncompressed tar archive from one or more source paths.
  extract    (WRITE) — extract files from a tar archive (optionally to a destination dir).
  verify     (READ)  — compare archive contents against the live filesystem.
  create_gz  (WRITE) — create a gzip-compressed tar archive (.tar.gz / .tgz).
  create_bz2 (WRITE) — create a bzip2-compressed tar archive (.tar.bz2).
  create_xz  (WRITE) — create an xz-compressed tar archive (.tar.xz).

Permission mapping
------------------
  READ  : list, verify
  WRITE : create, extract, create_gz, create_bz2, create_xz

Note on extract (WRITE, not DESTRUCTIVE)
  Extracting over an existing directory tree can overwrite files, but per the
  file-op norm this is WRITE (CONFIRM) rather than DESTRUCTIVE.  The caller's
  permission gate is the authority.

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
# SELinux hint detection (copied VERBATIM per SLICE-CONTRACT §3)
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

_ARCHIVE_ARG = ArgSpec(
    name="archive",
    type=str,
    required=True,
    description="Path to the tar archive file (e.g. '/backup/data.tar.gz').",
)

_SOURCES_ARG = ArgSpec(
    name="sources",
    type=list,
    required=True,
    description="List of source file/directory paths to include in the archive.",
)

_DEST_ARG = ArgSpec(
    name="dest",
    type=str,
    required=False,
    description="Destination directory for extraction (default: current directory).",
    default="",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """tar --list --verbose --file <archive>"""
    archive: str = args["archive"]
    result = run_subprocess(["tar", "--list", "--verbose", "--file", archive])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        file_count = result.stdout.count("\n")
        summary = f"Archive '{archive}' listed successfully ({file_count} entries)."
    else:
        summary = f"Failed to list archive '{archive}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_create(args: dict[str, Any]) -> ToolResult:
    """tar --create --file <archive> <sources...>"""
    archive: str = args["archive"]
    sources: list = args["sources"]
    cmd = ["tar", "--create", "--file", archive] + [str(s) for s in sources]
    result = run_subprocess(cmd, timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Archive '{archive}' created from {len(sources)} source path(s)."
    else:
        summary = f"Failed to create archive '{archive}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_extract(args: dict[str, Any]) -> ToolResult:
    """tar --extract --file <archive> [--directory <dest>]"""
    archive: str = args["archive"]
    dest: str = args.get("dest") or ""
    cmd = ["tar", "--extract", "--file", archive]
    if dest:
        cmd += ["--directory", dest]
    result = run_subprocess(cmd, timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    dest_label = dest if dest else "current directory"
    if result.ok:
        summary = f"Archive '{archive}' extracted to '{dest_label}'."
    else:
        summary = f"Failed to extract archive '{archive}' to '{dest_label}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_verify(args: dict[str, Any]) -> ToolResult:
    """tar --compare --file <archive> (compare archive to filesystem)"""
    archive: str = args["archive"]
    result = run_subprocess(["tar", "--compare", "--file", archive], timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Archive '{archive}' verified; contents match the filesystem."
    else:
        summary = f"Archive '{archive}' verification found differences (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_create_gz(args: dict[str, Any]) -> ToolResult:
    """tar --create --gzip --file <archive> <sources...>"""
    archive: str = args["archive"]
    sources: list = args["sources"]
    cmd = ["tar", "--create", "--gzip", "--file", archive] + [str(s) for s in sources]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Gzip-compressed archive '{archive}' created from {len(sources)} source path(s)."
    else:
        summary = f"Failed to create gzip archive '{archive}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_create_bz2(args: dict[str, Any]) -> ToolResult:
    """tar --create --bzip2 --file <archive> <sources...>"""
    archive: str = args["archive"]
    sources: list = args["sources"]
    cmd = ["tar", "--create", "--bzip2", "--file", archive] + [str(s) for s in sources]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Bzip2-compressed archive '{archive}' created from {len(sources)} source path(s)."
    else:
        summary = f"Failed to create bzip2 archive '{archive}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_create_xz(args: dict[str, Any]) -> ToolResult:
    """tar --create --xz --file <archive> <sources...>"""
    archive: str = args["archive"]
    sources: list = args["sources"]
    cmd = ["tar", "--create", "--xz", "--file", archive] + [str(s) for s in sources]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Xz-compressed archive '{archive}' created from {len(sources)} source path(s)."
    else:
        summary = f"Failed to create xz archive '{archive}' (exit {result.exit_code})."
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
    "list":       _op_list,
    "create":     _op_create,
    "extract":    _op_extract,
    "verify":     _op_verify,
    "create_gz":  _op_create_gz,
    "create_bz2": _op_create_bz2,
    "create_xz":  _op_create_xz,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a tar operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never writes to the audit log (I4) and never calls
    permissions.classify() (I3).  It never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for tar tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

TAR_SPEC = ToolSpec(
    name="tar",
    description="Create, list, extract, and verify tar archives (plain, gzip, bzip2, xz).",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[_ARCHIVE_ARG],
            description="List the contents of a tar archive (verbose, showing permissions and sizes).",
        ),
        "create": OpSpec(
            op_name="create",
            permission_class=OpClass.WRITE,
            args=[_ARCHIVE_ARG, _SOURCES_ARG],
            description="Create an uncompressed tar archive from one or more source paths.",
        ),
        "extract": OpSpec(
            op_name="extract",
            permission_class=OpClass.WRITE,
            args=[_ARCHIVE_ARG, _DEST_ARG],
            description="Extract files from a tar archive, optionally to a destination directory.",
        ),
        "verify": OpSpec(
            op_name="verify",
            permission_class=OpClass.READ,
            args=[_ARCHIVE_ARG],
            description="Compare archive contents against the live filesystem to detect drift.",
        ),
        "create_gz": OpSpec(
            op_name="create_gz",
            permission_class=OpClass.WRITE,
            args=[_ARCHIVE_ARG, _SOURCES_ARG],
            description="Create a gzip-compressed tar archive (.tar.gz) from one or more source paths.",
        ),
        "create_bz2": OpSpec(
            op_name="create_bz2",
            permission_class=OpClass.WRITE,
            args=[_ARCHIVE_ARG, _SOURCES_ARG],
            description="Create a bzip2-compressed tar archive (.tar.bz2) from one or more source paths.",
        ),
        "create_xz": OpSpec(
            op_name="create_xz",
            permission_class=OpClass.WRITE,
            args=[_ARCHIVE_ARG, _SOURCES_ARG],
            description="Create an xz-compressed tar archive (.tar.xz) from one or more source paths.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(TAR_SPEC)
