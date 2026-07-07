"""core/tools/fapolicyd.py — File access policy enforcement via fapolicyd.

Supported operations
--------------------
  status      (READ)  — show fapolicyd service status via systemctl.
  list_rules  (READ)  — list loaded fapolicyd rules via fapolicyd-cli.
  allow       (WRITE) — add an allow rule for a path or executable.
  deny        (WRITE) — add a deny rule for a path or executable.
                        Denying a critical system path (e.g. /usr/sbin/sshd,
                        /bin/login) can prevent logins or system execution —
                        confirm before applying and reload with 'update'.
  update      (WRITE) — reload fapolicyd rules via fapolicyd-cli --update.

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
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status --no-pager fapolicyd"""
    result = run_subprocess(["systemctl", "status", "--no-pager", "fapolicyd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "fapolicyd service is active and running."
    else:
        summary = f"fapolicyd service reported status exit {result.exit_code}."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_list_rules(args: dict[str, Any]) -> ToolResult:
    """fapolicyd-cli --list"""
    result = run_subprocess(["fapolicyd-cli", "--list"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        rule_count = result.stdout.count("\n")
        summary = f"Listed {rule_count} fapolicyd rule entries."
    else:
        summary = f"Failed to list fapolicyd rules (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_allow(args: dict[str, Any]) -> ToolResult:
    """fapolicyd-cli --add 'allow perm=any all : path=<path>'"""
    path: str = args["path"]
    rule = f"allow perm=any all : path={path}"
    result = run_subprocess(["fapolicyd-cli", "--add", rule])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Allow rule added for path '{path}'."
    else:
        summary = f"Failed to add allow rule for '{path}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_deny(args: dict[str, Any]) -> ToolResult:
    """fapolicyd-cli --add 'deny perm=any all : path=<path>'

    Note: denying a critical system path (e.g. /usr/sbin/sshd, /bin/login)
    can brick logins or prevent system execution. Confirm before applying and
    reload with 'update' to enforce the new rule.
    """
    path: str = args["path"]
    rule = f"deny perm=any all : path={path}"
    result = run_subprocess(["fapolicyd-cli", "--add", rule])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Deny rule added for path '{path}'. "
            "Denying a critical system path can prevent logins or system execution — "
            "run 'update' to apply and verify access is not broken."
        )
    else:
        summary = f"Failed to add deny rule for '{path}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_update(args: dict[str, Any]) -> ToolResult:
    """fapolicyd-cli --update"""
    result = run_subprocess(["fapolicyd-cli", "--update"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "fapolicyd rules reloaded successfully."
    else:
        summary = f"fapolicyd rule reload failed (exit {result.exit_code})."
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
    "list_rules": _op_list_rules,
    "allow": _op_allow,
    "deny": _op_deny,
    "update": _op_update,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a fapolicyd operation and return a structured ToolResult.

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
            summary=f"Unknown operation '{op}' for fapolicyd tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_PATH_ARG = ArgSpec(
    name="path",
    type=str,
    required=True,
    description=(
        "The file or executable path to apply the rule to "
        "(e.g. '/usr/local/bin/myapp', '/opt/vendor/bin/tool')."
    ),
)

FAPOLICYD_SPEC = ToolSpec(
    name="fapolicyd",
    description="Manage file access policy enforcement via fapolicyd and fapolicyd-cli.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current status of the fapolicyd service.",
        ),
        "list_rules": OpSpec(
            op_name="list_rules",
            permission_class=OpClass.READ,
            args=[],
            description="List all loaded fapolicyd rules.",
        ),
        "allow": OpSpec(
            op_name="allow",
            permission_class=OpClass.WRITE,
            args=[_PATH_ARG],
            description="Add an allow rule for a file path or executable.",
        ),
        "deny": OpSpec(
            op_name="deny",
            permission_class=OpClass.WRITE,
            args=[_PATH_ARG],
            description=(
                "Add a deny rule for a file path or executable. "
                "Denying a critical path can block logins or system operations."
            ),
        ),
        "update": OpSpec(
            op_name="update",
            permission_class=OpClass.WRITE,
            args=[],
            description=(
                "Reload fapolicyd rules by notifying the daemon to re-read "
                "its configuration via fapolicyd-cli --update."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(FAPOLICYD_SPEC)
