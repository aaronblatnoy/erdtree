"""core/tools/sysctl.py — Kernel parameter inspection and configuration via sysctl.

Supported operations
--------------------
  list    (READ)  — list all kernel parameters (sysctl -a).
  get     (READ)  — read the current value of a single kernel parameter.
  set     (WRITE) — write a kernel parameter at runtime (sysctl -w); not persistent.
  persist (WRITE) — write a kernel parameter to /etc/sysctl.d/ and reload.

Permission mapping (advisory; Phase 1 classifier is authoritative):
  READ  : list, get
  WRITE : set, persist

Note on critical kernel parameters
  Writing certain kernel parameters (kernel.panic, kernel.sysrq,
  kernel.modules_disabled, net.ipv4.ip_forward, vm.overcommit_memory,
  kernel.core_pattern, net.ipv4.conf.all.rp_filter, kernel.kexec_load_disabled)
  can alter host security posture or, in the case of kernel.modules_disabled,
  permanently disable module loading until reboot.  Phase 1 (permissions.py)
  will escalate writes to those keys to DESTRUCTIVE.  The OpSpec labels here
  are WRITE per the plan table.

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
# Shared ArgSpecs
# ---------------------------------------------------------------------------

_KEY_ARG = ArgSpec(
    name="key",
    type=str,
    required=True,
    description="Kernel parameter name (e.g. 'net.ipv4.ip_forward').",
)

_VALUE_ARG = ArgSpec(
    name="value",
    type=str,
    required=True,
    description="Value to assign to the kernel parameter.",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_list(args: dict[str, Any]) -> ToolResult:
    """sysctl -a — list all current kernel parameters and their values."""
    result = run_subprocess(["sysctl", "-a"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        count = result.stdout.count("\n")
        summary = f"Listed {count} kernel parameters."
    else:
        summary = f"Failed to list kernel parameters (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_get(args: dict[str, Any]) -> ToolResult:
    """sysctl <key> — read a single kernel parameter value."""
    key: str = args["key"]
    result = run_subprocess(["sysctl", key])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Kernel parameter '{key}' read successfully."
    else:
        summary = f"Failed to read kernel parameter '{key}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set(args: dict[str, Any]) -> ToolResult:
    """sysctl -w key=value — set a kernel parameter at runtime (non-persistent)."""
    key: str = args["key"]
    value: str = args["value"]
    assignment = f"{key}={value}"
    result = run_subprocess(["sysctl", "-w", assignment])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Kernel parameter '{key}' set to '{value}' (runtime only; not persistent)."
    else:
        summary = (
            f"Failed to set kernel parameter '{key}' to '{value}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_persist(args: dict[str, Any]) -> ToolResult:
    """Write a kernel parameter to /etc/sysctl.d/ and reload via sysctl --system."""
    key: str = args["key"]
    value: str = args["value"]
    # Sanitise the key name for use as a filename component (replace dots with dashes)
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", key)
    filename = args.get("filename") or f"99-{safe_name}.conf"
    # Restrict to /etc/sysctl.d/ only
    if "/" in filename:
        filename = filename.rsplit("/", 1)[-1]
    filepath = f"/etc/sysctl.d/{filename}"
    content = f"{key} = {value}\n"

    # Write the drop-in file using tee (allows writing to root-owned paths)
    write_result = run_subprocess(["tee", filepath], input=content)
    selinux = _maybe_selinux_hint(write_result.stderr)
    if not write_result.ok:
        summary = (
            f"Failed to write '{key} = {value}' to {filepath} "
            f"(exit {write_result.exit_code})."
        )
        return ToolResult(
            exit_code=write_result.exit_code,
            stdout=write_result.stdout,
            stderr=write_result.stderr,
            summary=summary + selinux,
        )

    # Reload all sysctl.d drop-ins
    reload_result = run_subprocess(["sysctl", "--system"])
    selinux = selinux or _maybe_selinux_hint(reload_result.stderr)
    if reload_result.ok:
        summary = (
            f"Kernel parameter '{key}' set to '{value}' and persisted to {filepath}."
        )
    else:
        summary = (
            f"Parameter '{key} = {value}' written to {filepath} but sysctl --system "
            f"reload failed (exit {reload_result.exit_code})."
        )
    return ToolResult(
        exit_code=reload_result.exit_code,
        stdout=write_result.stdout + reload_result.stdout,
        stderr=write_result.stderr + reload_result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "list":    _op_list,
    "get":     _op_get,
    "set":     _op_set,
    "persist": _op_persist,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a sysctl operation and return a structured ToolResult.

    The caller is responsible for resolving the permission gate and writing
    the audit record.  This function never raises (I9).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for sysctl tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

SYSCTL_SPEC = ToolSpec(
    name="sysctl",
    description=(
        "Read and write Linux kernel parameters via sysctl; "
        "persist settings to /etc/sysctl.d/ drop-in files."
    ),
    ops={
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[],
            description="List all current kernel parameters and their values.",
        ),
        "get": OpSpec(
            op_name="get",
            permission_class=OpClass.READ,
            args=[_KEY_ARG],
            description="Read the current value of a single kernel parameter.",
        ),
        "set": OpSpec(
            op_name="set",
            permission_class=OpClass.WRITE,
            args=[_KEY_ARG, _VALUE_ARG],
            description=(
                "Set a kernel parameter at runtime via sysctl -w (not persistent; "
                "reverts on reboot)."
            ),
        ),
        "persist": OpSpec(
            op_name="persist",
            permission_class=OpClass.WRITE,
            args=[
                _KEY_ARG,
                _VALUE_ARG,
                ArgSpec(
                    name="filename",
                    type=str,
                    required=False,
                    description=(
                        "Drop-in filename under /etc/sysctl.d/ "
                        "(default: '99-<key>.conf')."
                    ),
                    default=None,
                ),
            ],
            description=(
                "Write a kernel parameter to /etc/sysctl.d/ and reload via "
                "sysctl --system so the change survives reboots."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(SYSCTL_SPEC)
