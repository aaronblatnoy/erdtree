"""core/tools/quota.py — Disk quota management via the quota utilities.

Supported operations
--------------------
  repquota    (READ)  — report disk quota usage for a filesystem or all filesystems.
  quota_user  (READ)  — show quota limits and usage for a specific user.
  quotaon     (WRITE) — enable disk quota enforcement on a filesystem.
  quotaoff    (WRITE) — disable disk quota enforcement on a filesystem.
  quotacheck  (WRITE) — scan a filesystem and rebuild quota accounting files.
  edquota     (WRITE) — set quota limits for a user on a filesystem (via setquota).

Permission mapping:
  READ  : repquota, quota_user
  WRITE : quotaon, quotaoff, quotacheck, edquota

Note on edquota
  The op is named 'edquota' per the plan table but delegates to the setquota
  binary, which is the non-interactive programmatic equivalent. edquota itself
  opens an editor session and is unsuitable for subprocess execution; setquota
  accepts all the same limit parameters on argv and exits deterministically.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL binary.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module never
      calls permissions.classify().
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
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_FILESYSTEM_ARG_REQUIRED = ArgSpec(
    name="filesystem",
    type=str,
    required=True,
    description="Filesystem mount point or device (e.g. '/home', '/dev/sda1').",
)

_FILESYSTEM_ARG_OPTIONAL = ArgSpec(
    name="filesystem",
    type=str,
    required=False,
    description=(
        "Filesystem mount point (e.g. '/home'). "
        "Omit to report all quota-enabled filesystems."
    ),
    default="-a",
)

_USERNAME_ARG = ArgSpec(
    name="username",
    type=str,
    required=True,
    description="The username whose quota is to be inspected or modified.",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_repquota(args: dict[str, Any]) -> ToolResult:
    """repquota — show quota usage report for a filesystem or all filesystems."""
    filesystem: str = args.get("filesystem", "-a")
    if filesystem == "-a":
        cmd = ["repquota", "-a", "-s"]
        fs_desc = "all quota-enabled filesystems"
    else:
        cmd = ["repquota", "-s", filesystem]
        fs_desc = f"'{filesystem}'"
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Quota report for {fs_desc} retrieved."
    else:
        summary = (
            f"Failed to retrieve quota report for {fs_desc} (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_quota_user(args: dict[str, Any]) -> ToolResult:
    """quota -u <username> — show quota limits and usage for a specific user."""
    username: str = args["username"]
    result = run_subprocess(["quota", "-u", username])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Quota information for user '{username}' retrieved."
    else:
        summary = (
            f"Failed to retrieve quota for user '{username}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_quotaon(args: dict[str, Any]) -> ToolResult:
    """quotaon -v <filesystem> — enable quota enforcement on a filesystem."""
    filesystem: str = args["filesystem"]
    result = run_subprocess(["quotaon", "-v", filesystem])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Quota enforcement enabled on '{filesystem}'."
    else:
        summary = (
            f"Failed to enable quotas on '{filesystem}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_quotaoff(args: dict[str, Any]) -> ToolResult:
    """quotaoff -v <filesystem> — disable quota enforcement on a filesystem."""
    filesystem: str = args["filesystem"]
    result = run_subprocess(["quotaoff", "-v", filesystem])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Quota enforcement disabled on '{filesystem}'."
    else:
        summary = (
            f"Failed to disable quotas on '{filesystem}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_quotacheck(args: dict[str, Any]) -> ToolResult:
    """quotacheck -ugm <filesystem> — scan and rebuild quota accounting files."""
    filesystem: str = args["filesystem"]
    result = run_subprocess(["quotacheck", "-ugm", filesystem], timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Quota check completed for '{filesystem}'; accounting files updated."
    else:
        summary = (
            f"Quota check failed for '{filesystem}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_edquota(args: dict[str, Any]) -> ToolResult:
    """setquota -u <user> <soft> <hard> <soft_inodes> <hard_inodes> <fs>

    Sets quota limits for a user on a filesystem using setquota (the
    non-interactive programmatic equivalent of edquota). Limits are in 1K
    blocks for block quotas and file counts for inode quotas; 0 means no limit.
    """
    username: str = args["username"]
    filesystem: str = args["filesystem"]
    try:
        soft_blocks = int(args.get("soft_blocks", 0))
        hard_blocks = int(args.get("hard_blocks", 0))
        soft_inodes = int(args.get("soft_inodes", 0))
        hard_inodes = int(args.get("hard_inodes", 0))
    except (TypeError, ValueError):
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=(
                f"Invalid quota limit values for user '{username}'; "
                "all limit values must be non-negative integers (0 = no limit)."
            ),
        )
    result = run_subprocess([
        "setquota", "-u", username,
        str(soft_blocks), str(hard_blocks),
        str(soft_inodes), str(hard_inodes),
        filesystem,
    ])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Quota limits set for user '{username}' on '{filesystem}': "
            f"blocks soft={soft_blocks} hard={hard_blocks}, "
            f"inodes soft={soft_inodes} hard={hard_inodes}."
        )
    else:
        summary = (
            f"Failed to set quota limits for user '{username}' on '{filesystem}' "
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
    "repquota":   _op_repquota,
    "quota_user": _op_quota_user,
    "quotaon":    _op_quotaon,
    "quotaoff":   _op_quotaoff,
    "quotacheck": _op_quotacheck,
    "edquota":    _op_edquota,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a quota operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9): unknown or failing ops degrade to a
    well-formed ToolResult with a non-zero exit code.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for quota tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

QUOTA_SPEC = ToolSpec(
    name="quota",
    description="Manage disk quotas on Linux filesystems using the quota utilities.",
    ops={
        "repquota": OpSpec(
            op_name="repquota",
            permission_class=OpClass.READ,
            args=[_FILESYSTEM_ARG_OPTIONAL],
            description="Report disk quota usage for all users on a filesystem.",
        ),
        "quota_user": OpSpec(
            op_name="quota_user",
            permission_class=OpClass.READ,
            args=[_USERNAME_ARG],
            description="Show quota limits and current usage for a specific user.",
        ),
        "quotaon": OpSpec(
            op_name="quotaon",
            permission_class=OpClass.WRITE,
            args=[_FILESYSTEM_ARG_REQUIRED],
            description="Enable disk quota enforcement on a filesystem.",
        ),
        "quotaoff": OpSpec(
            op_name="quotaoff",
            permission_class=OpClass.WRITE,
            args=[_FILESYSTEM_ARG_REQUIRED],
            description="Disable disk quota enforcement on a filesystem.",
        ),
        "quotacheck": OpSpec(
            op_name="quotacheck",
            permission_class=OpClass.WRITE,
            args=[_FILESYSTEM_ARG_REQUIRED],
            description="Scan a filesystem and rebuild quota accounting files.",
        ),
        "edquota": OpSpec(
            op_name="edquota",
            permission_class=OpClass.WRITE,
            args=[
                _USERNAME_ARG,
                _FILESYSTEM_ARG_REQUIRED,
                ArgSpec(
                    name="soft_blocks",
                    type=int,
                    required=False,
                    description="Soft block limit in 1K blocks (0 = no limit).",
                    default=0,
                ),
                ArgSpec(
                    name="hard_blocks",
                    type=int,
                    required=False,
                    description="Hard block limit in 1K blocks (0 = no limit).",
                    default=0,
                ),
                ArgSpec(
                    name="soft_inodes",
                    type=int,
                    required=False,
                    description="Soft inode limit (0 = no limit).",
                    default=0,
                ),
                ArgSpec(
                    name="hard_inodes",
                    type=int,
                    required=False,
                    description="Hard inode limit (0 = no limit).",
                    default=0,
                ),
            ],
            description=(
                "Set quota limits for a user on a filesystem "
                "(soft/hard block and inode limits)."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(QUOTA_SPEC)
