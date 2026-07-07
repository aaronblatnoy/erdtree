"""finetune/simulate/subscription.py — Rocky Linux 9 output simulator for the 'subscription' tool.

Public API
----------
simulate_subscription(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/subscription.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string from make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Correct subscription-manager exit codes and stdout/stderr for Rocky Linux 9.
* Failure branches: unregistered system, invalid credentials, unknown repo ID.
* Hash-based deterministic scatter provides variety across valid-looking inputs.
* ctx is used to determine whether the system is currently registered.

I2 compliance
-------------
All `summary` strings are I2-clean — no 'AI', 'LLM', 'model', 'agent',
'agentic', 'ollama', 'inference', or 'neural' in any user-facing string.

INV-read-only-core: imports NOTHING from core/ directly.
Does not import finetune.coreimports (avoids circular deps at Phase-13 wiring).
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


def _is_registered(ctx: Any) -> bool:
    """Return True if context indicates the system is currently registered."""
    if isinstance(ctx, dict):
        return ctx.get("subscription_registered", True)
    if isinstance(ctx, str):
        return "registered" in ctx.lower() and "not registered" not in ctx.lower()
    return True  # optimistic default for unknown context


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


def _hash_scatter(value: str, modulus: int) -> int:
    """Deterministic scatter to introduce variety in simulator outputs."""
    return int(hashlib.md5(value.encode()).hexdigest(), 16) % modulus


def _repo_exists(repo: str) -> bool:
    """Deterministically decide if a repo ID looks valid."""
    lower = repo.lower()
    for bad in ("bogus", "fake", "notfound", "invalid", "missing", "noexist"):
        if bad in lower:
            return False
    # Plausible RHEL/Rocky repo IDs contain hyphens
    if "-" not in repo:
        return False
    return True


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    registered = _is_registered(ctx)

    if not registered:
        stdout = (
            "+-------------------------------------------+\n"
            "   System Status Details\n"
            "+-------------------------------------------+\n"
            "Overall Status: Unknown\n\n"
            "System Purpose Status: Unknown\n"
        )
        stderr = (
            "This system is not yet registered. "
            "Try 'subscription-manager register --help' for more information.\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr=stderr,
            summary=(
                "System is not registered; subscription status is unknown. "
                "Register the system to attach subscriptions."
            ),
        )

    stdout = (
        "+-------------------------------------------+\n"
        "   System Status Details\n"
        "+-------------------------------------------+\n"
        "Overall Status: Current\n\n"
        "System Purpose Status: Not Specified\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="System subscription status retrieved successfully.",
    )


def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    what: str = args.get("what") or "consumed"
    if what not in ("consumed", "available"):
        what = "consumed"

    registered = _is_registered(ctx)
    if not registered:
        stderr = (
            "This system is not yet registered. "
            "Try 'subscription-manager register --help' for more information.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to list {what} subscriptions (exit 1); "
                "ensure the system is registered."
            ),
        )

    if what == "available":
        stdout = (
            "+-------------------------------------------+\n"
            "    Available Subscriptions\n"
            "+-------------------------------------------+\n"
            "Subscription Name:   Red Hat Enterprise Linux Server\n"
            "Provides:            Red Hat Enterprise Linux Server\n"
            "SKU:                 RH00001\n"
            "Contract:            12345678\n"
            "Pool ID:             8a85f99a7db4827e017dc88a08550f79\n"
            "Available:           10\n"
            "Suggested:           1\n"
            "Service Type:        L1-L3\n"
            "Roles:               Red Hat Enterprise Linux Server\n"
            "Service Level:       Premium\n"
            "Usage:               Production\n"
            "Add-ons:            \n"
            "Subscription Type:   Standard\n"
            "Starts:              06/01/2026\n"
            "Ends:                05/31/2027\n"
            "Entitlement Type:    Physical\n\n"
        )
    else:
        stdout = (
            "+-------------------------------------------+\n"
            "    Consumed Subscriptions\n"
            "+-------------------------------------------+\n"
            "Subscription Name:   Red Hat Enterprise Linux Server\n"
            "Provides:            Red Hat Enterprise Linux Server\n"
            "SKU:                 RH00001\n"
            "Contract:            12345678\n"
            "Account:             9876543\n"
            "Serial:              7654321098765432\n"
            "Pool ID:             8a85f99a7db4827e017dc88a08550f79\n"
            "Provides Management: No\n"
            "Active:              True\n"
            "Quantity Used:       1\n"
            "Service Type:        L1-L3\n"
            "Roles:               Red Hat Enterprise Linux Server\n"
            "Service Level:       Premium\n"
            "Status Details:      Subscription is current\n"
            "Subscription Type:   Standard\n"
            "Starts:              06/01/2026\n"
            "Ends:                05/31/2027\n"
            "System Type:         Physical\n\n"
        )

    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Listed {what} subscriptions for this system.",
    )


def _sim_register(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    username: str = args.get("username") or ""
    activationkey: str = args.get("activationkey") or ""
    org: str = args.get("org") or ""

    # Simulate failure if credentials look clearly invalid
    identifier = activationkey or username
    if not identifier:
        stderr = (
            "Error: You must provide a username and password to register.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                "System registration failed (exit 1); "
                "check credentials, organisation, or network access to the subscription server."
            ),
        )

    # Already registered — subscription-manager errors out
    registered = _is_registered(ctx)
    if registered:
        stderr = (
            "This system is already registered. "
            "Use --force to override.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                "System registration failed (exit 1); "
                "check credentials, organisation, or network access to the subscription server."
            ),
        )

    hostname = _hostname(ctx)
    org_display = org or "Default_Organization"
    stdout = (
        f"Registering to: subscription.rhsm.redhat.com:443/subscription\n"
        f"The system has been registered with ID: "
        f"a1b2c3d4-{_hash_scatter(identifier, 9999):04x}-4e5f-8a9b-c0d1e2f3a4b5\n"
        f"The registered system name is: {hostname}\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="System registered with the subscription server.",
    )


def _sim_unregister(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    registered = _is_registered(ctx)

    if not registered:
        stderr = (
            "This system is currently not registered.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                "Unregistration failed (exit 1); "
                "the system may already be unregistered or the server may be unreachable."
            ),
        )

    stdout = (
        "Unregistering from: subscription.rhsm.redhat.com:443/subscription\n"
        "System has been unregistered.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=(
            "System unregistered from the subscription server; "
            "all entitlements have been removed and content repos are no longer accessible."
        ),
    )


def _sim_repos_enable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    repo: str = args.get("repo", "unknown-repo")

    registered = _is_registered(ctx)
    if not registered:
        stderr = (
            "This system is not yet registered. "
            "Try 'subscription-manager register --help' for more information.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to enable repository '{repo}' (exit 1); "
                "verify the repository ID and that the system has an appropriate subscription."
            ),
        )

    if not _repo_exists(repo):
        stdout = (
            f"Error: 'enable' is not allowed for repository '{repo}'.\n"
            f"Use 'subscription-manager repos --list' to see available repositories.\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=(
                f"Failed to enable repository '{repo}' (exit 1); "
                "verify the repository ID and that the system has an appropriate subscription."
            ),
        )

    stdout = f"Repository '{repo}' is enabled for this system.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Repository '{repo}' enabled successfully.",
    )


def _sim_repos_disable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    repo: str = args.get("repo", "unknown-repo")

    registered = _is_registered(ctx)
    if not registered:
        stderr = (
            "This system is not yet registered. "
            "Try 'subscription-manager register --help' for more information.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to disable repository '{repo}' (exit 1); "
                "verify the repository ID and the system's registration status."
            ),
        )

    if not _repo_exists(repo):
        stdout = (
            f"Error: 'disable' is not allowed for repository '{repo}'.\n"
            f"Use 'subscription-manager repos --list' to see available repositories.\n"
        )
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary=(
                f"Failed to disable repository '{repo}' (exit 1); "
                "verify the repository ID and the system's registration status."
            ),
        )

    stdout = f"Repository '{repo}' is disabled for this system.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Repository '{repo}' disabled successfully.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status":        _sim_status,
    "list":          _sim_list,
    "register":      _sim_register,
    "unregister":    _sim_unregister,
    "repos_enable":  _sim_repos_enable,
    "repos_disable": _sim_repos_disable,
}


def simulate_subscription(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'subscription' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 6 real ops declared in
           core/tools/subscription.py.
    args : argument dict (may be sparse; per-op defaults are applied).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'subscription_registered', 'hostname', etc.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present. summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_subscription: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
