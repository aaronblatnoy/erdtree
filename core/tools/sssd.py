"""core/tools/sssd.py — SSSD / realm identity management tool.

Supported operations
--------------------
  status      (READ)        — show the running status of the sssd daemon.
  id_lookup   (READ)        — look up a user or group identity via NSS/sssd.
  cache_flush  (WRITE)      — flush the sssd cache (sss_cache -E).
  realm_list  (READ)        — list enrolled or discovered realms.
  realm_join  (WRITE)       — enroll this host into an AD/IdM domain.
  realm_leave (DESTRUCTIVE) — remove this host from an AD/IdM domain; locks out
                              all domain-account logins until re-enrolled.

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
# SELinux hint detection (VERBATIM from services.py)
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
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_DOMAIN_ARG = ArgSpec(
    name="domain",
    type=str,
    required=True,
    description="The AD/IdM domain name (e.g. 'corp.example.com').",
)

_USER_ARG = ArgSpec(
    name="user",
    type=str,
    required=True,
    description="The username or group name to look up.",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_status(args: dict[str, Any]) -> ToolResult:
    """systemctl status sssd --no-pager"""
    result = run_subprocess(["systemctl", "status", "--no-pager", "sssd"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "The sssd daemon is active and running."
    else:
        summary = f"The sssd daemon reported a non-zero status (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_id_lookup(args: dict[str, Any]) -> ToolResult:
    """id <user>"""
    user: str = args["user"]
    result = run_subprocess(["id", user])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Identity information retrieved for '{user}'."
    else:
        summary = f"Identity lookup failed for '{user}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_cache_flush(args: dict[str, Any]) -> ToolResult:
    """sss_cache -E  (flush all sssd caches)"""
    result = run_subprocess(["sss_cache", "-E"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "The sssd cache was flushed successfully."
    else:
        summary = f"sssd cache flush failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_realm_list(args: dict[str, Any]) -> ToolResult:
    """realm list"""
    result = run_subprocess(["realm", "list"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        if result.stdout.strip():
            summary = "Enrolled realm information retrieved."
        else:
            summary = "No realms are currently enrolled on this host."
    else:
        summary = f"realm list failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_realm_join(args: dict[str, Any]) -> ToolResult:
    """realm join <domain>"""
    domain: str = args["domain"]
    result = run_subprocess(["realm", "join", domain])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Host successfully enrolled in domain '{domain}'."
    else:
        summary = f"Failed to join domain '{domain}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_realm_leave(args: dict[str, Any]) -> ToolResult:
    """realm leave <domain>  — DESTRUCTIVE: removes domain auth for all domain accounts."""
    domain: str = args["domain"]
    result = run_subprocess(["realm", "leave", domain])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Host removed from domain '{domain}'. "
            "Domain account logins are no longer available on this host."
        )
    else:
        summary = f"Failed to leave domain '{domain}' (exit {result.exit_code})."
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
    "id_lookup": _op_id_lookup,
    "cache_flush": _op_cache_flush,
    "realm_list": _op_realm_list,
    "realm_join": _op_realm_join,
    "realm_leave": _op_realm_leave,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an sssd operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record. This function never raises (I9): unknown ops and all
    subprocess failures degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for sssd tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

SSSD_SPEC = ToolSpec(
    name="sssd",
    description="Manage SSSD identity services, realm enrollment, and identity cache.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the running status of the sssd daemon.",
        ),
        "id_lookup": OpSpec(
            op_name="id_lookup",
            permission_class=OpClass.READ,
            args=[_USER_ARG],
            description="Look up a user or group identity through sssd/NSS.",
        ),
        "cache_flush": OpSpec(
            op_name="cache_flush",
            permission_class=OpClass.WRITE,
            args=[],
            description="Flush all sssd caches (sss_cache -E).",
        ),
        "realm_list": OpSpec(
            op_name="realm_list",
            permission_class=OpClass.READ,
            args=[],
            description="List enrolled or discovered AD/IdM realms on this host.",
        ),
        "realm_join": OpSpec(
            op_name="realm_join",
            permission_class=OpClass.WRITE,
            args=[_DOMAIN_ARG],
            description="Enroll this host into an AD/IdM domain.",
        ),
        "realm_leave": OpSpec(
            op_name="realm_leave",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_DOMAIN_ARG],
            description=(
                "Remove this host from an AD/IdM domain. "
                "All domain-account logins will be unavailable until the host is re-enrolled."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SSSD_SPEC)
