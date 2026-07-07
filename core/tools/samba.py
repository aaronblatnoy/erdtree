"""core/tools/samba.py — Samba file-sharing management via smbd/nmbd, testparm, smbpasswd, and net.

Supported operations
--------------------
  smbd_status      (READ)        — show the status of smbd and nmbd via systemctl.
  nmbd_status      (READ)        — show the status of nmbd via systemctl.
  testparm         (READ)        — validate the smb.conf configuration file.
  smbpasswd_add    (WRITE)       — add a Samba user password entry (smbpasswd -a).
  smbpasswd_delete (DESTRUCTIVE) — remove a Samba user account (smbpasswd -x).
  usershare_list   (READ)        — list net usershares.
  usershare_add    (WRITE)       — add or update a net usershare.

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
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_smbd_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status smbd nmbd --no-pager"""
    result = run_subprocess(["systemctl", "status", "--no-pager", "smbd", "nmbd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Samba daemons smbd and nmbd are active and running."
    else:
        summary = f"Samba daemon status check reported exit {result.exit_code}."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_nmbd_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status nmbd --no-pager"""
    result = run_subprocess(["systemctl", "status", "--no-pager", "nmbd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "nmbd is active and running."
    else:
        summary = f"nmbd status check reported exit {result.exit_code}."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_testparm(args: dict[str, Any]) -> ToolResult:
    """testparm -s — validate smb.conf without prompting."""
    result = run_subprocess(["testparm", "-s"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "smb.conf syntax check passed; configuration is valid."
    else:
        summary = f"smb.conf validation failed (exit {result.exit_code}); review the output for errors."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_smbpasswd_add(args: dict[str, Any]) -> ToolResult:
    """smbpasswd -a <username> — add a Samba user (reads password from stdin)."""
    username: str = args["username"]
    password: str = args.get("password", "")
    # smbpasswd -a reads the new password twice from stdin: "new\nnew\n"
    stdin_input = f"{password}\n{password}\n" if password else None
    result = run_subprocess(
        ["smbpasswd", "-a", username],
        input=stdin_input,
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Samba user '{username}' added successfully."
    else:
        summary = f"Failed to add Samba user '{username}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_smbpasswd_delete(args: dict[str, Any]) -> ToolResult:
    """smbpasswd -x <username> — remove a Samba user account (DESTRUCTIVE)."""
    username: str = args["username"]
    result = run_subprocess(["smbpasswd", "-x", username])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Samba user '{username}' removed from the Samba user database."
    else:
        summary = f"Failed to remove Samba user '{username}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_usershare_list(args: dict[str, Any]) -> ToolResult:
    """net usershare list — list all current usershares."""
    result = run_subprocess(["net", "usershare", "list"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        count = len([ln for ln in result.stdout.splitlines() if ln.strip()])
        summary = f"Listed {count} usershare(s)."
    else:
        summary = f"Failed to list usershares (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_usershare_add(args: dict[str, Any]) -> ToolResult:
    """net usershare add <name> <path> <comment> <acl> — add or update a usershare."""
    name: str = args["name"]
    path: str = args["path"]
    comment: str = args.get("comment", "")
    acl: str = args.get("acl", "Everyone:R")
    result = run_subprocess(
        ["net", "usershare", "add", name, path, comment, acl]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Usershare '{name}' pointing to '{path}' added successfully."
    else:
        summary = f"Failed to add usershare '{name}' (exit {result.exit_code})."
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
    "smbd_status":      _op_smbd_status,
    "nmbd_status":      _op_nmbd_status,
    "testparm":         _op_testparm,
    "smbpasswd_add":    _op_smbpasswd_add,
    "smbpasswd_delete": _op_smbpasswd_delete,
    "usershare_list":   _op_usershare_list,
    "usershare_add":    _op_usershare_add,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a samba operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record. This function never calls permissions.classify() (I3)
    and never writes audit records (I4). It never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for samba tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_USERNAME_ARG = ArgSpec(
    name="username",
    type=str,
    required=True,
    description="The local system username to add or remove from the Samba user database.",
)

SAMBA_SPEC = ToolSpec(
    name="samba",
    description="Manage Samba file-sharing: check service status, validate config, and manage users and usershares.",
    ops={
        "smbd_status": OpSpec(
            op_name="smbd_status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current status of the smbd and nmbd daemons.",
        ),
        "nmbd_status": OpSpec(
            op_name="nmbd_status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current status of the nmbd NetBIOS daemon.",
        ),
        "testparm": OpSpec(
            op_name="testparm",
            permission_class=OpClass.READ,
            args=[],
            description="Validate the smb.conf configuration file for syntax errors.",
        ),
        "smbpasswd_add": OpSpec(
            op_name="smbpasswd_add",
            permission_class=OpClass.WRITE,
            args=[
                _USERNAME_ARG,
                ArgSpec(
                    name="password",
                    type=str,
                    required=False,
                    description="Password for the new Samba user (passed via stdin).",
                    default="",
                ),
            ],
            description="Add a system user to the Samba user database.",
        ),
        "smbpasswd_delete": OpSpec(
            op_name="smbpasswd_delete",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_USERNAME_ARG],
            description="Remove a user from the Samba user database (locks out that user's share access).",
        ),
        "usershare_list": OpSpec(
            op_name="usershare_list",
            permission_class=OpClass.READ,
            args=[],
            description="List all currently defined usershares.",
        ),
        "usershare_add": OpSpec(
            op_name="usershare_add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="name",
                    type=str,
                    required=True,
                    description="The usershare name (must be a valid share name).",
                ),
                ArgSpec(
                    name="path",
                    type=str,
                    required=True,
                    description="Absolute path on the local filesystem to share.",
                ),
                ArgSpec(
                    name="comment",
                    type=str,
                    required=False,
                    description="Human-readable description of the share.",
                    default="",
                ),
                ArgSpec(
                    name="acl",
                    type=str,
                    required=False,
                    description="ACL string (e.g. 'Everyone:R' or 'Everyone:F').",
                    default="Everyone:R",
                ),
            ],
            description="Add or update a usershare definition.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SAMBA_SPEC)
