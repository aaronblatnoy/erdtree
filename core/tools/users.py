"""core/tools/users.py — local user account management tool.

Supported operations
--------------------
  list                 (READ)        — list local accounts (cat /etc/passwd).
  info                 (READ)        — show one account's id/group record (id <user>).
  add                  (WRITE)       — create an account (useradd <user>).
  set_shell            (WRITE)       — set an account's login shell (usermod -s <shell> <user>).
  add_to_group         (WRITE)       — add an account to a group (usermod -aG <group> <user>).
  lock                 (DESTRUCTIVE) — lock an account (usermod -L <user>); lockout risk.
  delete               (DESTRUCTIVE) — delete an account (userdel <user>); lockout risk.
  remove_from_privgroup(DESTRUCTIVE) — remove an account from a privileged group
                                       (gpasswd -d <user> wheel); strips sudo access.

Permission mapping
  READ        : list, info
  WRITE       : add, set_shell, add_to_group
  DESTRUCTIVE : lock, delete, remove_from_privgroup

Blast radius
  This tool has a HIGH lockout blast radius. Locking, deleting, or stripping the
  privileged-group membership of the only administrative account can lock every
  human out of a remote host. Those three ops are DESTRUCTIVE. The gate that
  enforces the typed-word confirmation is NOT resolved here — the caller (the
  loop) renders the faithful command line (e.g. "usermod -L <user>",
  "userdel <user>", "gpasswd -d <user> wheel") and the hardened classifier
  escalates it to DESTRUCTIVE -> typed-word confirmation. The OpSpec class here
  is advisory.

Design rules
------------
  I1  No network calls — every op shells out via run_subprocess only.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE dispatch; this module does
      NOT call permissions.classify() and never self-classifies.
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.

Subprocess mocking
------------------
  On a host without useradd/usermod/passwd/userdel/gpasswd, every test patches
  ``core.tools.users.run_subprocess`` so no real process is launched. The tool
  builds a command vector and calls ``run_subprocess``; it never inspects
  ``sys.platform``.
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
# SELinux hint detection (copied from services.py — AVC denials are likely on
# account writes when SELinux confines the calling domain).
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)

# The privileged group whose membership grants sudo on Rocky/RHEL.
_PRIV_GROUP = "wheel"


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """cat /etc/passwd — list local accounts."""
    result = run_subprocess(["cat", "/etc/passwd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        count = result.stdout.count("\n")
        summary = f"Listed {count} local accounts."
    else:
        summary = f"Account listing failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_info(args: dict[str, Any]) -> ToolResult:
    """id <user> — show one account's uid/gid/group record."""
    user: str = args["user"]
    result = run_subprocess(["id", user])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok and result.stdout.strip():
        summary = f"Found account record for '{user}'."
    elif result.ok:
        summary = f"No account record for '{user}'."
    else:
        summary = f"Account lookup for '{user}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_add(args: dict[str, Any]) -> ToolResult:
    """useradd <user> — create an account."""
    user: str = args["user"]
    result = run_subprocess(["useradd", user])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Account '{user}' created."
    else:
        summary = f"Failed to create account '{user}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_shell(args: dict[str, Any]) -> ToolResult:
    """usermod -s <shell> <user> — set an account's login shell."""
    user: str = args["user"]
    shell: str = args["shell"]
    result = run_subprocess(["usermod", "-s", shell, user])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Login shell for '{user}' set to '{shell}'."
    else:
        summary = f"Failed to set login shell for '{user}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_add_to_group(args: dict[str, Any]) -> ToolResult:
    """usermod -aG <group> <user> — add an account to a group."""
    user: str = args["user"]
    group: str = args["group"]
    result = run_subprocess(["usermod", "-aG", group, user])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Account '{user}' added to group '{group}'."
    else:
        summary = f"Failed to add '{user}' to group '{group}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_lock(args: dict[str, Any]) -> ToolResult:
    """usermod -L <user> — lock an account (lockout risk)."""
    user: str = args["user"]
    result = run_subprocess(["usermod", "-L", user])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Account '{user}' locked."
    else:
        summary = f"Failed to lock account '{user}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_delete(args: dict[str, Any]) -> ToolResult:
    """userdel <user> — delete an account (lockout risk)."""
    user: str = args["user"]
    result = run_subprocess(["userdel", user])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Account '{user}' deleted."
    else:
        summary = f"Failed to delete account '{user}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_remove_from_privgroup(args: dict[str, Any]) -> ToolResult:
    """gpasswd -d <user> wheel — remove an account from the privileged group."""
    user: str = args["user"]
    result = run_subprocess(["gpasswd", "-d", user, _PRIV_GROUP])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Account '{user}' removed from group '{_PRIV_GROUP}'."
    else:
        summary = (
            f"Failed to remove '{user}' from group '{_PRIV_GROUP}' "
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
    "list": _op_list,
    "info": _op_info,
    "add": _op_add,
    "set_shell": _op_set_shell,
    "add_to_group": _op_add_to_group,
    "lock": _op_lock,
    "delete": _op_delete,
    "remove_from_privgroup": _op_remove_from_privgroup,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a users operation and return a structured ToolResult.

    The caller (the loop) resolves the permission gate and writes the audit
    record. This function runs the subprocess, builds a ToolResult, and returns;
    it never touches permissions or audit (I3 / I4).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        # Should not happen — ToolRegistry validates ops before calling execute().
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for users tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_USER_ARG = ArgSpec(
    name="user",
    type=str,
    required=True,
    description="The login name of the account (e.g. 'deploy', 'jdoe').",
)

USERS_SPEC = ToolSpec(
    name="users",
    description="Manage local user accounts via useradd, usermod, userdel, and gpasswd.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[],
            description="List local user accounts.",
        ),
        "info": OpSpec(
            op_name="info",
            permission_class=OpClass.READ,
            args=[_USER_ARG],
            description="Show the record for one account.",
        ),
        "add": OpSpec(
            op_name="add",
            permission_class=OpClass.WRITE,
            args=[_USER_ARG],
            description="Create a new account.",
        ),
        "set_shell": OpSpec(
            op_name="set_shell",
            permission_class=OpClass.WRITE,
            args=[
                _USER_ARG,
                ArgSpec(
                    name="shell",
                    type=str,
                    required=True,
                    description="The login shell path (e.g. '/bin/bash').",
                ),
            ],
            description="Set an account's login shell.",
        ),
        "add_to_group": OpSpec(
            op_name="add_to_group",
            permission_class=OpClass.WRITE,
            args=[
                _USER_ARG,
                ArgSpec(
                    name="group",
                    type=str,
                    required=True,
                    description="The group name to add the account to.",
                ),
            ],
            description="Add an account to a supplementary group.",
        ),
        "lock": OpSpec(
            op_name="lock",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_USER_ARG],
            description="Lock an account so it cannot sign in.",
        ),
        "delete": OpSpec(
            op_name="delete",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_USER_ARG],
            description="Delete an account.",
        ),
        "remove_from_privgroup": OpSpec(
            op_name="remove_from_privgroup",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_USER_ARG],
            description="Remove an account from the privileged group that grants sudo.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(USERS_SPEC)
