"""core/tools/kernel_modules.py — Kernel module inspection and management.

Supported operations
--------------------
  lsmod          (READ)        — list currently loaded kernel modules.
  modinfo        (READ)        — show information about a kernel module.
  modprobe       (WRITE)       — load a kernel module into the running kernel.
  rmmod          (DESTRUCTIVE) — remove a loaded kernel module; unloading an
                                 active storage or network driver can wedge the
                                 host.
  modules-load.d (WRITE)       — persist a module name to /etc/modules-load.d/
                                 so it loads automatically at boot.

Permission mapping (advisory; Phase 1 classifier is authoritative):
  READ        : lsmod, modinfo
  WRITE       : modprobe, modules-load.d
  DESTRUCTIVE : rmmod

Design rules (load-bearing invariants):
  I1  No network.  Every effect goes through run_subprocess against a LOCAL
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
# Shared arg spec
# ---------------------------------------------------------------------------

_MODULE_ARG = ArgSpec(
    name="module",
    type=str,
    required=True,
    description="Kernel module name (e.g. 'nf_conntrack', 'br_netfilter').",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_lsmod(args: dict[str, Any]) -> ToolResult:
    """lsmod — list currently loaded kernel modules."""
    result = run_subprocess(["lsmod"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        lines = result.stdout.strip().splitlines()
        count = max(0, len(lines) - 1)  # first line is the header
        summary = f"Listed {count} loaded kernel modules."
    else:
        summary = f"Failed to list loaded kernel modules (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_modinfo(args: dict[str, Any]) -> ToolResult:
    """modinfo <module> — display module metadata."""
    module: str = args["module"]
    result = run_subprocess(["modinfo", module])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Module information retrieved for '{module}'."
    else:
        summary = (
            f"Failed to retrieve information for module '{module}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_modprobe(args: dict[str, Any]) -> ToolResult:
    """modprobe <module> — load a kernel module."""
    module: str = args["module"]
    result = run_subprocess(["modprobe", module])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Kernel module '{module}' loaded."
    else:
        summary = f"Failed to load kernel module '{module}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_rmmod(args: dict[str, Any]) -> ToolResult:
    """rmmod <module> — remove a loaded kernel module (DESTRUCTIVE)."""
    module: str = args["module"]
    result = run_subprocess(["rmmod", module])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Kernel module '{module}' removed."
    else:
        summary = f"Failed to remove kernel module '{module}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_modules_load_d(args: dict[str, Any]) -> ToolResult:
    """Write module name to /etc/modules-load.d/<filename>.conf for boot-time loading."""
    module: str = args["module"]
    raw_filename: str = args.get("filename") or module  # type: ignore[assignment]
    # Strip path separators to prevent directory traversal.
    safe_filename = raw_filename.replace("/", "_").replace("\\", "_")
    conf_path = f"/etc/modules-load.d/{safe_filename}.conf"
    result = run_subprocess(["tee", conf_path], input=module + "\n")
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Module '{module}' written to '{conf_path}' for persistent loading at boot."
    else:
        summary = (
            f"Failed to write module '{module}' to '{conf_path}' "
            f"(exit {result.exit_code})."
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
    "lsmod":          _op_lsmod,
    "modinfo":        _op_modinfo,
    "modprobe":       _op_modprobe,
    "rmmod":          _op_rmmod,
    "modules-load.d": _op_modules_load_d,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a kernel_modules operation and return a structured ToolResult.

    The caller (Phase 4 router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9): unknown ops and subprocess failures both degrade to
    well-formed ToolResult instances.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for kernel_modules tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

KERNEL_MODULES_SPEC = ToolSpec(
    name="kernel_modules",
    description=(
        "Inspect and manage kernel modules via lsmod, modinfo, modprobe, "
        "and rmmod on Rocky Linux 9."
    ),
    ops={
        "lsmod": OpSpec(
            op_name="lsmod",
            permission_class=OpClass.READ,
            args=[],
            description="List all currently loaded kernel modules.",
        ),
        "modinfo": OpSpec(
            op_name="modinfo",
            permission_class=OpClass.READ,
            args=[_MODULE_ARG],
            description="Show metadata (filename, version, parameters, dependencies) for a kernel module.",
        ),
        "modprobe": OpSpec(
            op_name="modprobe",
            permission_class=OpClass.WRITE,
            args=[_MODULE_ARG],
            description="Load a kernel module into the running kernel.",
        ),
        "rmmod": OpSpec(
            op_name="rmmod",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_MODULE_ARG],
            description=(
                "Remove a loaded kernel module.  Unloading a module that is "
                "actively in use by a storage or network driver can wedge the host."
            ),
        ),
        "modules-load.d": OpSpec(
            op_name="modules-load.d",
            permission_class=OpClass.WRITE,
            args=[
                _MODULE_ARG,
                ArgSpec(
                    name="filename",
                    type=str,
                    required=False,
                    description=(
                        "Config file base name under /etc/modules-load.d/ "
                        "(defaults to the module name; .conf extension is appended)."
                    ),
                    default=None,
                ),
            ],
            description=(
                "Persist a module name to /etc/modules-load.d/ so it is loaded "
                "automatically at every boot."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(KERNEL_MODULES_SPEC)
