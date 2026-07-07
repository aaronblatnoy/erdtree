"""core/tools/dnf_modules.py — DNF module stream management via 'dnf module'.

Supported operations
--------------------
  list     (READ)   — list available modules (optionally filtered by name).
  info     (READ)   — show detailed info for a module.
  enable   (WRITE)  — enable a module stream.
  disable  (WRITE)  — disable a module stream.
  install  (WRITE)  — install a module profile.
  reset    (WRITE)  — reset a module to the default stream/state.

Permission mapping:
  READ  : list, info
  WRITE : enable, disable, install, reset

Note on destructive scope:
  Package removal (dnf remove/erase/autoremove) is owned by the 'packages'
  tool.  This tool exposes NO remove op — only module metadata/stream ops.
  Per the DESTRUCTIVE-VERB-MANIFEST, dnf_modules has no DESTRUCTIVE verbs;
  the highest class here is WRITE.

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
# SELinux hint detection (copied verbatim from services.py)
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

_MODULE_ARG = ArgSpec(
    name="module",
    type=str,
    required=True,
    description=(
        "Module name, optionally with stream and/or profile "
        "(e.g. 'nodejs', 'nodejs:18', 'nodejs:18/development')."
    ),
)

_FILTER_ARG = ArgSpec(
    name="module",
    type=str,
    required=False,
    description="Optional module name to filter the listing (default: all modules).",
    default="",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """dnf module list [<module>] --assumeyes"""
    module: str = args.get("module") or ""
    cmd = ["dnf", "module", "list"]
    if module:
        cmd.append(module)
    result = run_subprocess(cmd, timeout=60)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = (
            f"Module listing retrieved{' for ' + module if module else ''}."
        )
    else:
        summary = (
            f"Failed to list modules"
            f"{' for ' + module if module else ''} (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_info(args: dict[str, Any]) -> ToolResult:
    """dnf module info <module>"""
    module: str = args["module"]
    result = run_subprocess(["dnf", "module", "info", module], timeout=60)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Module info retrieved for '{module}'."
    else:
        summary = f"Failed to retrieve info for module '{module}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_enable(args: dict[str, Any]) -> ToolResult:
    """dnf module enable <module> -y"""
    module: str = args["module"]
    result = run_subprocess(["dnf", "module", "enable", module, "-y"], timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Module '{module}' enabled."
    else:
        summary = f"Failed to enable module '{module}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_disable(args: dict[str, Any]) -> ToolResult:
    """dnf module disable <module> -y"""
    module: str = args["module"]
    result = run_subprocess(["dnf", "module", "disable", module, "-y"], timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Module '{module}' disabled."
    else:
        summary = f"Failed to disable module '{module}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_install(args: dict[str, Any]) -> ToolResult:
    """dnf module install <module>[:<stream>[/<profile>]] -y"""
    module: str = args["module"]
    result = run_subprocess(["dnf", "module", "install", module, "-y"], timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Module '{module}' installed."
    else:
        summary = f"Failed to install module '{module}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_reset(args: dict[str, Any]) -> ToolResult:
    """dnf module reset <module> -y"""
    module: str = args["module"]
    result = run_subprocess(["dnf", "module", "reset", module, "-y"], timeout=120)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Module '{module}' reset to default state."
    else:
        summary = f"Failed to reset module '{module}' (exit {result.exit_code})."
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
    "list": _op_list,
    "info": _op_info,
    "enable": _op_enable,
    "disable": _op_disable,
    "install": _op_install,
    "reset": _op_reset,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a dnf_modules operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    audit records.  This function never raises (I9): unknown ops degrade to
    a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for dnf_modules tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

DNF_MODULES_SPEC = ToolSpec(
    name="dnf_modules",
    description="Manage DNF module streams and profiles via 'dnf module'.",
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[_FILTER_ARG],
            description="List available DNF modules, optionally filtered by name.",
        ),
        "info": OpSpec(
            op_name="info",
            permission_class=OpClass.READ,
            args=[_MODULE_ARG],
            description="Show detailed information about a DNF module.",
        ),
        "enable": OpSpec(
            op_name="enable",
            permission_class=OpClass.WRITE,
            args=[_MODULE_ARG],
            description="Enable a DNF module stream (e.g. 'nodejs:18').",
        ),
        "disable": OpSpec(
            op_name="disable",
            permission_class=OpClass.WRITE,
            args=[_MODULE_ARG],
            description="Disable a DNF module stream.",
        ),
        "install": OpSpec(
            op_name="install",
            permission_class=OpClass.WRITE,
            args=[_MODULE_ARG],
            description="Install a DNF module profile (e.g. 'nodejs:18/development').",
        ),
        "reset": OpSpec(
            op_name="reset",
            permission_class=OpClass.WRITE,
            args=[_MODULE_ARG],
            description="Reset a DNF module to its default stream and state.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(DNF_MODULES_SPEC)
