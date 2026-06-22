"""core/tools/disk.py — block-device and filesystem management tool.

Supported operations
--------------------
  usage     (READ)        — show free/used space per filesystem (df).
  list      (READ)        — list block devices and their layout (lsblk).
  smart     (READ)        — report drive health and attributes (smartctl).
  mount     (WRITE)       — attach a filesystem at a mount point.
  unmount   (WRITE)       — detach a mounted filesystem.
  format    (DESTRUCTIVE) — create a filesystem on a device ("mkfs.<fstype> <device>"),
                            which erases everything on it.
  partition (DESTRUCTIVE) — change the partition table of a device ("parted <device> ...").
  wipe      (DESTRUCTIVE) — erase filesystem signatures from a device ("wipefs -a <device>").
  dd_write  (DESTRUCTIVE) — write a source onto a device ("dd if=... of=<device>").

Permission mapping (Phase 6 spec; the EXISTING hardened classifier in
core/agent/permissions.py is the authority — see notes below):
  READ        : usage, list, smart
  WRITE       : mount, unmount
  DESTRUCTIVE : format, partition, wipe, dd_write

This tool carries the HIGHEST data-loss blast radius of the toolset: formatting,
re-partitioning, wiping, or dd'ing a device is irreversible. By construction
every destructive op shells out through a command vector whose literal form
(mkfs.<fstype> <device>, parted <device> ..., wipefs -a <device>,
dd if=... of=<device>) is exactly what the REPL's synthesize_command() renders
for the classifier, so the existing hardened classifier escalates each to
DESTRUCTIVE -> CONFIRM_TYPED. This module NEVER classifies, gates, or audits
anything itself (A3): it builds a command vector, runs it via run_subprocess,
and returns a ToolResult.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a local
      binary; this module imports no device/disk Python libraries.
  I2  No AI/LLM/model/agent language in any user-facing string (every ToolSpec /
      OpSpec description and every ToolResult.summary).
  I3  The caller (REPL) resolves the permission gate BEFORE dispatch; this
      module does NOT call permissions.classify().
  I4  The caller writes the audit record; this module writes no audit entries.
  I6  Zero tier/product names anywhere in this file.
  I9  No operation raises out of execute(): every failure path degrades to a
      well-formed ToolResult.

Subprocess mocking
------------------
  Several of these binaries (mkfs/parted/wipefs/smartctl) are absent on the dev
  host. Every test patches ``core.tools.disk.run_subprocess`` so no real process
  is launched. The tool is portable: it builds a command vector and calls
  ``run_subprocess``; it never inspects ``sys.platform`` and never touches a
  real device.
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
# SELinux hint detection (copied from services.py — AVC denials are likely on
# mount/format/wipe operations against labelled devices)
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

def _op_usage(args: dict[str, Any]) -> ToolResult:
    """df -h [<path>] — free/used space per filesystem."""
    cmd = ["df", "-h"]
    path = args.get("path")
    if path:
        cmd.append(str(path))
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        # Header line plus one line per filesystem; subtract the header.
        rows = max(0, result.stdout.count("\n") - 1)
        summary = f"Reported space usage for {rows} filesystem(s)."
    else:
        summary = f"Space usage query failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_list(args: dict[str, Any]) -> ToolResult:
    """lsblk [-f] [<device>] — list block devices and their layout."""
    cmd = ["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT"]
    device = args.get("device")
    if device:
        cmd.append(str(device))
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        rows = max(0, result.stdout.count("\n") - 1)
        summary = f"Listed {rows} block device entry(ies)."
    else:
        summary = f"Block device listing failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_smart(args: dict[str, Any]) -> ToolResult:
    """smartctl -H -A <device> — drive health and attributes."""
    device: str = args["device"]
    result = run_subprocess(["smartctl", "-H", "-A", device])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Reported drive health for '{device}'."
    else:
        # smartctl uses a bitmask exit code; a nonzero code can still carry
        # useful health data, so we report the device and the code plainly.
        summary = (
            f"Drive health for '{device}' returned status exit {result.exit_code}."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_mount(args: dict[str, Any]) -> ToolResult:
    """mount <device> <mount_point> — attach a filesystem."""
    device: str = args["device"]
    mount_point: str = args["mount_point"]
    result = run_subprocess(["mount", device, mount_point])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Mounted '{device}' at '{mount_point}'."
    else:
        summary = (
            f"Failed to mount '{device}' at '{mount_point}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_unmount(args: dict[str, Any]) -> ToolResult:
    """umount <target> — detach a mounted filesystem (device or mount point)."""
    target: str = args["target"]
    result = run_subprocess(["umount", target])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Unmounted '{target}'."
    else:
        summary = f"Failed to unmount '{target}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_format(args: dict[str, Any]) -> ToolResult:
    """mkfs.<fstype> <device> — create a filesystem (erases the device).

    The command vector's program name is literally ``mkfs.<fstype>`` so the
    classifier sees the real destructive shape via synthesize_command().
    """
    device: str = args["device"]
    fstype: str = args.get("fstype", "ext4")
    result = run_subprocess([f"mkfs.{fstype}", device])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Created a {fstype} filesystem on '{device}'."
    else:
        summary = (
            f"Failed to create a {fstype} filesystem on '{device}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_partition(args: dict[str, Any]) -> ToolResult:
    """parted <device> <command...> — change a device's partition table.

    ``command`` is a list of literal parted directives (e.g.
    ["mklabel", "gpt"] or ["rm", "1"]). Each is appended as a separate argv
    token so nothing is passed through a shell.
    """
    device: str = args["device"]
    raw_cmd = args.get("command") or []
    if isinstance(raw_cmd, str):
        parted_cmd = raw_cmd.split()
    else:
        parted_cmd = [str(c) for c in raw_cmd]
    result = run_subprocess(["parted", device, *parted_cmd])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Applied partition table change to '{device}'."
    else:
        summary = (
            f"Partition table change on '{device}' failed (exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_wipe(args: dict[str, Any]) -> ToolResult:
    """wipefs -a <device> — erase all filesystem signatures from a device."""
    device: str = args["device"]
    result = run_subprocess(["wipefs", "-a", device])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Erased filesystem signatures from '{device}'."
    else:
        summary = (
            f"Failed to erase filesystem signatures from '{device}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_dd_write(args: dict[str, Any]) -> ToolResult:
    """dd if=<source> of=<device> [bs=...] — write a source onto a device.

    The classifier recognizes ``dd ... of=<block device>`` as DESTRUCTIVE via
    synthesize_command(); the command vector mirrors that literal shape.
    """
    source: str = args["source"]
    device: str = args["device"]
    bs = args.get("bs", "4M")
    cmd = ["dd", f"if={source}", f"of={device}", f"bs={bs}"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Wrote '{source}' onto '{device}'."
    else:
        summary = (
            f"Failed to write '{source}' onto '{device}' "
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
    "usage": _op_usage,
    "list": _op_list,
    "smart": _op_smart,
    "mount": _op_mount,
    "unmount": _op_unmount,
    "format": _op_format,
    "partition": _op_partition,
    "wipe": _op_wipe,
    "dd_write": _op_dd_write,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a disk operation and return a structured ToolResult.

    The caller (REPL) is responsible for:
      1. Resolving the permission gate via permissions.classify() against the
         command line synthesize_command() renders for this (tool, op, args).
      2. Writing the audit record.

    This function builds a command vector, runs the subprocess, and returns a
    ToolResult. It never classifies, gates, or audits (A3 / I3 / I4) and never
    raises (I9): an unknown op degrades to a well-formed error ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for disk tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_DEVICE_ARG = ArgSpec(
    name="device",
    type=str,
    required=True,
    description="The block device path (e.g. '/dev/sdb1', '/dev/nvme0n1p2').",
)

TOOL_SPEC = ToolSpec(
    name="disk",
    description="Inspect and manage block devices and filesystems.",
    ops={
        "usage": OpSpec(
            op_name="usage",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="path",
                    type=str,
                    required=False,
                    description="Limit the report to the filesystem holding this path.",
                ),
            ],
            description="Show free and used space per filesystem.",
        ),
        "list": OpSpec(
            op_name="list",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="device",
                    type=str,
                    required=False,
                    description="Limit the listing to a single block device.",
                ),
            ],
            description="List block devices and their partition layout.",
        ),
        "smart": OpSpec(
            op_name="smart",
            permission_class=OpClass.READ,
            args=[_DEVICE_ARG],
            description="Report a drive's health status and attributes.",
        ),
        "mount": OpSpec(
            op_name="mount",
            permission_class=OpClass.WRITE,
            args=[
                _DEVICE_ARG,
                ArgSpec(
                    name="mount_point",
                    type=str,
                    required=True,
                    description="The directory to attach the filesystem at.",
                ),
            ],
            description="Attach a filesystem at a mount point.",
        ),
        "unmount": OpSpec(
            op_name="unmount",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="target",
                    type=str,
                    required=True,
                    description="The device or mount point to detach.",
                ),
            ],
            description="Detach a mounted filesystem.",
        ),
        "format": OpSpec(
            op_name="format",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                _DEVICE_ARG,
                ArgSpec(
                    name="fstype",
                    type=str,
                    required=False,
                    description="Filesystem type to create (e.g. 'ext4', 'xfs'). Default ext4.",
                    default="ext4",
                ),
            ],
            description="Create a filesystem on a device, erasing everything on it.",
        ),
        "partition": OpSpec(
            op_name="partition",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                _DEVICE_ARG,
                ArgSpec(
                    name="command",
                    type=list,
                    required=False,
                    description="Partition directives to apply (e.g. ['mklabel', 'msdos']).",
                ),
            ],
            description="Change a device's partition table.",
        ),
        "wipe": OpSpec(
            op_name="wipe",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_DEVICE_ARG],
            description="Erase all filesystem signatures from a device.",
        ),
        "dd_write": OpSpec(
            op_name="dd_write",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                ArgSpec(
                    name="source",
                    type=str,
                    required=True,
                    description="The source file or image to read from.",
                ),
                _DEVICE_ARG,
                ArgSpec(
                    name="bs",
                    type=str,
                    required=False,
                    description="Block size for the copy (default '4M').",
                    default="4M",
                ),
            ],
            description="Write a source file or image onto a device, overwriting it.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(TOOL_SPEC)
