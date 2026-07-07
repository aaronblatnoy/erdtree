"""core/tools/bond.py — network bond interface management via nmcli.

Supported operations
--------------------
  show    (READ)        — list bond connections or show detail for a named bond.
  add     (WRITE)       — create a bond connection with optional bonding mode.
  modify  (WRITE)       — modify a property on an existing bond connection.
  remove  (DESTRUCTIVE) — delete a bond connection (nmcli connection delete).

Overlap note (OVERLAP-MAP §bond vs network)
-------------------------------------------
  'network' manages generic interface inspection (show/status/interfaces)
  and link bring_up/bring_down.  'bond' is the authoritative tool for bond
  CREATE/MODIFY/REMOVE only.  network.interfaces / network.show WILL list
  bond devices because bonds are interfaces — that inspection overlap is
  acceptable.  'bond' must NOT re-expose bring_up, bring_down, or set_ip.

Destructive verb (DESTRUCTIVE-VERB-MANIFEST §bond)
---------------------------------------------------
  remove renders as `nmcli connection delete <bond>` — labelled DESTRUCTIVE
  because deleting the bond connection severs the aggregated link and can
  lock out remote access.  Phase 1 must escalate `nmcli connection delete`
  to DESTRUCTIVE; until then the advisory OpClass label is accurate.

Design rules (load-bearing invariants)
--------------------------------------
  I1  No network.  Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed
      ToolResult (missing binary → exit 127, timeout → 124, OSError → 1).
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

def _op_show(args: dict[str, Any]) -> ToolResult:
    """nmcli connection show [<bond>]

    If 'bond' arg is provided, show detailed properties for that connection.
    Otherwise show all NetworkManager connections (bonds will appear as type bond).
    """
    bond: str = args.get("bond", "")
    if bond:
        cmd = ["nmcli", "connection", "show", bond]
    else:
        cmd = ["nmcli", "connection", "show"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        if bond:
            summary = f"Bond connection '{bond}' properties retrieved."
        else:
            summary = "Bond and network connection list retrieved."
    else:
        if bond:
            summary = (
                f"Failed to show bond connection '{bond}' (exit {result.exit_code})."
            )
        else:
            summary = f"Failed to list connections (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_add(args: dict[str, Any]) -> ToolResult:
    """nmcli connection add type bond ...

    Creates a bond connection in NetworkManager.  Slave interfaces are not
    added here; use 'modify' or a separate nmcli connection add for each
    slave after the bond is created.
    """
    bond: str = args["bond"]
    raw_mode = args.get("mode")
    mode: str = str(raw_mode) if raw_mode is not None else "active-backup"
    cmd = [
        "nmcli", "connection", "add",
        "type", "bond",
        "con-name", bond,
        "ifname", bond,
        "bond.options", f"mode={mode}",
    ]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Bond connection '{bond}' created with mode '{mode}'."
    else:
        summary = (
            f"Failed to create bond connection '{bond}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_modify(args: dict[str, Any]) -> ToolResult:
    """nmcli connection modify <bond> <property> <value>

    Modifies a property on an existing bond connection.  For example:
      property='bond.options'  value='mode=802.3ad'
      property='ipv4.addresses' value='192.168.1.10/24'
    """
    bond: str = args["bond"]
    prop: str = args["property"]
    value: str = args["value"]
    cmd = ["nmcli", "connection", "modify", bond, prop, value]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Bond connection '{bond}' property '{prop}' updated to '{value}'."
    else:
        summary = (
            f"Failed to modify bond connection '{bond}' (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_remove(args: dict[str, Any]) -> ToolResult:
    """nmcli connection delete <bond>  [DESTRUCTIVE]

    Permanently removes the bond connection profile from NetworkManager.
    Deleting the active bond connection drops the aggregated link and can
    sever remote access — confirm before executing.
    """
    bond: str = args["bond"]
    cmd = ["nmcli", "connection", "delete", bond]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Bond connection '{bond}' deleted."
    else:
        summary = (
            f"Failed to delete bond connection '{bond}' (exit {result.exit_code})."
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
    "show":   _op_show,
    "add":    _op_add,
    "modify": _op_modify,
    "remove": _op_remove,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a bond operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify() (I3).
      2. Writing the audit record (I4).

    This function dispatches to the per-op handler, which runs the subprocess
    and returns a ToolResult.  It never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for bond tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_BOND_ARG = ArgSpec(
    name="bond",
    type=str,
    required=True,
    description="NetworkManager connection name for the bond (e.g. 'bond0').",
)

BOND_SPEC = ToolSpec(
    name="bond",
    description="Manage network bond interfaces via nmcli (create, modify, remove).",
    ops={
        "show": OpSpec(
            op_name="show",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="bond",
                    type=str,
                    required=False,
                    description=(
                        "Bond connection name to inspect. "
                        "If omitted all connections are listed."
                    ),
                    default="",
                ),
            ],
            description=(
                "List NetworkManager connections or show detail for a named bond."
            ),
        ),
        "add": OpSpec(
            op_name="add",
            permission_class=OpClass.WRITE,
            args=[
                _BOND_ARG,
                ArgSpec(
                    name="mode",
                    type=str,
                    required=False,
                    description=(
                        "Bonding mode (e.g. 'active-backup', '802.3ad', "
                        "'balance-rr'). Defaults to 'active-backup'."
                    ),
                    default="active-backup",
                ),
            ],
            description="Create a bond connection in NetworkManager.",
        ),
        "modify": OpSpec(
            op_name="modify",
            permission_class=OpClass.WRITE,
            args=[
                _BOND_ARG,
                ArgSpec(
                    name="property",
                    type=str,
                    required=True,
                    description=(
                        "NetworkManager property to set "
                        "(e.g. 'bond.options', 'ipv4.method')."
                    ),
                ),
                ArgSpec(
                    name="value",
                    type=str,
                    required=True,
                    description="New value for the property.",
                ),
            ],
            description="Modify a property on an existing bond connection.",
        ),
        "remove": OpSpec(
            op_name="remove",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_BOND_ARG],
            description=(
                "Delete a bond connection from NetworkManager "
                "(nmcli connection delete). "
                "Removing the active bond drops the aggregated link — "
                "this operation can sever remote access."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(BOND_SPEC)
