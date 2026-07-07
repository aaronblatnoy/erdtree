"""core/tools/aide.py — AIDE (Advanced Intrusion Detection Environment) integrity tool.

Supported operations
--------------------
  check      (READ)  — compare the live filesystem against the AIDE reference database.
  init       (WRITE) — initialise (or reinitialise) the AIDE reference database.
  update     (WRITE) — update the AIDE reference database to reflect approved changes.
  db_status  (READ)  — show the AIDE database file metadata (size, timestamp, path).

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

# Default AIDE config path on Rocky Linux 9
_AIDE_CONF = "/etc/aide.conf"
# Default AIDE database path on Rocky Linux 9
_AIDE_DB = "/var/lib/aide/aide.db.gz"


def _op_check(args: dict[str, Any]) -> ToolResult:
    """aide --check [--config <conf>]

    Compares the live filesystem against the reference database.
    Returns exit 0 if no changes found, non-zero otherwise.
    Uses a generous timeout because a full check can take several minutes.
    """
    conf: str = args.get("config", _AIDE_CONF)
    cmd = ["aide", "--check", "--config", conf]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "aide integrity check passed — no unexpected changes detected."
    else:
        summary = (
            f"aide integrity check reported changes or errors "
            f"(exit {result.exit_code}); review stdout for details."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_init(args: dict[str, Any]) -> ToolResult:
    """aide --init [--config <conf>]

    Initialises a new AIDE reference database from the current filesystem
    state.  The new DB is written to the 'database_out' path in the config
    (typically /var/lib/aide/aide.db.new.gz) and must be moved into place
    manually to become the active reference.  This is a WRITE operation:
    it overwrites the outgoing database file.
    """
    conf: str = args.get("config", _AIDE_CONF)
    cmd = ["aide", "--init", "--config", conf]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            "aide database initialised successfully. "
            "Move aide.db.new.gz to aide.db.gz to activate the new baseline."
        )
    else:
        summary = (
            f"aide database initialisation failed (exit {result.exit_code}); "
            "check stderr for configuration or permission errors."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_update(args: dict[str, Any]) -> ToolResult:
    """aide --update [--config <conf>]

    Runs a check and then writes a new database that matches the current
    filesystem, effectively accepting all changes as the new baseline.
    This replaces the prior reference — a WRITE operation.
    """
    conf: str = args.get("config", _AIDE_CONF)
    cmd = ["aide", "--update", "--config", conf]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            "aide database updated successfully. "
            "The new baseline reflects the current filesystem state."
        )
    else:
        summary = (
            f"aide database update failed (exit {result.exit_code}); "
            "review stderr for details."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_db_status(args: dict[str, Any]) -> ToolResult:
    """stat /var/lib/aide/aide.db.gz (or a custom path)

    Shows the AIDE database file metadata: size, modification timestamp,
    and permissions.  Read-only — does not touch the database contents.
    """
    db_path: str = args.get("db_path", _AIDE_DB)
    cmd = ["stat", db_path]
    result = run_subprocess(cmd, timeout=30)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"aide database file found at '{db_path}'; details in stdout."
    else:
        summary = (
            f"aide database file not found or inaccessible at '{db_path}' "
            f"(exit {result.exit_code}). Run 'aide --init' to create it."
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
    "check":     _op_check,
    "init":      _op_init,
    "update":    _op_update,
    "db_status": _op_db_status,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an aide operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never raises (I9): an unknown op or subprocess failure
    always degrades to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for aide tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_CONF_ARG = ArgSpec(
    name="config",
    type=str,
    required=False,
    description="Path to the AIDE configuration file (default: /etc/aide.conf).",
    default=_AIDE_CONF,
)

AIDE_SPEC = ToolSpec(
    name="aide",
    description="Run aide integrity checks and manage the reference database.",
    ops={
        "check": OpSpec(
            op_name="check",
            permission_class=OpClass.READ,
            args=[_CONF_ARG],
            description="Compare the live filesystem against the aide reference database.",
        ),
        "init": OpSpec(
            op_name="init",
            permission_class=OpClass.WRITE,
            args=[_CONF_ARG],
            description="Initialise a new aide reference database from the current filesystem state.",
        ),
        "update": OpSpec(
            op_name="update",
            permission_class=OpClass.WRITE,
            args=[_CONF_ARG],
            description="Update the aide reference database to accept current filesystem changes as the new baseline.",
        ),
        "db_status": OpSpec(
            op_name="db_status",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="db_path",
                    type=str,
                    required=False,
                    description="Path to the aide database file (default: /var/lib/aide/aide.db.gz).",
                    default=_AIDE_DB,
                )
            ],
            description="Show aide database file metadata (size, timestamp, permissions).",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(AIDE_SPEC)
