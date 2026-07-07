"""core/tools/lvm.py — LVM (Logical Volume Manager) tool.

Supported operations
--------------------
  pvdisplay  (READ)        — show physical volume attributes.
  vgdisplay  (READ)        — show volume group attributes.
  lvdisplay  (READ)        — show logical volume attributes.
  pvcreate   (WRITE)       — initialise a block device as an LVM physical volume.
  vgcreate   (WRITE)       — create a new volume group from one or more PVs.
  lvcreate   (WRITE)       — create a new logical volume in a volume group.
  lvextend   (WRITE)       — extend an existing logical volume.
  vgextend   (WRITE)       — add a physical volume to an existing volume group.
  pvremove   (DESTRUCTIVE) — remove a physical volume, destroying its data.
  vgremove   (DESTRUCTIVE) — remove a volume group and its contents.
  lvremove   (DESTRUCTIVE) — remove a logical volume, destroying its data.
  lvreduce   (DESTRUCTIVE) — shrink a logical volume; may destroy data.

Permission mapping (from the Phase 3 / DESTRUCTIVE-VERB-MANIFEST):
  READ        : pvdisplay, vgdisplay, lvdisplay
  WRITE       : pvcreate, vgcreate, lvcreate, lvextend, vgextend
  DESTRUCTIVE : pvremove, vgremove, lvremove, lvreduce

Overlap ruling (OVERLAP-MAP.md §Phase 3):
  This tool is the AUTHORITATIVE LVM tool.  It operates on PV/VG/LV objects
  only.  It does NOT call mkfs, parted, wipefs, or dd — those remain in
  core/tools/disk.py.  If a user wants a filesystem on an LV, direct them to
  disk.format on the LV device path.

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

_PV_ARG = ArgSpec(
    name="pv",
    type=str,
    required=True,
    description="Physical volume device path (e.g. '/dev/sdb', '/dev/sdb1').",
)

_PV_ARG_OPT = ArgSpec(
    name="pv",
    type=str,
    required=False,
    description="Physical volume device path (omit to display all PVs).",
    default=None,
)

_VG_ARG = ArgSpec(
    name="vg",
    type=str,
    required=True,
    description="Volume group name (e.g. 'vg_data').",
)

_VG_ARG_OPT = ArgSpec(
    name="vg",
    type=str,
    required=False,
    description="Volume group name (omit to display all VGs).",
    default=None,
)

_LV_ARG = ArgSpec(
    name="lv",
    type=str,
    required=True,
    description="Logical volume path (e.g. '/dev/vg_data/lv_home' or 'vg_data/lv_home').",
)

_LV_ARG_OPT = ArgSpec(
    name="lv",
    type=str,
    required=False,
    description="Logical volume path (omit to display all LVs).",
    default=None,
)

_SIZE_ARG = ArgSpec(
    name="size",
    type=str,
    required=True,
    description="Size specification (e.g. '10G', '500M', '+5G' for relative extend).",
)


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_pvdisplay(args: dict[str, Any]) -> ToolResult:
    """pvdisplay [pv]"""
    pv = args.get("pv")
    cmd = ["pvdisplay"] if not pv else ["pvdisplay", pv]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        target = f"physical volume '{pv}'" if pv else "all physical volumes"
        summary = f"Displayed attributes for {target}."
    else:
        target = f"physical volume '{pv}'" if pv else "physical volumes"
        summary = f"Failed to display {target} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_vgdisplay(args: dict[str, Any]) -> ToolResult:
    """vgdisplay [vg]"""
    vg = args.get("vg")
    cmd = ["vgdisplay"] if not vg else ["vgdisplay", vg]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        target = f"volume group '{vg}'" if vg else "all volume groups"
        summary = f"Displayed attributes for {target}."
    else:
        target = f"volume group '{vg}'" if vg else "volume groups"
        summary = f"Failed to display {target} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_lvdisplay(args: dict[str, Any]) -> ToolResult:
    """lvdisplay [lv]"""
    lv = args.get("lv")
    cmd = ["lvdisplay"] if not lv else ["lvdisplay", lv]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        target = f"logical volume '{lv}'" if lv else "all logical volumes"
        summary = f"Displayed attributes for {target}."
    else:
        target = f"logical volume '{lv}'" if lv else "logical volumes"
        summary = f"Failed to display {target} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pvcreate(args: dict[str, Any]) -> ToolResult:
    """pvcreate <device>"""
    pv: str = args["pv"]
    result = run_subprocess(["pvcreate", pv])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Device '{pv}' initialised as an LVM physical volume."
    else:
        summary = f"Failed to initialise '{pv}' as a physical volume (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_vgcreate(args: dict[str, Any]) -> ToolResult:
    """vgcreate <vg_name> <pv>"""
    vg: str = args["vg"]
    pv: str = args["pv"]
    result = run_subprocess(["vgcreate", vg, pv])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Volume group '{vg}' created with physical volume '{pv}'."
    else:
        summary = f"Failed to create volume group '{vg}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_lvcreate(args: dict[str, Any]) -> ToolResult:
    """lvcreate -L <size> -n <lv_name> <vg>"""
    lv_name: str = args["lv_name"]
    vg: str = args["vg"]
    size: str = args["size"]
    result = run_subprocess(["lvcreate", "-L", size, "-n", lv_name, vg])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Logical volume '{lv_name}' ({size}) created in volume group '{vg}'."
    else:
        summary = f"Failed to create logical volume '{lv_name}' in '{vg}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_lvextend(args: dict[str, Any]) -> ToolResult:
    """lvextend -L <size> <lv>"""
    lv: str = args["lv"]
    size: str = args["size"]
    result = run_subprocess(["lvextend", "-L", size, lv])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Logical volume '{lv}' extended to {size}."
    else:
        summary = f"Failed to extend logical volume '{lv}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_vgextend(args: dict[str, Any]) -> ToolResult:
    """vgextend <vg> <pv>"""
    vg: str = args["vg"]
    pv: str = args["pv"]
    result = run_subprocess(["vgextend", vg, pv])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Physical volume '{pv}' added to volume group '{vg}'."
    else:
        summary = f"Failed to add '{pv}' to volume group '{vg}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pvremove(args: dict[str, Any]) -> ToolResult:
    """pvremove <pv>  — DESTRUCTIVE: destroys data on the PV."""
    pv: str = args["pv"]
    result = run_subprocess(["pvremove", pv])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Physical volume '{pv}' removed; LVM metadata wiped from the device."
    else:
        summary = f"Failed to remove physical volume '{pv}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_vgremove(args: dict[str, Any]) -> ToolResult:
    """vgremove <vg>  — DESTRUCTIVE: destroys all data in the VG."""
    vg: str = args["vg"]
    result = run_subprocess(["vgremove", vg])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Volume group '{vg}' removed."
    else:
        summary = f"Failed to remove volume group '{vg}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_lvremove(args: dict[str, Any]) -> ToolResult:
    """lvremove -f <lv>  — DESTRUCTIVE: destroys data in the LV."""
    lv: str = args["lv"]
    result = run_subprocess(["lvremove", "-f", lv])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Logical volume '{lv}' removed."
    else:
        summary = f"Failed to remove logical volume '{lv}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_lvreduce(args: dict[str, Any]) -> ToolResult:
    """lvreduce -L <size> <lv>  — DESTRUCTIVE: shrinking may destroy data."""
    lv: str = args["lv"]
    size: str = args["size"]
    result = run_subprocess(["lvreduce", "-L", size, lv])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Logical volume '{lv}' reduced to {size}."
    else:
        summary = f"Failed to reduce logical volume '{lv}' (exit {result.exit_code})."
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
    "pvdisplay": _op_pvdisplay,
    "vgdisplay": _op_vgdisplay,
    "lvdisplay": _op_lvdisplay,
    "pvcreate":  _op_pvcreate,
    "vgcreate":  _op_vgcreate,
    "lvcreate":  _op_lvcreate,
    "lvextend":  _op_lvextend,
    "vgextend":  _op_vgextend,
    "pvremove":  _op_pvremove,
    "vgremove":  _op_vgremove,
    "lvremove":  _op_lvremove,
    "lvreduce":  _op_lvreduce,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute an lvm operation and return a structured ToolResult.

    The caller (router) is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record.

    This function never raises (I9): unknown ops and subprocess failures all
    degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for lvm tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

LVM_SPEC = ToolSpec(
    name="lvm",
    description="Manage LVM physical volumes, volume groups, and logical volumes.",
    ops={
        "pvdisplay": OpSpec(
            op_name="pvdisplay",
            permission_class=OpClass.READ,
            args=[_PV_ARG_OPT],
            description="Display attributes of physical volumes (all, or a specific PV).",
        ),
        "vgdisplay": OpSpec(
            op_name="vgdisplay",
            permission_class=OpClass.READ,
            args=[_VG_ARG_OPT],
            description="Display attributes of volume groups (all, or a specific VG).",
        ),
        "lvdisplay": OpSpec(
            op_name="lvdisplay",
            permission_class=OpClass.READ,
            args=[_LV_ARG_OPT],
            description="Display attributes of logical volumes (all, or a specific LV).",
        ),
        "pvcreate": OpSpec(
            op_name="pvcreate",
            permission_class=OpClass.WRITE,
            args=[_PV_ARG],
            description="Initialise a block device as an LVM physical volume.",
        ),
        "vgcreate": OpSpec(
            op_name="vgcreate",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="vg",
                    type=str,
                    required=True,
                    description="Name for the new volume group.",
                ),
                _PV_ARG,
            ],
            description="Create a new volume group from a physical volume.",
        ),
        "lvcreate": OpSpec(
            op_name="lvcreate",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="lv_name",
                    type=str,
                    required=True,
                    description="Name for the new logical volume.",
                ),
                ArgSpec(
                    name="vg",
                    type=str,
                    required=True,
                    description="Volume group to create the logical volume in.",
                ),
                _SIZE_ARG,
            ],
            description="Create a new logical volume of a given size in a volume group.",
        ),
        "lvextend": OpSpec(
            op_name="lvextend",
            permission_class=OpClass.WRITE,
            args=[
                _LV_ARG,
                _SIZE_ARG,
            ],
            description="Extend an existing logical volume to a new (larger) size.",
        ),
        "vgextend": OpSpec(
            op_name="vgextend",
            permission_class=OpClass.WRITE,
            args=[
                _VG_ARG,
                _PV_ARG,
            ],
            description="Add a physical volume to an existing volume group.",
        ),
        "pvremove": OpSpec(
            op_name="pvremove",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_PV_ARG],
            description="Remove a physical volume, wiping its LVM metadata. Data-loss operation.",
        ),
        "vgremove": OpSpec(
            op_name="vgremove",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_VG_ARG],
            description="Remove a volume group and all its logical volumes. Data-loss operation.",
        ),
        "lvremove": OpSpec(
            op_name="lvremove",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_LV_ARG],
            description="Remove a logical volume, destroying its data. Data-loss operation.",
        ),
        "lvreduce": OpSpec(
            op_name="lvreduce",
            permission_class=OpClass.DESTRUCTIVE,
            args=[
                _LV_ARG,
                _SIZE_ARG,
            ],
            description="Shrink a logical volume to a smaller size. May destroy data if filesystem not pre-shrunk.",
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(LVM_SPEC)
