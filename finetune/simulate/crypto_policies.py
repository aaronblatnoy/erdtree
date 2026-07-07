"""finetune/simulate/crypto_policies.py — Rocky Linux 9 output simulator for the 'crypto_policies' tool.

Public API
----------
simulate_crypto_policies(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 5 real operations declared in core/tools/crypto_policies.py
           (get, list, set, fips-status, fips-enable)
    args : dict of op arguments (may be {} for all-optional ops)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Exit codes mirror real update-crypto-policies / fips-mode-setup behaviour:
    0 — success
    1 — operation failed or FIPS not enabled (fips-status)
    127 — binary not found
* Failure triggers are hash-based and deterministic, using the policy name
  for set operations.
* ctx is used to determine the current policy when available.

I2 compliance
-------------
All `summary` strings are I2-clean. No AI/LLM/model/agent language used.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_KNOWN_POLICIES = ["DEFAULT", "FUTURE", "LEGACY", "FIPS", "DEFAULT:NO-SHA1", "FIPS:NO-CAMELLIA"]


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


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _current_policy(ctx: Any) -> str:
    """Derive the active crypto policy from context."""
    if isinstance(ctx, dict):
        return ctx.get("crypto_policy", "DEFAULT")
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if "crypto" in line.lower() and "policy" in line.lower():
                for pol in _KNOWN_POLICIES:
                    if pol in line.upper():
                        return pol
    return "DEFAULT"


def _fips_enabled(ctx: Any) -> bool:
    """Return True if FIPS mode appears active in the context."""
    if isinstance(ctx, dict):
        return ctx.get("fips_enabled", False)
    if isinstance(ctx, str):
        lower = ctx.lower()
        return "fips" in lower and ("enabled" in lower or "active" in lower)
    return False


def _policy_invalid(policy: str) -> bool:
    """Deterministically decide if a policy name is unrecognised."""
    upper = policy.upper()
    for known in _KNOWN_POLICIES:
        if upper == known or upper.startswith(known + ":"):
            return False
    # Hash-based scatter: valid-looking but unknown names fail ~25% of the time
    h = int(hashlib.md5(policy.encode()).hexdigest(), 16)
    return h % 4 == 0


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_get(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate update-crypto-policies --show."""
    policy = _current_policy(ctx)
    stdout = f"{policy}\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Current crypto policy is '{policy}'.",
    )


def _sim_list(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate update-crypto-policies --list."""
    stdout = "\n".join(_KNOWN_POLICIES) + "\n"
    count = len(_KNOWN_POLICIES)
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Found {count} available crypto policies.",
    )


def _sim_set(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate update-crypto-policies --set <policy>."""
    policy = args.get("policy", "DEFAULT")

    # Simulate binary-not-found scenario for special token
    if "notfound" in policy.lower() or "missing" in policy.lower():
        stderr = "bash: update-crypto-policies: command not found\n"
        return _make_result(
            exit_code=127,
            stdout="",
            stderr=stderr,
            summary=f"'update-crypto-policies' binary not found; cannot set crypto policy.",
        )

    if _policy_invalid(policy):
        stderr = (
            f"Error: '{policy}' is not a valid crypto policy.\n"
            f"Available policies: {', '.join(_KNOWN_POLICIES)}\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to set crypto policy to '{policy}' — policy name not recognised (exit 1).",
        )

    stdout = (
        f"Setting system policy to {policy}\n"
        f"Note: System-wide crypto policies are applied on the next initscripts or services start.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Crypto policy set to '{policy}'.",
    )


def _sim_fips_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate fips-mode-setup --check."""
    enabled = _fips_enabled(ctx)

    if enabled:
        stdout = "FIPS mode is enabled.\n"
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="FIPS 140 mode is enabled on this system.",
        )
    else:
        stdout = "FIPS mode is disabled.\n"
        return _make_result(
            exit_code=1,
            stdout=stdout,
            stderr="",
            summary="FIPS 140 mode is not currently enabled (exit 1).",
        )


def _sim_fips_enable(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate fips-mode-setup --enable."""
    # Hash-based scatter: ~10% chance of a simulated failure (e.g. on a VM guest)
    host = _hostname(ctx)
    h = int(hashlib.md5(host.encode()).hexdigest(), 16)
    if h % 10 == 0:
        stderr = (
            "FIPS mode cannot be enabled on this system configuration.\n"
            "Ensure the system is running on a supported hardware platform.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary="Failed to enable FIPS 140 mode — unsupported system configuration (exit 1).",
        )

    stdout = (
        "Setting system policy to FIPS\n"
        "Note: Please reboot the system for the setting to take effect.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary="FIPS 140 mode enabled; a system reboot is required for changes to take effect.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "get":         _sim_get,
    "list":        _sim_list,
    "set":         _sim_set,
    "fips-status": _sim_fips_status,
    "fips-enable": _sim_fips_enable,
}


def simulate_crypto_policies(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'crypto_policies' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 5 real ops declared in
           core/tools/crypto_policies.py (get, list, set, fips-status, fips-enable).
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict with 'crypto_policy'/'fips_enabled' fields.

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
            f"simulate_crypto_policies: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
