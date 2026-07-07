"""core/tools/subscription.py — Red Hat subscription and repository management via subscription-manager.

Supported operations
--------------------
  status        (READ)        — show the overall subscription status of the system.
  list          (READ)        — list consumed or available subscriptions.
  register      (WRITE)       — register this system with a subscription server.
  unregister    (DESTRUCTIVE) — remove all entitlements and unregister the system.
  repos_enable  (WRITE)       — enable one or more content repositories.
  repos_disable (WRITE)       — disable one or more content repositories.

Permission mapping:
  READ        : status, list
  WRITE       : register, repos_enable, repos_disable
  DESTRUCTIVE : unregister  (removes entitlements — lockout of repos/updates)

Note on unregister
  subscription-manager unregister removes this system's entitlements from the
  subscription server and destroys its local consumer certificate.  Re-registration
  is required before repositories become available again.  This is a lockout and is
  labelled DESTRUCTIVE per the manifest.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller (router / REPL) MUST resolve the permission gate BEFORE
      calling execute(); this module does NOT call permissions.classify().
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
# SELinux hint detection (copied verbatim from services.py per SLICE-CONTRACT §3)
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
    """subscription-manager status"""
    result = run_subprocess(["subscription-manager", "status"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "System subscription status retrieved successfully."
    else:
        summary = (
            f"Subscription status check returned exit {result.exit_code}; "
            "the system may not be registered or subscriptions may have expired."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_list(args: dict[str, Any]) -> ToolResult:
    """subscription-manager list [--consumed|--available]"""
    what: str = args.get("what") or "consumed"
    # Normalise — only allow the two valid options; fallback to consumed
    if what not in ("consumed", "available"):
        what = "consumed"
    flag = f"--{what}"
    result = run_subprocess(["subscription-manager", "list", flag])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Listed {what} subscriptions for this system."
    else:
        summary = (
            f"Failed to list {what} subscriptions (exit {result.exit_code}); "
            "ensure the system is registered."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_register(args: dict[str, Any]) -> ToolResult:
    """subscription-manager register [--username ...] [--password ...] [--org ...] [--activationkey ...]"""
    cmd = ["subscription-manager", "register"]

    username: str = args.get("username") or ""
    password: str = args.get("password") or ""
    org: str = args.get("org") or ""
    activationkey: str = args.get("activationkey") or ""

    if activationkey:
        cmd += ["--activationkey", activationkey]
        if org:
            cmd += ["--org", org]
    else:
        if username:
            cmd += ["--username", username]
        if password:
            cmd += ["--password", password]
        if org:
            cmd += ["--org", org]

    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "System registered with the subscription server."
    else:
        summary = (
            f"System registration failed (exit {result.exit_code}); "
            "check credentials, organisation, or network access to the subscription server."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_unregister(args: dict[str, Any]) -> ToolResult:
    """subscription-manager unregister — DESTRUCTIVE: removes all entitlements."""
    result = run_subprocess(["subscription-manager", "unregister"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            "System unregistered from the subscription server; "
            "all entitlements have been removed and content repos are no longer accessible."
        )
    else:
        summary = (
            f"Unregistration failed (exit {result.exit_code}); "
            "the system may already be unregistered or the server may be unreachable."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_repos_enable(args: dict[str, Any]) -> ToolResult:
    """subscription-manager repos --enable=<repo>"""
    repo: str = args["repo"]
    result = run_subprocess(["subscription-manager", "repos", f"--enable={repo}"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Repository '{repo}' enabled successfully."
    else:
        summary = (
            f"Failed to enable repository '{repo}' (exit {result.exit_code}); "
            "verify the repository ID and that the system has an appropriate subscription."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_repos_disable(args: dict[str, Any]) -> ToolResult:
    """subscription-manager repos --disable=<repo>"""
    repo: str = args["repo"]
    result = run_subprocess(["subscription-manager", "repos", f"--disable={repo}"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Repository '{repo}' disabled successfully."
    else:
        summary = (
            f"Failed to disable repository '{repo}' (exit {result.exit_code}); "
            "verify the repository ID and the system's registration status."
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
    "status":        _op_status,
    "list":          _op_list,
    "register":      _op_register,
    "unregister":    _op_unregister,
    "repos_enable":  _op_repos_enable,
    "repos_disable": _op_repos_disable,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a subscription operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9); all failures are returned as ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for subscription tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_REPO_ARG = ArgSpec(
    name="repo",
    type=str,
    required=True,
    description="Repository ID as shown by 'subscription-manager repos --list' (e.g. 'rhel-9-for-x86_64-baseos-rpms').",
)

# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

SUBSCRIPTION_SPEC = ToolSpec(
    name="subscription",
    description="Manage Red Hat subscriptions and content repositories via subscription-manager.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current subscription status of this system.",
        ),
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="what",
                    type=str,
                    required=False,
                    description="Which subscriptions to list: 'consumed' (default) or 'available'.",
                    default="consumed",
                ),
            ],
            description="List consumed or available subscriptions for this system.",
        ),
        "register": OpSpec(
            op_name="register",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="username",
                    type=str,
                    required=False,
                    description="Red Hat account username.",
                    default=None,
                ),
                ArgSpec(
                    name="password",
                    type=str,
                    required=False,
                    description="Red Hat account password.",
                    default=None,
                ),
                ArgSpec(
                    name="org",
                    type=str,
                    required=False,
                    description="Organisation ID for registration.",
                    default=None,
                ),
                ArgSpec(
                    name="activationkey",
                    type=str,
                    required=False,
                    description="Activation key for registration (alternative to username/password).",
                    default=None,
                ),
            ],
            description="Register this system with a Red Hat subscription server.",
        ),
        "unregister": OpSpec(
            op_name="unregister",
            permission_class=OpClass.DESTRUCTIVE,
            args=[],
            description=(
                "Unregister this system, removing all subscription entitlements. "
                "Content repositories become inaccessible until the system is re-registered."
            ),
        ),
        "repos_enable": OpSpec(
            op_name="repos_enable",
            permission_class=OpClass.WRITE,
            args=[_REPO_ARG],
            description="Enable a content repository for this system.",
        ),
        "repos_disable": OpSpec(
            op_name="repos_disable",
            permission_class=OpClass.WRITE,
            args=[_REPO_ARG],
            description="Disable a content repository for this system.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SUBSCRIPTION_SPEC)
