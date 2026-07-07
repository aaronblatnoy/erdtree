"""finetune/simulate/bond.py — Rocky Linux 9 output simulator for the 'bond' tool.

Public API
----------
simulate_bond(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 4 real operations declared in core/tools/bond.py
           (show, add, modify, remove)
    args : dict of op arguments (may be sparse; defaults are applied per-op)
    ctx  : system context string produced by make_context(), OR a profile
           dict with 'active_services'/'hostname'/... keys. Both forms are
           supported via isinstance checks.

Realism model
-------------
* nmcli command output mirrors Rocky Linux 9 NetworkManager 1.x format.
* Exit codes follow nmcli conventions:
    0   — success
    1   — unknown or failed operation
    2   — invalid user input / wrong arguments
    4   — connection not found
* Failure triggers are deterministic: a bond name containing the tokens
  "notfound", "noexist", "broken", "fail", "missing", or "bogus" returns
  a not-found error.  A hash-based ~15% scatter adds variety.
* ctx is used to decide whether a bond is configured: if the bond name
  appears in ctx (as a string) or in ctx["bond_connections"] (as a list),
  show reports it present.

I2 compliance
-------------
All `summary` strings are I2-clean.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps).
The ToolResult shape is mirrored as a plain dict — no class dependency.
"""

from __future__ import annotations

import hashlib
import uuid as _uuid_mod
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _bond_is_configured(bond: str, ctx: Any) -> bool:
    """Return True if the bond appears to be configured in the given context."""
    if isinstance(ctx, dict):
        bonds: list[str] = ctx.get("bond_connections", [])
        if bond in bonds or any(bond in b for b in bonds):
            return True
    if isinstance(ctx, str):
        return bond in ctx
    return False


def _bond_not_found(bond: str) -> bool:
    """Deterministically decide if a bond name should trigger a not-found error."""
    lower = bond.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus"):
        if tok in lower:
            return True
    # Hash-based deterministic scatter (~15%)
    h = int(hashlib.md5(bond.encode()).hexdigest(), 16)
    return h % 20 == 0


def _fake_uuid(seed: str) -> str:
    """Return a deterministic UUID-shaped string from a seed."""
    h = hashlib.md5(seed.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_show(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    bond = args.get("bond", "")

    if bond:
        # Show detail for a specific bond connection
        if _bond_not_found(bond):
            stderr = f"Error: No such connection profile '{bond}'.\n"
            return _make_result(
                exit_code=10,
                stdout="",
                stderr=stderr,
                summary=f"Bond connection '{bond}' was not found.",
            )

        uid = _fake_uuid(bond)
        configured = _bond_is_configured(bond, ctx)
        device_line = bond if configured else "--"
        stdout = (
            f"connection.id:                          {bond}\n"
            f"connection.uuid:                        {uid}\n"
            f"connection.stable-id:                   --\n"
            f"connection.type:                        bond\n"
            f"connection.interface-name:              {bond}\n"
            f"connection.autoconnect:                 yes\n"
            f"connection.autoconnect-priority:        0\n"
            f"connection.timestamp:                   0\n"
            f"connection.read-only:                   no\n"
            f"connection.permissions:                 --\n"
            f"connection.zone:                        --\n"
            f"bond.options:                           mode=active-backup\n"
            f"bond.options:                           miimon=100\n"
            f"GENERAL.NAME:                           {bond}\n"
            f"GENERAL.UUID:                           {uid}\n"
            f"GENERAL.DEVICES:                        {device_line}\n"
            f"GENERAL.STATE:                          {'activated' if configured else 'deactivated'}\n"
            f"GENERAL.DEFAULT:                        {'yes' if configured else 'no'}\n"
            f"GENERAL.DEFAULT6:                       no\n"
            f"GENERAL.SPEC-OBJECT:                    --\n"
            f"GENERAL.VPN:                            no\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Bond connection '{bond}' properties retrieved.",
        )
    else:
        # Show all connections — include a couple of representative entries
        stdout = (
            "NAME          UUID                                  TYPE      DEVICE \n"
            f"bond0         {_fake_uuid('bond0')}  bond      bond0  \n"
            f"bond0-port1   {_fake_uuid('bond0-port1')}  ethernet  eth0   \n"
            f"bond0-port2   {_fake_uuid('bond0-port2')}  ethernet  eth1   \n"
            f"bond1         {_fake_uuid('bond1')}  bond      --     \n"
            f"eth2          {_fake_uuid('eth2')}  ethernet  eth2   \n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="Bond and network connection list retrieved.",
        )


def _sim_add(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    bond = args.get("bond", "bond0")
    raw_mode = args.get("mode")
    mode: str = str(raw_mode) if raw_mode is not None else "active-backup"

    if _bond_not_found(bond):
        # Simulate an invalid name or NM error
        stderr = (
            f"Error: Failed to add connection: "
            f"invalid bond interface name '{bond}'.\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create bond connection '{bond}' (exit 2).",
        )

    uid = _fake_uuid(bond)
    stdout = f"Connection '{bond}' ({uid}) successfully added.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Bond connection '{bond}' created with mode '{mode}'.",
    )


def _sim_modify(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    bond = args.get("bond", "bond0")
    prop = args.get("property", "bond.options")
    value = args.get("value", "mode=active-backup")

    if _bond_not_found(bond):
        stderr = f"Error: No such connection profile '{bond}'.\n"
        return _make_result(
            exit_code=10,
            stdout="",
            stderr=stderr,
            summary=f"Failed to modify bond connection '{bond}' (exit 10).",
        )

    # nmcli connection modify exits 0 silently on success
    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Bond connection '{bond}' property '{prop}' updated to '{value}'.",
    )


def _sim_remove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    bond = args.get("bond", "bond0")

    if _bond_not_found(bond):
        stderr = f"Error: No such connection profile '{bond}'.\n"
        return _make_result(
            exit_code=10,
            stdout="",
            stderr=stderr,
            summary=f"Failed to delete bond connection '{bond}' (exit 10).",
        )

    stdout = f"Connection '{bond}' successfully deleted.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Bond connection '{bond}' deleted.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "show":   _sim_show,
    "add":    _sim_add,
    "modify": _sim_modify,
    "remove": _sim_remove,
}


def simulate_bond(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'bond' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 4 real ops declared in the
           bond ToolSpec (show, add, modify, remove).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'bond_connections'/'hostname' etc.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_bond: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
