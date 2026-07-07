"""finetune/simulate/lvm.py — Rocky Linux 9 output simulator for the 'lvm' tool.

Public API
----------
simulate_lvm(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 12 real operations declared in core/tools/lvm.py
    args : dict of op arguments (may be sparse; defaults applied per-op)
    ctx  : system context string OR profile dict — both forms supported.

Realism model
-------------
  Exit codes mirror real lvm2 behaviour:
    0 — success
    1 — operation failed (device busy, not found, insufficient space)
    5 — device/object not found
  stdout/stderr reflect actual Rocky 9 lvm2 / lvm2-libs output format.
  Failure triggers are deterministic: object names containing "missing",
  "bogus", "notfound", "noexist" or "fail" return failure cases so traces
  teach error handling.  A hash-based ~15% scatter adds variety.

I2 compliance
-------------
  All summary strings are I2-clean (no AI/LLM/model/agent/agentic language).

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps).
The ToolResult shape is mirrored as a plain dict — no class dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


def _obj_not_found(name: str) -> bool:
    """Deterministically decide if an LVM object name should trigger a not-found error."""
    lower = name.lower()
    for tok in ("missing", "bogus", "notfound", "noexist", "fail", "broken", "bad"):
        if tok in lower:
            return True
    # Hash-based deterministic scatter (~15%)
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 20 == 0


def _device_not_found(dev: str) -> bool:
    """Return True if a device path looks like it should not exist."""
    return _obj_not_found(dev)


def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for realistic output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_pvdisplay(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pv = args.get("pv")

    if pv and _device_not_found(pv):
        stderr = f"  Failed to find physical volume \"{pv}\".\n"
        return _make_result(
            exit_code=5,
            stdout="",
            stderr=stderr,
            summary=f"Physical volume '{pv}' was not found.",
        )

    if pv:
        # Single PV display
        stdout = (
            f"  --- Physical volume ---\n"
            f"  PV Name               {pv}\n"
            f"  VG Name               vg_data\n"
            f"  PV Size               <20.00 GiB / not usable 4.00 MiB\n"
            f"  Allocatable           yes (but full)\n"
            f"  PE Size               4.00 MiB\n"
            f"  Total PE              5119\n"
            f"  Free PE               0\n"
            f"  Allocated PE          5119\n"
            f"  PV UUID               abc123-4567-89de-f012-345678901234\n"
        )
        summary = f"Displayed attributes for physical volume '{pv}'."
    else:
        # All PVs
        stdout = (
            f"  --- Physical volume ---\n"
            f"  PV Name               /dev/sdb\n"
            f"  VG Name               vg_data\n"
            f"  PV Size               <20.00 GiB / not usable 4.00 MiB\n"
            f"  Allocatable           yes (but full)\n"
            f"  PE Size               4.00 MiB\n"
            f"  Total PE              5119\n"
            f"  Free PE               0\n"
            f"  Allocated PE          5119\n"
            f"  PV UUID               abc123-4567-89de-f012-345678901234\n"
            f"\n"
            f"  --- Physical volume ---\n"
            f"  PV Name               /dev/sdc\n"
            f"  VG Name               vg_archive\n"
            f"  PV Size               <50.00 GiB / not usable 4.00 MiB\n"
            f"  Allocatable           yes\n"
            f"  PE Size               4.00 MiB\n"
            f"  Total PE              12799\n"
            f"  Free PE               2560\n"
            f"  Allocated PE          10239\n"
            f"  PV UUID               def456-7890-ab12-cd34-567890abcdef\n"
        )
        summary = "Displayed attributes for all physical volumes."

    return _make_result(exit_code=0, stdout=stdout, stderr="", summary=summary)


def _sim_vgdisplay(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    vg = args.get("vg")

    if vg and _obj_not_found(vg):
        stderr = f"  Volume group \"{vg}\" not found\n"
        return _make_result(
            exit_code=5,
            stdout="",
            stderr=stderr,
            summary=f"Volume group '{vg}' was not found.",
        )

    if vg:
        stdout = (
            f"  --- Volume group ---\n"
            f"  VG Name               {vg}\n"
            f"  System ID\n"
            f"  Format                lvm2\n"
            f"  Metadata Areas        1\n"
            f"  Metadata Sequence No  4\n"
            f"  VG Access             read/write\n"
            f"  VG Status             resizable\n"
            f"  MAX LV                0\n"
            f"  Cur LV                2\n"
            f"  Open LV               2\n"
            f"  Max PV                0\n"
            f"  Cur PV                1\n"
            f"  Act PV                1\n"
            f"  VG Size               <20.00 GiB\n"
            f"  PE Size               4.00 MiB\n"
            f"  Total PE              5119\n"
            f"  Alloc PE / Size       5119 / <20.00 GiB\n"
            f"  Free  PE / Size       0 / 0\n"
            f"  VG UUID               abc123-4567-89de-f012-abcdef012345\n"
        )
        summary = f"Displayed attributes for volume group '{vg}'."
    else:
        stdout = (
            f"  --- Volume group ---\n"
            f"  VG Name               vg_data\n"
            f"  Format                lvm2\n"
            f"  VG Size               <20.00 GiB\n"
            f"  Cur LV                2\n"
            f"  VG UUID               abc123-4567-89de-f012-abcdef012345\n"
            f"\n"
            f"  --- Volume group ---\n"
            f"  VG Name               vg_archive\n"
            f"  Format                lvm2\n"
            f"  VG Size               <50.00 GiB\n"
            f"  Cur LV                1\n"
            f"  VG UUID               def456-7890-ab12-cd34-567890fedcba\n"
        )
        summary = "Displayed attributes for all volume groups."

    return _make_result(exit_code=0, stdout=stdout, stderr="", summary=summary)


def _sim_lvdisplay(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    lv = args.get("lv")

    if lv and _obj_not_found(lv):
        stderr = f"  Failed to find logical volume \"{lv}\".\n"
        return _make_result(
            exit_code=5,
            stdout="",
            stderr=stderr,
            summary=f"Logical volume '{lv}' was not found.",
        )

    if lv:
        lv_name = lv.split("/")[-1] if "/" in lv else lv
        vg_name = lv.split("/")[-2] if lv.count("/") >= 2 else "vg_data"
        stdout = (
            f"  --- Logical volume ---\n"
            f"  LV Path                /dev/{vg_name}/{lv_name}\n"
            f"  LV Name                {lv_name}\n"
            f"  VG Name                {vg_name}\n"
            f"  LV UUID                abc123-4567-89de-f012-fedcba098765\n"
            f"  LV Write Access        read/write\n"
            f"  LV Creation host, time rocky-host, 2026-07-01 12:00:00 +0000\n"
            f"  LV Status              available\n"
            f"  # open                 1\n"
            f"  LV Size                10.00 GiB\n"
            f"  Current LE             2560\n"
            f"  Segments               1\n"
            f"  Allocation             inherit\n"
            f"  Read ahead sectors     auto\n"
            f"  - currently set to     256\n"
            f"  Block device           253:0\n"
        )
        summary = f"Displayed attributes for logical volume '{lv}'."
    else:
        stdout = (
            f"  --- Logical volume ---\n"
            f"  LV Path                /dev/vg_data/lv_home\n"
            f"  LV Name                lv_home\n"
            f"  VG Name                vg_data\n"
            f"  LV Size                10.00 GiB\n"
            f"  LV UUID                abc123-4567-89de-f012-fedcba098765\n"
            f"\n"
            f"  --- Logical volume ---\n"
            f"  LV Path                /dev/vg_data/lv_swap\n"
            f"  LV Name                lv_swap\n"
            f"  VG Name                vg_data\n"
            f"  LV Size                2.00 GiB\n"
            f"  LV UUID                fedcba-9876-5432-10fe-dcba98765432\n"
        )
        summary = "Displayed attributes for all logical volumes."

    return _make_result(exit_code=0, stdout=stdout, stderr="", summary=summary)


def _sim_pvcreate(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pv = args.get("pv", "/dev/sdb")

    if _device_not_found(pv):
        stderr = (
            f"  Device {pv} not found.\n"
            f"  Cannot use {pv}: No such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to initialise '{pv}' as a physical volume — device not found (exit 1).",
        )

    # Hash-based failure: device already in use
    h = int(hashlib.md5((pv + "pvcreate").encode()).hexdigest(), 16)
    if h % 15 == 0:
        stderr = (
            f"  Device {pv} is already in use.\n"
            f"  Can't initialize physical volume \"{pv}\" of volume group "
            f"\"vg_data\" without -ff\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to initialise '{pv}' as a physical volume — device already in use (exit 1).",
        )

    stdout = f"  Physical volume \"{pv}\" successfully created.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Device '{pv}' initialised as an LVM physical volume.",
    )


def _sim_vgcreate(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    vg = args.get("vg", "vg_data")
    pv = args.get("pv", "/dev/sdb")

    if _device_not_found(pv):
        stderr = f"  Device {pv} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create volume group '{vg}' — physical volume '{pv}' not found (exit 1).",
        )

    if _obj_not_found(vg):
        stderr = f"  Volume group name \"{vg}\" is invalid.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create volume group '{vg}' — invalid name (exit 1).",
        )

    stdout = (
        f"  Volume group \"{vg}\" successfully created\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Volume group '{vg}' created with physical volume '{pv}'.",
    )


def _sim_lvcreate(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    lv_name = args.get("lv_name", "lv_data")
    vg = args.get("vg", "vg_data")
    size = args.get("size", "10G")

    if _obj_not_found(vg):
        stderr = f"  Volume group \"{vg}\" not found\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create logical volume '{lv_name}' — volume group '{vg}' not found (exit 1).",
        )

    # Hash-based: insufficient free space
    h = int(hashlib.md5((lv_name + vg + size).encode()).hexdigest(), 16)
    if h % 14 == 0:
        stderr = (
            f"  Insufficient free space: 0 extents available, "
            f"but {size} required.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create logical volume '{lv_name}' in '{vg}' — insufficient free space (exit 1).",
        )

    stdout = (
        f"  Logical volume \"{lv_name}\" created.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Logical volume '{lv_name}' ({size}) created in volume group '{vg}'.",
    )


def _sim_lvextend(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    lv = args.get("lv", "/dev/vg_data/lv_home")
    size = args.get("size", "+5G")

    if _obj_not_found(lv):
        stderr = f"  Failed to find logical volume \"{lv}\".\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to extend logical volume '{lv}' — not found (exit 1).",
        )

    # Hash-based: insufficient space
    h = int(hashlib.md5((lv + size + "extend").encode()).hexdigest(), 16)
    if h % 14 == 0:
        stderr = (
            f"  Insufficient free space: 0 extents available.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to extend logical volume '{lv}' — insufficient free space in the volume group (exit 1).",
        )

    lv_name = lv.split("/")[-1] if "/" in lv else lv
    stdout = (
        f"  Size of logical volume vg_data/{lv_name} changed from 10.00 GiB (2560 extents) "
        f"to 15.00 GiB (3840 extents).\n"
        f"  Logical volume vg_data/{lv_name} successfully resized.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Logical volume '{lv}' extended to {size}.",
    )


def _sim_vgextend(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    vg = args.get("vg", "vg_data")
    pv = args.get("pv", "/dev/sdc")

    if _obj_not_found(vg):
        stderr = f"  Volume group \"{vg}\" not found\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to add '{pv}' to volume group '{vg}' — volume group not found (exit 1).",
        )

    if _device_not_found(pv):
        stderr = f"  Device {pv} not found.\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to add '{pv}' to volume group '{vg}' — device not found (exit 1).",
        )

    stdout = f"  Volume group \"{vg}\" successfully extended\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Physical volume '{pv}' added to volume group '{vg}'.",
    )


def _sim_pvremove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    pv = args.get("pv", "/dev/sdb")

    if _device_not_found(pv):
        stderr = (
            f"  Failed to find physical volume \"{pv}\".\n"
            f"  Cannot remove physical volume \"{pv}\" of volume group "
            f"\"vg_data\" without -ff (use -f to override)\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove physical volume '{pv}' — not found (exit 1).",
        )

    # Hash-based: PV still in use by a VG
    h = int(hashlib.md5((pv + "pvremove").encode()).hexdigest(), 16)
    if h % 12 == 0:
        stderr = (
            f"  PV {pv} is used by VG vg_data so please use vgreduce first.\n"
            f"  (If you are certain you need pvremove, then confirm by using --force twice.)\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove physical volume '{pv}' — it is still in use by a volume group (exit 1).",
        )

    stdout = (
        f"  Labels on physical volume \"{pv}\" successfully wiped.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Physical volume '{pv}' removed; LVM metadata wiped from the device.",
    )


def _sim_vgremove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    vg = args.get("vg", "vg_data")

    if _obj_not_found(vg):
        stderr = f"  Volume group \"{vg}\" not found\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove volume group '{vg}' — not found (exit 1).",
        )

    # Hash-based: LVs still active
    h = int(hashlib.md5((vg + "vgremove").encode()).hexdigest(), 16)
    if h % 12 == 0:
        stderr = (
            f"  Logical volume vg_data/lv_home still active.\n"
            f"  Can't remove volume group \"{vg}\" with active LV vg_data/lv_home\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove volume group '{vg}' — it has active logical volumes (exit 1).",
        )

    stdout = (
        f"  Logical volume \"lv_home\" successfully removed.\n"
        f"  Logical volume \"lv_swap\" successfully removed.\n"
        f"  Volume group \"{vg}\" successfully removed\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Volume group '{vg}' removed.",
    )


def _sim_lvremove(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    lv = args.get("lv", "/dev/vg_data/lv_home")

    if _obj_not_found(lv):
        stderr = f"  Failed to find logical volume \"{lv}\".\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove logical volume '{lv}' — not found (exit 1).",
        )

    # Hash-based: LV still open/mounted
    h = int(hashlib.md5((lv + "lvremove").encode()).hexdigest(), 16)
    if h % 12 == 0:
        stderr = (
            f"  Logical volume {lv} contains a filesystem in use.\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to remove logical volume '{lv}' — the volume contains a mounted filesystem (exit 1).",
        )

    lv_name = lv.split("/")[-1] if "/" in lv else lv
    stdout = f"  Logical volume \"{lv_name}\" successfully removed.\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Logical volume '{lv}' removed.",
    )


def _sim_lvreduce(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    lv = args.get("lv", "/dev/vg_data/lv_home")
    size = args.get("size", "5G")

    if _obj_not_found(lv):
        stderr = f"  Failed to find logical volume \"{lv}\".\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to reduce logical volume '{lv}' — not found (exit 1).",
        )

    # Hash-based: new size larger than current (can't reduce to a bigger size)
    h = int(hashlib.md5((lv + size + "reduce").encode()).hexdigest(), 16)
    if h % 14 == 0:
        stderr = (
            f"  New size (15360 extents) matches existing size (15360 extents).\n"
            f"  New size given (15.00 GiB) not less than existing size (10.00 GiB).\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to reduce logical volume '{lv}' — new size is not smaller than the current size (exit 1).",
        )

    lv_name = lv.split("/")[-1] if "/" in lv else lv
    stdout = (
        f"  WARNING: Reducing active logical volume to {size}.\n"
        f"  THIS MAY DESTROY YOUR DATA (filesystem etc.)\n"
        f"  Size of logical volume vg_data/{lv_name} changed from 10.00 GiB (2560 extents) "
        f"to {size} (1280 extents).\n"
        f"  Logical volume vg_data/{lv_name} successfully resized.\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Logical volume '{lv}' reduced to {size}.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "pvdisplay": _sim_pvdisplay,
    "vgdisplay": _sim_vgdisplay,
    "lvdisplay": _sim_lvdisplay,
    "pvcreate":  _sim_pvcreate,
    "vgcreate":  _sim_vgcreate,
    "lvcreate":  _sim_lvcreate,
    "lvextend":  _sim_lvextend,
    "vgextend":  _sim_vgextend,
    "pvremove":  _sim_pvremove,
    "vgremove":  _sim_vgremove,
    "lvremove":  _sim_lvremove,
    "lvreduce":  _sim_lvreduce,
}


def simulate_lvm(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate an 'lvm' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 12 real ops declared in the
           lvm ToolSpec (pvdisplay, vgdisplay, lvdisplay, pvcreate, vgcreate,
           lvcreate, lvextend, vgextend, pvremove, vgremove, lvremove, lvreduce).
    args : argument dict (may be sparse; defaults applied per-op).
    ctx  : system context — either a snapshot_text str or a profile dict.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present.  summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_lvm: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
