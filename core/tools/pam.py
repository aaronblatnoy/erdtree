"""core/tools/pam.py — PAM configuration and faillock management tool.

Supported operations
--------------------
  pamd_audit       (READ)  — display a PAM service configuration file from /etc/pam.d/.
  faillock_status  (READ)  — show authentication failure tallies via faillock.
  faillock_reset   (WRITE) — reset faillock failure tallies (all users or one user).
  pam_auth_update  (WRITE) — enable or disable a PAM profile via pam-auth-update.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.

Note on pam_auth_update lockout risk
  Applying a broken or misconfigured PAM profile via pam-auth-update can lock
  out ALL interactive and SSH logins. The op is labeled WRITE; administrators
  must verify the profile exists and is correct before applying. The summary
  always includes a reminder to test login in a second session before closing
  the current one.
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

def _op_pamd_audit(args: dict[str, Any]) -> ToolResult:
    """cat /etc/pam.d/<service> — display a PAM service config file."""
    service: str = args["service"]
    result = run_subprocess(["cat", f"/etc/pam.d/{service}"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n")
        summary = f"PAM configuration for '{service}' retrieved ({line_count} lines)."
    else:
        summary = (
            f"Failed to read /etc/pam.d/{service} (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_faillock_status(args: dict[str, Any]) -> ToolResult:
    """faillock [--user <user>] — show authentication failure tallies."""
    user: str | None = args.get("user")
    if user:
        cmd = ["faillock", "--user", user]
    else:
        cmd = ["faillock"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        if user:
            summary = f"Faillock tallies for user '{user}' retrieved."
        else:
            summary = "Faillock authentication failure tallies retrieved."
    else:
        if user:
            summary = f"Failed to retrieve faillock status for '{user}' (exit {result.exit_code})."
        else:
            summary = f"Failed to retrieve faillock status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_faillock_reset(args: dict[str, Any]) -> ToolResult:
    """faillock --reset [--user <user>] — reset authentication failure tallies."""
    user: str | None = args.get("user")
    if user:
        cmd = ["faillock", "--user", user, "--reset"]
    else:
        cmd = ["faillock", "--reset"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        if user:
            summary = f"Faillock tallies reset for user '{user}'."
        else:
            summary = "Faillock authentication failure tallies reset for all users."
    else:
        if user:
            summary = f"Failed to reset faillock tallies for '{user}' (exit {result.exit_code})."
        else:
            summary = f"Failed to reset faillock tallies (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pam_auth_update(args: dict[str, Any]) -> ToolResult:
    """pam-auth-update --enable|--disable <profile> — apply a PAM profile."""
    profile: str = args["profile"]
    action: str = args.get("action") or "enable"
    # Normalise action to a recognised flag
    if action not in ("enable", "disable"):
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=(
                f"Unknown action '{action}' for pam_auth_update; "
                "use 'enable' or 'disable'."
            ),
        )
    cmd = ["pam-auth-update", f"--{action}", profile]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"PAM profile '{profile}' {action}d via pam-auth-update. "
            "Verify login access in a separate session before closing this one."
        )
    else:
        summary = (
            f"pam-auth-update failed to {action} profile '{profile}' "
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
    "pamd_audit":      _op_pamd_audit,
    "faillock_status": _op_faillock_status,
    "faillock_reset":  _op_faillock_reset,
    "pam_auth_update": _op_pam_auth_update,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a PAM operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record. This function only runs the subprocess and returns.
    It never raises (I9): unknown ops and missing binaries both degrade
    to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for pam tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_SERVICE_ARG = ArgSpec(
    name="service",
    type=str,
    required=True,
    description="PAM service name matching a file in /etc/pam.d/ (e.g. 'sshd', 'sudo', 'login').",
)

_USER_ARG = ArgSpec(
    name="user",
    type=str,
    required=False,
    description="Username to scope the faillock operation to; omit to target all users.",
    default=None,
)

PAM_SPEC = ToolSpec(
    name="pam",
    description=(
        "Inspect and manage PAM configuration and authentication failure tallies "
        "via pam.d files, faillock, and pam-auth-update."
    ),
    ops={
        "pamd_audit": OpSpec(
            op_name="pamd_audit",
            permission_class=OpClass.READ,
            args=[_SERVICE_ARG],
            description="Display the PAM configuration file for a named service from /etc/pam.d/.",
        ),
        "faillock_status": OpSpec(
            op_name="faillock_status",
            permission_class=OpClass.READ,
            args=[_USER_ARG],
            description="Show authentication failure tallies tracked by faillock.",
        ),
        "faillock_reset": OpSpec(
            op_name="faillock_reset",
            permission_class=OpClass.WRITE,
            args=[_USER_ARG],
            description="Reset faillock authentication failure tallies for a user or all users.",
        ),
        "pam_auth_update": OpSpec(
            op_name="pam_auth_update",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="profile",
                    type=str,
                    required=True,
                    description=(
                        "PAM profile name to enable or disable "
                        "(e.g. 'mkhomedir', 'pwquality', 'faillock')."
                    ),
                ),
                ArgSpec(
                    name="action",
                    type=str,
                    required=False,
                    description="Action to perform: 'enable' (default) or 'disable'.",
                    default="enable",
                ),
            ],
            description=(
                "Enable or disable a PAM authentication profile via pam-auth-update. "
                "A misconfigured profile can lock out all logins — always verify "
                "in a separate session."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(PAM_SPEC)
