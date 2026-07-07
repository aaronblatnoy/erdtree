"""core/tools/crypto_policies.py — system-wide cryptographic policy management via update-crypto-policies and fips-mode-setup.

Supported operations
--------------------
  get           (READ)  — show the currently active crypto policy.
  list          (READ)  — list all available crypto policy names.
  set           (WRITE) — apply a named crypto policy system-wide.
  fips-status   (READ)  — report whether FIPS 140 mode is currently enabled.
  fips-enable   (WRITE) — enable FIPS 140 mode (requires reboot to take effect).

Permission mapping:
  READ  : get, list, fips-status
  WRITE : set, fips-enable

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

def _op_get(args: dict[str, Any]) -> ToolResult:
    """update-crypto-policies --show — display the active policy."""
    result = run_subprocess(["update-crypto-policies", "--show"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        policy = result.stdout.strip() or "UNKNOWN"
        summary = f"Current crypto policy is '{policy}'."
    else:
        summary = f"Failed to retrieve the current crypto policy (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_list(args: dict[str, Any]) -> ToolResult:
    """update-crypto-policies --list — list available policies."""
    result = run_subprocess(["update-crypto-policies", "--list"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        policies = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        count = len(policies)
        summary = f"Found {count} available crypto {'policy' if count == 1 else 'policies'}."
    else:
        summary = f"Failed to list crypto policies (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set(args: dict[str, Any]) -> ToolResult:
    """update-crypto-policies --set <policy> — apply a policy system-wide."""
    policy: str = args["policy"]
    result = run_subprocess(["update-crypto-policies", "--set", policy])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Crypto policy set to '{policy}'."
    else:
        summary = f"Failed to set crypto policy to '{policy}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_fips_status(args: dict[str, Any]) -> ToolResult:
    """fips-mode-setup --check — report FIPS 140 mode state."""
    result = run_subprocess(["fips-mode-setup", "--check"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "FIPS 140 mode is enabled on this system."
    else:
        # exit 1 means FIPS is not enabled (normal, non-error state)
        summary = f"FIPS 140 mode is not currently enabled (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_fips_enable(args: dict[str, Any]) -> ToolResult:
    """fips-mode-setup --enable — enable FIPS 140 mode (reboot required)."""
    result = run_subprocess(["fips-mode-setup", "--enable"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "FIPS 140 mode enabled; a system reboot is required for changes to take effect."
    else:
        summary = f"Failed to enable FIPS 140 mode (exit {result.exit_code})."
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
    "get":          _op_get,
    "list":         _op_list,
    "set":          _op_set,
    "fips-status":  _op_fips_status,
    "fips-enable":  _op_fips_enable,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a crypto_policies operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9): unknown ops and subprocess failures both degrade
    to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for crypto_policies tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_POLICY_ARG = ArgSpec(
    name="policy",
    type=str,
    required=True,
    description="Crypto policy name (e.g. DEFAULT, FUTURE, LEGACY, FIPS).",
)

CRYPTO_POLICIES_SPEC = ToolSpec(
    name="crypto_policies",
    description="Manage system-wide cryptographic policies via update-crypto-policies and fips-mode-setup.",
    ops={
        "get": OpSpec(
            op_name="get",
            permission_class=OpClass.READ,
            args=[],
            description="Show the currently active system crypto policy.",
        ),
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[],
            description="List all available crypto policy names.",
        ),
        "set": OpSpec(
            op_name="set",
            permission_class=OpClass.WRITE,
            args=[_POLICY_ARG],
            description="Apply a named crypto policy system-wide.",
        ),
        "fips-status": OpSpec(
            op_name="fips-status",
            permission_class=OpClass.READ,
            args=[],
            description="Report whether FIPS 140 mode is currently enabled.",
        ),
        "fips-enable": OpSpec(
            op_name="fips-enable",
            permission_class=OpClass.WRITE,
            args=[],
            description="Enable FIPS 140 mode; a reboot is required to take effect.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(CRYPTO_POLICIES_SPEC)
