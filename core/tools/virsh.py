"""core/tools/virsh.py — libvirt/KVM virtual machine management via virsh.

Supported operations
--------------------
  list         (READ)        — list all defined domains (VMs).
  dominfo      (READ)        — show detailed info for a domain.
  start        (WRITE)       — start a defined domain.
  shutdown     (WRITE)       — gracefully shut down a running domain.
  define       (WRITE)       — define a new domain from an XML file.
  destroy      (DESTRUCTIVE) — forcibly power off a running domain (abrupt stop).
  undefine     (DESTRUCTIVE) — remove a domain definition; optionally delete storage.
  pool-list    (READ)        — list all storage pools.
  pool-define  (WRITE)       — define a storage pool from an XML file.
  pool-destroy (DESTRUCTIVE) — stop and destroy a storage pool.

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
# SELinux hint detection (verbatim from canonical pattern)
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
    description="The name of the virtual machine domain (e.g. 'centos9-vm').",
)

_XMLFILE_ARG = ArgSpec(
    name="xmlfile",
    type=str,
    required=True,
    description="Path to the XML definition file (e.g. '/tmp/vm.xml').",
)

_POOL_ARG = ArgSpec(
    name="pool",
    type=str,
    required=True,
    description="The name of the storage pool (e.g. 'default').",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """virsh list --all"""
    result = run_subprocess(["virsh", "list", "--all"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Listed all defined virtual machine domains."
    else:
        summary = f"Failed to list virtual machine domains (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_dominfo(args: dict[str, Any]) -> ToolResult:
    """virsh dominfo <domain>"""
    domain: str = args["domain"]
    result = run_subprocess(["virsh", "dominfo", domain])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Retrieved domain info for '{domain}'."
    else:
        summary = f"Failed to get domain info for '{domain}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_start(args: dict[str, Any]) -> ToolResult:
    """virsh start <domain>"""
    domain: str = args["domain"]
    result = run_subprocess(["virsh", "start", domain])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Domain '{domain}' started."
    else:
        summary = f"Failed to start domain '{domain}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_shutdown(args: dict[str, Any]) -> ToolResult:
    """virsh shutdown <domain>"""
    domain: str = args["domain"]
    result = run_subprocess(["virsh", "shutdown", domain])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Shutdown signal sent to domain '{domain}'."
    else:
        summary = f"Failed to send shutdown signal to domain '{domain}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_define(args: dict[str, Any]) -> ToolResult:
    """virsh define <xmlfile>"""
    xmlfile: str = args["xmlfile"]
    result = run_subprocess(["virsh", "define", xmlfile])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Domain defined from XML file '{xmlfile}'."
    else:
        summary = f"Failed to define domain from '{xmlfile}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_destroy(args: dict[str, Any]) -> ToolResult:
    """virsh destroy <domain> — DESTRUCTIVE: abrupt power-off, potential data loss."""
    domain: str = args["domain"]
    result = run_subprocess(["virsh", "destroy", domain])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Domain '{domain}' forcibly powered off."
    else:
        summary = f"Failed to destroy domain '{domain}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_undefine(args: dict[str, Any]) -> ToolResult:
    """virsh undefine <domain> [--remove-all-storage] — DESTRUCTIVE."""
    domain: str = args["domain"]
    remove_storage: bool = bool(args.get("remove_storage", False))
    cmd = ["virsh", "undefine", domain]
    if remove_storage:
        cmd.append("--remove-all-storage")
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        if remove_storage:
            summary = f"Domain '{domain}' undefined and all associated storage removed."
        else:
            summary = f"Domain '{domain}' undefined; disk images were not removed."
    else:
        summary = f"Failed to undefine domain '{domain}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pool_list(args: dict[str, Any]) -> ToolResult:
    """virsh pool-list --all"""
    result = run_subprocess(["virsh", "pool-list", "--all"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "Listed all storage pools."
    else:
        summary = f"Failed to list storage pools (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pool_define(args: dict[str, Any]) -> ToolResult:
    """virsh pool-define <xmlfile>"""
    xmlfile: str = args["xmlfile"]
    result = run_subprocess(["virsh", "pool-define", xmlfile])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Storage pool defined from XML file '{xmlfile}'."
    else:
        summary = f"Failed to define storage pool from '{xmlfile}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pool_destroy(args: dict[str, Any]) -> ToolResult:
    """virsh pool-destroy <pool> — DESTRUCTIVE: stops the pool and drops access to its volumes."""
    pool: str = args["pool"]
    result = run_subprocess(["virsh", "pool-destroy", pool])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Storage pool '{pool}' destroyed (stopped and deactivated)."
    else:
        summary = f"Failed to destroy storage pool '{pool}' (exit {result.exit_code})."
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
    "list":         _op_list,
    "dominfo":      _op_dominfo,
    "start":        _op_start,
    "shutdown":     _op_shutdown,
    "define":       _op_define,
    "destroy":      _op_destroy,
    "undefine":     _op_undefine,
    "pool-list":    _op_pool_list,
    "pool-define":  _op_pool_define,
    "pool-destroy": _op_pool_destroy,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a virsh operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9): unknown ops and missing binaries all
    degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for virsh tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

VIRSH_SPEC = ToolSpec(
    name="virsh",
    description="Manage KVM/libvirt virtual machines and storage pools via virsh.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[],
            description="List all defined virtual machine domains.",
        ),
        "dominfo": OpSpec(
            op_name="dominfo",
            permission_class=OpClass.READ,
            args=[_DOMAIN_ARG],
            description="Show detailed information for a virtual machine domain.",
        ),
        "start": OpSpec(
            op_name="start",
            permission_class=OpClass.WRITE,
            args=[_DOMAIN_ARG],
            description="Start a defined virtual machine domain.",
        ),
        "shutdown": OpSpec(
            op_name="shutdown",
            permission_class=OpClass.WRITE,
            args=[_DOMAIN_ARG],
            description="Send a graceful shutdown signal to a running domain.",
        ),
        "define": OpSpec(
            op_name="define",
            permission_class=OpClass.WRITE,
            args=[_XMLFILE_ARG],
            description="Define a new virtual machine domain from an XML configuration file.",
        ),
        "destroy": OpSpec(
            op_name="destroy",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_DOMAIN_ARG],
            description=(
                "Forcibly power off a running domain (abrupt stop — "
                "risks data corruption and service outage)."
            ),
        ),
        "undefine": OpSpec(
            op_name="undefine",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                _DOMAIN_ARG,
                ArgSpec(
                    name="remove_storage",
                    type=bool,
                    required=False,
                    description=(
                        "If True, also delete all storage volumes associated with the domain "
                        "(permanent data loss). Default: False."
                    ),
                    default=False,
                ),
            ],
            description=(
                "Remove a domain definition. With remove_storage=True also deletes "
                "all associated disk images (irreversible)."
            ),
        ),
        "pool-list": OpSpec(
            op_name="pool-list",
            permission_class=OpClass.READ,
            args=[],
            description="List all defined libvirt storage pools.",
        ),
        "pool-define": OpSpec(
            op_name="pool-define",
            permission_class=OpClass.WRITE,
            args=[_XMLFILE_ARG],
            description="Define a new storage pool from an XML configuration file.",
        ),
        "pool-destroy": OpSpec(
            op_name="pool-destroy",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_POOL_ARG],
            description=(
                "Stop and destroy a storage pool, dropping access to all its volumes "
                "(irreversible while the pool is destroyed)."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(VIRSH_SPEC)
