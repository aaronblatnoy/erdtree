"""core/tools/grub.py — GRUB bootloader inspection and configuration via grubby and grub2-mkconfig.

Supported operations
--------------------
  info           (READ)        — show grubby entry/entries for a kernel path or ALL.
  default-kernel (READ)        — print the current default kernel path.
  set-default    (WRITE)       — set the default boot kernel (grubby --set-default).
  args-add       (WRITE)       — add kernel command-line arguments (grubby --args).
  args-remove    (WRITE)       — remove kernel command-line arguments (grubby --remove-args).
  mkconfig       (DESTRUCTIVE) — regenerate /boot/grub2/grub.cfg via grub2-mkconfig.
  set-password   (WRITE)       — set the GRUB bootloader password via grub2-setpassword.
  remove-kernel  (DESTRUCTIVE) — remove a kernel entry from the GRUB menu (grubby --remove-kernel).

Permission mapping (advisory; Phase 1 classifier is authoritative):
  READ        : info, default-kernel
  WRITE       : set-default, args-add, args-remove, set-password
  DESTRUCTIVE : mkconfig, remove-kernel

Note on destructive ops
  grub2-mkconfig regenerates the bootloader configuration from scratch; a broken
  template can make the host unbootable (KNOWN to permissions classifier).
  grubby --remove-kernel removes a kernel entry; removing the only bootable kernel
  leaves the host unbootable (UNKNOWN to classifier until Phase 1 extends rules).

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
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_info(args: dict[str, Any]) -> ToolResult:
    """grubby --info=<kernel|ALL>"""
    kernel: str = args.get("kernel", "ALL")
    result = run_subprocess(["grubby", f"--info={kernel}"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Retrieved GRUB entry information for '{kernel}'."
    else:
        summary = f"Failed to retrieve GRUB entry information for '{kernel}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_default_kernel(args: dict[str, Any]) -> ToolResult:
    """grubby --default-kernel"""
    result = run_subprocess(["grubby", "--default-kernel"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        path = result.stdout.strip()
        summary = f"Default kernel is '{path}'." if path else "Default kernel path retrieved."
    else:
        summary = f"Failed to retrieve the default kernel (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_default(args: dict[str, Any]) -> ToolResult:
    """grubby --set-default=<kernel>"""
    kernel: str = args["kernel"]
    result = run_subprocess(["grubby", f"--set-default={kernel}"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Default boot kernel set to '{kernel}'."
    else:
        summary = f"Failed to set default kernel to '{kernel}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_args_add(args: dict[str, Any]) -> ToolResult:
    """grubby --update-kernel=<kernel> --args=<args>"""
    kernel: str = args["kernel"]
    kernel_args: str = args["kernel_args"]
    result = run_subprocess(
        ["grubby", f"--update-kernel={kernel}", f"--args={kernel_args}"]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Kernel arguments '{kernel_args}' added to '{kernel}'."
    else:
        summary = (
            f"Failed to add kernel arguments '{kernel_args}' to '{kernel}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_args_remove(args: dict[str, Any]) -> ToolResult:
    """grubby --update-kernel=<kernel> --remove-args=<args>"""
    kernel: str = args["kernel"]
    kernel_args: str = args["kernel_args"]
    result = run_subprocess(
        ["grubby", f"--update-kernel={kernel}", f"--remove-args={kernel_args}"]
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Kernel arguments '{kernel_args}' removed from '{kernel}'."
    else:
        summary = (
            f"Failed to remove kernel arguments '{kernel_args}' from '{kernel}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_mkconfig(args: dict[str, Any]) -> ToolResult:
    """grub2-mkconfig -o /boot/grub2/grub.cfg"""
    output_file: str = args.get("output_file", "/boot/grub2/grub.cfg")
    result = run_subprocess(
        ["grub2-mkconfig", "-o", output_file],
        timeout=120,
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"GRUB configuration regenerated and written to '{output_file}'."
    else:
        summary = (
            f"Failed to regenerate GRUB configuration to '{output_file}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_set_password(args: dict[str, Any]) -> ToolResult:
    """grub2-setpassword — set the GRUB bootloader password."""
    password: str = args["password"]
    # grub2-setpassword prompts for the password twice on stdin
    result = run_subprocess(
        ["grub2-setpassword"],
        input=f"{password}\n{password}\n",
    )
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "GRUB bootloader password set successfully."
    else:
        summary = f"Failed to set GRUB bootloader password (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_remove_kernel(args: dict[str, Any]) -> ToolResult:
    """grubby --remove-kernel=<kernel>"""
    kernel: str = args["kernel"]
    result = run_subprocess(["grubby", f"--remove-kernel={kernel}"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Kernel entry '{kernel}' removed from the boot menu."
    else:
        summary = (
            f"Failed to remove kernel entry '{kernel}' from the boot menu "
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
    "info":           _op_info,
    "default-kernel": _op_default_kernel,
    "set-default":    _op_set_default,
    "args-add":       _op_args_add,
    "args-remove":    _op_args_remove,
    "mkconfig":       _op_mkconfig,
    "set-password":   _op_set_password,
    "remove-kernel":  _op_remove_kernel,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a grub operation and return a structured ToolResult.

    The caller (Phase 4 router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function never calls permissions.classify() (I3) and never writes
    audit records (I4).  It never raises (I9): unknown ops and subprocess
    failures both degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for grub tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# Shared ArgSpec constants
# ---------------------------------------------------------------------------

_KERNEL_ARG = ArgSpec(
    name="kernel",
    type=str,
    required=True,
    description=(
        "Kernel path (e.g. '/boot/vmlinuz-5.14.0-362.13.1.el9_3.x86_64') "
        "or 'ALL' to target all entries."
    ),
)

_KERNEL_ARG_OPTIONAL = ArgSpec(
    name="kernel",
    type=str,
    required=False,
    description="Kernel path or 'ALL' (default: 'ALL').",
    default="ALL",
)

_KERNEL_ARGS_ARG = ArgSpec(
    name="kernel_args",
    type=str,
    required=True,
    description="Space-separated kernel command-line arguments (e.g. 'quiet splash').",
)

# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

GRUB_SPEC = ToolSpec(
    name="grub",
    description=(
        "Inspect and configure the GRUB bootloader via grubby and grub2-mkconfig."
    ),
    ops={
        "info": OpSpec(
            op_name="info",
            permission_class=OpClass.READ,
            args=[_KERNEL_ARG_OPTIONAL],
            description="Show GRUB boot entry details for a kernel path or ALL entries.",
        ),
        "default-kernel": OpSpec(
            op_name="default-kernel",
            permission_class=OpClass.READ,
            args=[],
            description="Print the current default boot kernel path.",
        ),
        "set-default": OpSpec(
            op_name="set-default",
            permission_class=OpClass.WRITE,
            args=[_KERNEL_ARG],
            description="Set the default boot kernel to the specified kernel path.",
        ),
        "args-add": OpSpec(
            op_name="args-add",
            permission_class=OpClass.WRITE,
            args=[_KERNEL_ARG, _KERNEL_ARGS_ARG],
            description="Add kernel command-line arguments to the specified kernel entry.",
        ),
        "args-remove": OpSpec(
            op_name="args-remove",
            permission_class=OpClass.WRITE,
            args=[_KERNEL_ARG, _KERNEL_ARGS_ARG],
            description="Remove kernel command-line arguments from the specified kernel entry.",
        ),
        "mkconfig": OpSpec(
            op_name="mkconfig",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="output_file",
                    type=str,
                    required=False,
                    description="Output path for the generated config (default: /boot/grub2/grub.cfg).",
                    default="/boot/grub2/grub.cfg",
                ),
            ],
            description=(
                "Regenerate the GRUB configuration file via grub2-mkconfig. "
                "A bad template can make the host unbootable."
            ),
        ),
        "set-password": OpSpec(
            op_name="set-password",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="password",
                    type=str,
                    required=True,
                    description="The new GRUB bootloader password.",
                ),
            ],
            description="Set the GRUB bootloader password via grub2-setpassword.",
        ),
        "remove-kernel": OpSpec(
            op_name="remove-kernel",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_KERNEL_ARG],
            description=(
                "Remove a kernel entry from the GRUB boot menu. "
                "Removing the only bootable kernel can make the host unbootable."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(GRUB_SPEC)
