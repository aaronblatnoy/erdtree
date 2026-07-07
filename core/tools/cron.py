"""core/tools/cron.py — Crontab and cron.d management via crontab and related binaries.

Supported operations
--------------------
  list       (READ)        — list the current (or specified) user's crontab entries.
  list-all   (READ)        — list all user crontab files found in /var/spool/cron/.
  edit       (WRITE)       — replace a user's crontab by writing new content via stdin.
  remove     (DESTRUCTIVE) — remove an entire crontab (irreversible job loss).
  crond-view (READ)        — view a specific /etc/cron.d/ file, or list the directory.
  crond-add  (WRITE)       — write a new drop-in file to /etc/cron.d/.

Permission mapping (from DESTRUCTIVE-VERB-MANIFEST Phase 6 and plan table):
  READ        : list, list-all, crond-view
  WRITE       : edit, crond-add
  DESTRUCTIVE : remove  (crontab -r is irreversible — the ENTIRE crontab is wiped)

Note on remove
  crontab -r removes the caller's crontab with no prompt and no undo.
  crontab -r -u <user> (root only) wipes another user's crontab.  Both forms
  are DESTRUCTIVE.  The permission classifier (Phase 1) will escalate the
  rendered argv to Gate.REFUSE until the user has confirmed.

Design rules
------------
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller (router / REPL) MUST resolve the permission gate BEFORE
      calling execute(); this module does NOT call permissions.classify()
      internally.
  I4  This module writes NO audit records; the caller does.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure (missing binary exit 127, non-zero
      exit, timeout) degrades to a well-formed ToolResult.
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
# SELinux hint detection (copied verbatim from services.py — §3 of contract)
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
    """crontab -l [-u user] — list the current (or specified) user's crontab."""
    user: str | None = args.get("user")
    if user:
        cmd = ["crontab", "-l", "-u", user]
    else:
        cmd = ["crontab", "-l"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n")
        target = f"user '{user}'" if user else "current user"
        summary = f"Crontab for {target} listed ({line_count} lines)."
    else:
        target = f"user '{user}'" if user else "current user"
        summary = (
            f"Failed to list crontab for {target} (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_list_all(args: dict[str, Any]) -> ToolResult:
    """ls /var/spool/cron/ — list all user crontab files on the system."""
    result = run_subprocess(["ls", "-la", "/var/spool/cron/"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        # Count non-header lines (skip . and ..)
        entries = [
            ln for ln in result.stdout.splitlines()
            if ln.strip() and not ln.startswith("total")
            and not ln.endswith((" .", " .."))
        ]
        count = len(entries)
        summary = f"Found {count} crontab file(s) in /var/spool/cron/."
    else:
        summary = (
            f"Failed to list /var/spool/cron/ (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_edit(args: dict[str, Any]) -> ToolResult:
    """crontab - [-u user] — replace a user's crontab by reading from stdin."""
    content: str = args["content"]
    user: str | None = args.get("user")
    if user:
        cmd = ["crontab", "-u", user, "-"]
    else:
        cmd = ["crontab", "-"]
    result = run_subprocess(cmd, input=content)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        target = f"user '{user}'" if user else "current user"
        summary = f"Crontab for {target} updated successfully."
    else:
        target = f"user '{user}'" if user else "current user"
        summary = (
            f"Failed to update crontab for {target} (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_remove(args: dict[str, Any]) -> ToolResult:
    """crontab -r [-u user] — remove an entire crontab (irreversible)."""
    user: str | None = args.get("user")
    if user:
        cmd = ["crontab", "-r", "-u", user]
    else:
        cmd = ["crontab", "-r"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        target = f"user '{user}'" if user else "current user"
        summary = f"Crontab for {target} removed (all scheduled jobs deleted)."
    else:
        target = f"user '{user}'" if user else "current user"
        summary = (
            f"Failed to remove crontab for {target} (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_crond_view(args: dict[str, Any]) -> ToolResult:
    """cat /etc/cron.d/<name> or ls /etc/cron.d/ — view a cron.d file or list directory."""
    name: str | None = args.get("name")
    if name:
        path = f"/etc/cron.d/{name}"
        cmd = ["cat", path]
        result = run_subprocess(cmd)
        selinux = _maybe_selinux_hint(result.stderr)
        if result.ok:
            summary = f"Contents of /etc/cron.d/{name} retrieved."
        else:
            summary = (
                f"Failed to read /etc/cron.d/{name} (exit {result.exit_code})."
            )
    else:
        cmd = ["ls", "-la", "/etc/cron.d/"]
        result = run_subprocess(cmd)
        selinux = _maybe_selinux_hint(result.stderr)
        if result.ok:
            entries = [
                ln for ln in result.stdout.splitlines()
                if ln.strip() and not ln.startswith("total")
                and not ln.endswith((" .", " .."))
            ]
            count = len(entries)
            summary = f"Found {count} file(s) in /etc/cron.d/."
        else:
            summary = (
                f"Failed to list /etc/cron.d/ (exit {result.exit_code})."
            )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_crond_add(args: dict[str, Any]) -> ToolResult:
    """tee /etc/cron.d/<name> — write a new cron.d drop-in file via stdin."""
    name: str = args["name"]
    content: str = args["content"]
    path = f"/etc/cron.d/{name}"
    result = run_subprocess(["tee", path], input=content)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Cron drop-in file /etc/cron.d/{name} written successfully."
    else:
        summary = (
            f"Failed to write /etc/cron.d/{name} (exit {result.exit_code})."
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
    "list":       _op_list,
    "list-all":   _op_list_all,
    "edit":       _op_edit,
    "remove":     _op_remove,
    "crond-view": _op_crond_view,
    "crond-add":  _op_crond_add,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a cron operation and return a structured ToolResult.

    The caller (Phase 4 router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never calls permissions or writes audit records (I3, I4).
    It never raises — every failure path returns a well-formed ToolResult (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for cron tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_USER_ARG = ArgSpec(
    name="user",
    type=str,
    required=False,
    description=(
        "Username whose crontab to operate on. "
        "If omitted, the current user's crontab is used."
    ),
    default=None,
)

_NAME_ARG = ArgSpec(
    name="name",
    type=str,
    required=False,
    description=(
        "Filename within /etc/cron.d/ (e.g. 'backup-jobs'). "
        "If omitted, the directory listing is returned."
    ),
    default=None,
)

# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

CRON_SPEC = ToolSpec(
    name="cron",
    description="Manage user crontabs and /etc/cron.d/ drop-in files via crontab.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[_USER_ARG],
            description="List the current (or specified) user's crontab entries.",
        ),
        "list-all": OpSpec(
            op_name="list-all",
            permission_class=OpClass.READ,
            args=[],
            description="List all user crontab files present in /var/spool/cron/.",
        ),
        "edit": OpSpec(
            op_name="edit",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="content",
                    type=str,
                    required=True,
                    description="The full crontab content to install (replaces existing entries).",
                ),
                _USER_ARG,
            ],
            description="Replace a user's crontab with new content supplied via stdin.",
        ),
        "remove": OpSpec(
            op_name="remove",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_USER_ARG],
            description=(
                "Remove an entire crontab (irreversible — all scheduled jobs are deleted). "
                "Uses crontab -r [-u user]."
            ),
        ),
        "crond-view": OpSpec(
            op_name="crond-view",
            permission_class=OpClass.READ,
            args=[_NAME_ARG],
            description=(
                "View a specific /etc/cron.d/ file by name, or list the directory "
                "when no name is given."
            ),
        ),
        "crond-add": OpSpec(
            op_name="crond-add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="name",
                    type=str,
                    required=True,
                    description="Filename to create within /etc/cron.d/ (e.g. 'backup-jobs').",
                ),
                ArgSpec(
                    name="content",
                    type=str,
                    required=True,
                    description="Full content to write into the /etc/cron.d/ drop-in file.",
                ),
            ],
            description="Write a new drop-in file to /etc/cron.d/ via tee.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(CRON_SPEC)
