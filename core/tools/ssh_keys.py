"""core/tools/ssh_keys.py — SSH key and configuration management tool.

Supported operations
--------------------
  keygen               (WRITE)       — generate an SSH key pair via ssh-keygen.
  authorized_keys_list (READ)        — list entries in a user's authorized_keys file.
  authorized_keys_add  (WRITE)       — append a public key to authorized_keys.
  authorized_keys_remove (DESTRUCTIVE) — remove a key from authorized_keys (lockout risk).
  known_hosts_list     (READ)        — list entries in a user's known_hosts file.
  known_hosts_remove   (WRITE)       — remove a host entry from known_hosts via ssh-keygen -R.
  sshd_config_audit    (READ)        — dump the effective sshd configuration via sshd -T.

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
# SELinux hint detection (copy VERBATIM from services.py — §4 of SLICE-CONTRACT)
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
# Path helpers
# ---------------------------------------------------------------------------

def _ak_path(user: str) -> str:
    """Return the canonical authorized_keys path for the given user."""
    if user == "root":
        return "/root/.ssh/authorized_keys"
    return f"/home/{user}/.ssh/authorized_keys"


def _kh_path(user: str) -> str:
    """Return the canonical known_hosts path for the given user."""
    if user == "root":
        return "/root/.ssh/known_hosts"
    return f"/home/{user}/.ssh/known_hosts"


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_keygen(args: dict[str, Any]) -> ToolResult:
    """ssh-keygen -t <type> -b <bits> -f <path> -N <passphrase>"""
    path: str = args["path"]
    key_type: str = str(args.get("key_type") or "ed25519")
    bits_raw = args.get("bits")
    bits: int = int(bits_raw) if bits_raw is not None else 4096
    passphrase: str = str(args.get("passphrase") or "")

    result = run_subprocess(
        ["ssh-keygen", "-t", key_type, "-b", str(bits), "-f", path, "-N", passphrase]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"SSH key pair generated at '{path}' (type={key_type}, bits={bits})."
        )
    else:
        summary = (
            f"Failed to generate SSH key pair at '{path}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_authorized_keys_list(args: dict[str, Any]) -> ToolResult:
    """cat /home/<user>/.ssh/authorized_keys"""
    user: str = str(args.get("user") or "root")
    path = _ak_path(user)
    result = run_subprocess(["cat", path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n") if result.stdout else 0
        summary = f"Retrieved {line_count} authorized key entries for user '{user}'."
    else:
        summary = (
            f"Could not read authorized_keys for user '{user}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_authorized_keys_add(args: dict[str, Any]) -> ToolResult:
    """tee -a /home/<user>/.ssh/authorized_keys  (key passed via stdin)"""
    key: str = args["key"]
    user: str = str(args.get("user") or "root")
    path = _ak_path(user)
    key_line = key.strip() + "\n"
    result = run_subprocess(["tee", "-a", path], input=key_line)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Public key appended to authorized_keys for user '{user}'."
    else:
        summary = (
            f"Failed to add key to authorized_keys for user '{user}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_authorized_keys_remove(args: dict[str, Any]) -> ToolResult:
    """sed -i '/<key_comment>/d' /home/<user>/.ssh/authorized_keys"""
    key_comment: str = args["key_comment"]
    user: str = str(args.get("user") or "root")
    path = _ak_path(user)
    # Use sed in-place deletion; key_comment identifies the key line to remove.
    result = run_subprocess(["sed", "-i", f"/{key_comment}/d", path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Entries matching '{key_comment}' removed from authorized_keys "
            f"for user '{user}'."
        )
    else:
        summary = (
            f"Failed to remove key '{key_comment}' from authorized_keys "
            f"for user '{user}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_known_hosts_list(args: dict[str, Any]) -> ToolResult:
    """cat /home/<user>/.ssh/known_hosts"""
    user: str = str(args.get("user") or "root")
    path = _kh_path(user)
    result = run_subprocess(["cat", path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n") if result.stdout else 0
        summary = f"Retrieved {line_count} known_hosts entries for user '{user}'."
    else:
        summary = (
            f"Could not read known_hosts for user '{user}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_known_hosts_remove(args: dict[str, Any]) -> ToolResult:
    """ssh-keygen -R <hostname> -f /home/<user>/.ssh/known_hosts"""
    hostname: str = args["hostname"]
    user: str = str(args.get("user") or "root")
    path = _kh_path(user)
    result = run_subprocess(["ssh-keygen", "-R", hostname, "-f", path])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Host '{hostname}' removed from known_hosts for user '{user}'."
        )
    else:
        summary = (
            f"Failed to remove '{hostname}' from known_hosts for user '{user}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_sshd_config_audit(args: dict[str, Any]) -> ToolResult:
    """sshd -T  — dump the effective sshd runtime configuration."""
    result = run_subprocess(["sshd", "-T"], timeout=15)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        line_count = result.stdout.count("\n") if result.stdout else 0
        summary = f"sshd configuration audit completed; {line_count} settings reported."
    else:
        summary = f"sshd configuration audit failed (exit {result.exit_code})."
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
    "keygen":                  _op_keygen,
    "authorized_keys_list":    _op_authorized_keys_list,
    "authorized_keys_add":     _op_authorized_keys_add,
    "authorized_keys_remove":  _op_authorized_keys_remove,
    "known_hosts_list":        _op_known_hosts_list,
    "known_hosts_remove":      _op_known_hosts_remove,
    "sshd_config_audit":       _op_sshd_config_audit,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an ssh_keys operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never raises (I9): unknown ops and subprocess errors
    both degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for ssh_keys tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_USER_ARG = ArgSpec(
    name="user",
    type=str,
    required=False,
    description="Local username whose SSH directory to target (default: root).",
    default="root",
)

# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

SSH_KEYS_SPEC = ToolSpec(
    name="ssh_keys",
    description="Manage SSH key pairs, authorized_keys, known_hosts, and sshd configuration.",
    ops={
        "keygen": OpSpec(
            op_name="keygen",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="path",
                    type=str,
                    required=True,
                    description="Output path for the private key file (public key written to <path>.pub).",
                ),
                ArgSpec(
                    name="key_type",
                    type=str,
                    required=False,
                    description="Key algorithm: ed25519, rsa, ecdsa (default: ed25519).",
                    default="ed25519",
                ),
                ArgSpec(
                    name="bits",
                    type=int,
                    required=False,
                    description="Key bit length (default: 4096; ignored for ed25519).",
                    default=4096,
                ),
                ArgSpec(
                    name="passphrase",
                    type=str,
                    required=False,
                    description="Passphrase to protect the private key (default: empty — no passphrase).",
                    default="",
                ),
            ],
            description="Generate a new SSH key pair at the specified path.",
        ),
        "authorized_keys_list": OpSpec(
            op_name="authorized_keys_list",
            permission_class=OpClass.READ,
            args=[_USER_ARG],
            description="List all entries in a user's authorized_keys file.",
        ),
        "authorized_keys_add": OpSpec(
            op_name="authorized_keys_add",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="key",
                    type=str,
                    required=True,
                    description="Full public key line to append (e.g. 'ssh-ed25519 AAAA... user@host').",
                ),
                _USER_ARG,
            ],
            description="Append a public key to a user's authorized_keys file.",
        ),
        "authorized_keys_remove": OpSpec(
            op_name="authorized_keys_remove",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="key_comment",
                    type=str,
                    required=True,
                    description="Comment or pattern identifying the key line(s) to remove (e.g. 'user@host').",
                ),
                _USER_ARG,
            ],
            description="Remove matching key entries from a user's authorized_keys file (lockout risk).",
        ),
        "known_hosts_list": OpSpec(
            op_name="known_hosts_list",
            permission_class=OpClass.READ,
            args=[_USER_ARG],
            description="List all entries in a user's known_hosts file.",
        ),
        "known_hosts_remove": OpSpec(
            op_name="known_hosts_remove",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="hostname",
                    type=str,
                    required=True,
                    description="Hostname (or IP) to remove from known_hosts.",
                ),
                _USER_ARG,
            ],
            description="Remove a host entry from a user's known_hosts file via ssh-keygen -R.",
        ),
        "sshd_config_audit": OpSpec(
            op_name="sshd_config_audit",
            permission_class=OpClass.READ,
            args=[],
            description="Dump the effective sshd runtime configuration via 'sshd -T'.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SSH_KEYS_SPEC)
