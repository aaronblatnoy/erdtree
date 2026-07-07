"""finetune/scenarios/lvm.py — Scenario corpus for the 'lvm' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  pvdisplay  READ        — display physical volume attributes
  vgdisplay  READ        — display volume group attributes
  lvdisplay  READ        — display logical volume attributes
  pvcreate   WRITE       — initialise a device as a physical volume
  vgcreate   WRITE       — create a volume group
  lvcreate   WRITE       — create a logical volume
  lvextend   WRITE       — extend a logical volume
  vgextend   WRITE       — add a PV to an existing volume group
  pvremove   DESTRUCTIVE — remove a physical volume (data-loss)
  vgremove   DESTRUCTIVE — remove a volume group (data-loss)
  lvremove   DESTRUCTIVE — remove a logical volume (data-loss)
  lvreduce   DESTRUCTIVE — shrink a logical volume (may destroy data)

Coverage targets
----------------
  >= 48 entries total across all 12 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach the
  escalated confirmation gate.

INV-schema-sync:  permission_class for each entry is derived from the LIVE
  registry via finetune.coreimports, never hardcoded.
INV-read-only-core: imports only from finetune.coreimports, never directly
  from core/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from finetune.coreimports import OpClass, registry

# ---------------------------------------------------------------------------
# Scenario dataclass — field names match services.py exactly for JOIN compat
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scenario:
    id: str
    tool: str
    operation: str
    permission_class: OpClass
    complexity: Literal["single", "multi", "diagnostic"]
    user_input: str
    notes: str


# ---------------------------------------------------------------------------
# Live permission-class lookup — INV-schema-sync
# ---------------------------------------------------------------------------

def _pc(op: str) -> OpClass:
    """Return the live permission class for an lvm operation."""
    return registry.get("lvm").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # pvdisplay  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="lvm-pvdisplay-0001",
        tool="lvm",
        operation="pvdisplay",
        permission_class=_pc("pvdisplay"),
        complexity="single",
        user_input="show me all physical volumes on this system",
        notes="Basic READ: list all PVs with their sizes and VG membership.",
    ),
    Scenario(
        id="lvm-pvdisplay-0002",
        tool="lvm",
        operation="pvdisplay",
        permission_class=_pc("pvdisplay"),
        complexity="single",
        user_input="display info for the physical volume /dev/sdb",
        notes="Single PV inspection by device path.",
    ),
    Scenario(
        id="lvm-pvdisplay-0003",
        tool="lvm",
        operation="pvdisplay",
        permission_class=_pc("pvdisplay"),
        complexity="diagnostic",
        user_input="I think /dev/sdc was set up as an LVM PV — show its attributes",
        notes="Diagnostic: verify whether a device is already a PV before creating a VG.",
    ),
    Scenario(
        id="lvm-pvdisplay-0004",
        tool="lvm",
        operation="pvdisplay",
        permission_class=_pc("pvdisplay"),
        complexity="multi",
        user_input="check all physical volumes and tell me how much free PE each has",
        notes="Multi-step: display all PVs and interpret free PE / allocated PE fields.",
    ),
    Scenario(
        id="lvm-pvdisplay-0005",
        tool="lvm",
        operation="pvdisplay",
        permission_class=_pc("pvdisplay"),
        complexity="single",
        user_input="what is the UUID of the physical volume /dev/sdb1?",
        notes="READ: retrieve the PV UUID for documentation or disaster recovery.",
    ),

    # =========================================================================
    # vgdisplay  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="lvm-vgdisplay-0001",
        tool="lvm",
        operation="vgdisplay",
        permission_class=_pc("vgdisplay"),
        complexity="single",
        user_input="show all volume groups on this server",
        notes="READ: list all VGs with size, PE counts, and UUID.",
    ),
    Scenario(
        id="lvm-vgdisplay-0002",
        tool="lvm",
        operation="vgdisplay",
        permission_class=_pc("vgdisplay"),
        complexity="single",
        user_input="display the details for volume group vg_data",
        notes="Single VG inspection by name.",
    ),
    Scenario(
        id="lvm-vgdisplay-0003",
        tool="lvm",
        operation="vgdisplay",
        permission_class=_pc("vgdisplay"),
        complexity="diagnostic",
        user_input="the lvcreate command said VG is full — check vg_data to see the free space",
        notes="Diagnostic: inspect VG free PE to diagnose an allocation failure.",
    ),
    Scenario(
        id="lvm-vgdisplay-0004",
        tool="lvm",
        operation="vgdisplay",
        permission_class=_pc("vgdisplay"),
        complexity="multi",
        user_input="show vg_archive attributes and then tell me if I can create a 20G LV in it",
        notes="Multi-step: vgdisplay then capacity arithmetic.",
    ),
    Scenario(
        id="lvm-vgdisplay-0005",
        tool="lvm",
        operation="vgdisplay",
        permission_class=_pc("vgdisplay"),
        complexity="single",
        user_input="how many logical volumes exist in vg_data?",
        notes="READ: count current LVs in a VG from the Cur LV field.",
    ),

    # =========================================================================
    # lvdisplay  (READ) — 5 entries
    # =========================================================================

    Scenario(
        id="lvm-lvdisplay-0001",
        tool="lvm",
        operation="lvdisplay",
        permission_class=_pc("lvdisplay"),
        complexity="single",
        user_input="list all logical volumes on this host",
        notes="READ: show all LVs with paths, sizes, and UUIDs.",
    ),
    Scenario(
        id="lvm-lvdisplay-0002",
        tool="lvm",
        operation="lvdisplay",
        permission_class=_pc("lvdisplay"),
        complexity="single",
        user_input="display the properties of /dev/vg_data/lv_home",
        notes="Single LV inspection by device path.",
    ),
    Scenario(
        id="lvm-lvdisplay-0003",
        tool="lvm",
        operation="lvdisplay",
        permission_class=_pc("lvdisplay"),
        complexity="diagnostic",
        user_input="the filesystem on lv_home looks full — show the LV size so I can plan an extension",
        notes="Diagnostic: check LV current size before planning lvextend.",
    ),
    Scenario(
        id="lvm-lvdisplay-0004",
        tool="lvm",
        operation="lvdisplay",
        permission_class=_pc("lvdisplay"),
        complexity="multi",
        user_input="show all LVs in vg_data and report which ones are open",
        notes="Multi-step: lvdisplay all then filter by '# open' field.",
    ),
    Scenario(
        id="lvm-lvdisplay-0005",
        tool="lvm",
        operation="lvdisplay",
        permission_class=_pc("lvdisplay"),
        complexity="single",
        user_input="what block device number is assigned to /dev/vg_data/lv_swap?",
        notes="READ: retrieve the block device major:minor from LV attributes.",
    ),

    # =========================================================================
    # pvcreate  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-pvcreate-0001",
        tool="lvm",
        operation="pvcreate",
        permission_class=_pc("pvcreate"),
        complexity="single",
        user_input="initialise /dev/sdb as an LVM physical volume",
        notes="WRITE: basic pvcreate on a bare disk before vgcreate.",
    ),
    Scenario(
        id="lvm-pvcreate-0002",
        tool="lvm",
        operation="pvcreate",
        permission_class=_pc("pvcreate"),
        complexity="multi",
        user_input="set up /dev/sdc as a PV and then add it to vg_archive",
        notes="Multi-step: pvcreate then vgextend.",
    ),
    Scenario(
        id="lvm-pvcreate-0003",
        tool="lvm",
        operation="pvcreate",
        permission_class=_pc("pvcreate"),
        complexity="single",
        user_input="prepare /dev/nvme1n1 for use as an LVM physical volume",
        notes="WRITE: pvcreate on an NVMe device — common in modern data centre builds.",
    ),
    Scenario(
        id="lvm-pvcreate-0004",
        tool="lvm",
        operation="pvcreate",
        permission_class=_pc("pvcreate"),
        complexity="diagnostic",
        user_input="I added a new disk /dev/sdd — make it a physical volume so I can expand storage",
        notes="Diagnostic-triggered WRITE: provisioning a new device after storage expansion.",
    ),

    # =========================================================================
    # vgcreate  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-vgcreate-0001",
        tool="lvm",
        operation="vgcreate",
        permission_class=_pc("vgcreate"),
        complexity="single",
        user_input="create a volume group called vg_data on /dev/sdb",
        notes="WRITE: basic VG creation on a freshly initialised PV.",
    ),
    Scenario(
        id="lvm-vgcreate-0002",
        tool="lvm",
        operation="vgcreate",
        permission_class=_pc("vgcreate"),
        complexity="multi",
        user_input="create vg_archive on /dev/sdc and then create a 40G LV called lv_backups in it",
        notes="Multi-step: vgcreate then lvcreate.",
    ),
    Scenario(
        id="lvm-vgcreate-0003",
        tool="lvm",
        operation="vgcreate",
        permission_class=_pc("vgcreate"),
        complexity="single",
        user_input="set up a new volume group named vg_db on /dev/nvme0n1",
        notes="WRITE: VG for a dedicated database storage layout.",
    ),
    Scenario(
        id="lvm-vgcreate-0004",
        tool="lvm",
        operation="vgcreate",
        permission_class=_pc("vgcreate"),
        complexity="diagnostic",
        user_input="I need a new VG for test workloads — create vg_test on /dev/sdd",
        notes="WRITE: provisioning a VG for an isolated test environment.",
    ),

    # =========================================================================
    # lvcreate  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-lvcreate-0001",
        tool="lvm",
        operation="lvcreate",
        permission_class=_pc("lvcreate"),
        complexity="single",
        user_input="create a 10G logical volume called lv_home in vg_data",
        notes="WRITE: standard LV creation for a home directory filesystem.",
    ),
    Scenario(
        id="lvm-lvcreate-0002",
        tool="lvm",
        operation="lvcreate",
        permission_class=_pc("lvcreate"),
        complexity="single",
        user_input="allocate a 2G swap LV named lv_swap in vg_data",
        notes="WRITE: swap LV creation — common post-install step.",
    ),
    Scenario(
        id="lvm-lvcreate-0003",
        tool="lvm",
        operation="lvcreate",
        permission_class=_pc("lvcreate"),
        complexity="multi",
        user_input="create lv_pgdata (50G) in vg_db and then check the LV attributes",
        notes="Multi-step: lvcreate then lvdisplay.",
    ),
    Scenario(
        id="lvm-lvcreate-0004",
        tool="lvm",
        operation="lvcreate",
        permission_class=_pc("lvcreate"),
        complexity="diagnostic",
        user_input="disk space is running low on /home — create a new 20G LV lv_home2 in vg_data as overflow",
        notes="Diagnostic-triggered WRITE: emergency LV for overflow storage.",
    ),

    # =========================================================================
    # lvextend  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-lvextend-0001",
        tool="lvm",
        operation="lvextend",
        permission_class=_pc("lvextend"),
        complexity="single",
        user_input="extend /dev/vg_data/lv_home to 20G",
        notes="WRITE: grow an LV to accommodate a growing filesystem.",
    ),
    Scenario(
        id="lvm-lvextend-0002",
        tool="lvm",
        operation="lvextend",
        permission_class=_pc("lvextend"),
        complexity="multi",
        user_input="extend lv_pgdata by 10G and then run resize2fs to expand the filesystem",
        notes="Multi-step: lvextend then filesystem resize.",
    ),
    Scenario(
        id="lvm-lvextend-0003",
        tool="lvm",
        operation="lvextend",
        permission_class=_pc("lvextend"),
        complexity="diagnostic",
        user_input="/var/lib/pgsql is at 95% — extend /dev/vg_db/lv_pgdata to 60G immediately",
        notes="Diagnostic-triggered WRITE: emergency LV extension to prevent a disk-full failure.",
    ),
    Scenario(
        id="lvm-lvextend-0004",
        tool="lvm",
        operation="lvextend",
        permission_class=_pc("lvextend"),
        complexity="single",
        user_input="increase the size of vg_archive/lv_backups by 5G",
        notes="WRITE: relative extension using +5G size notation.",
    ),

    # =========================================================================
    # vgextend  (WRITE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-vgextend-0001",
        tool="lvm",
        operation="vgextend",
        permission_class=_pc("vgextend"),
        complexity="single",
        user_input="add /dev/sdc to volume group vg_data",
        notes="WRITE: expand a VG by adding a new PV.",
    ),
    Scenario(
        id="lvm-vgextend-0002",
        tool="lvm",
        operation="vgextend",
        permission_class=_pc("vgextend"),
        complexity="multi",
        user_input="add the newly provisioned /dev/sdd to vg_archive and then confirm how much free space is in the VG",
        notes="Multi-step: vgextend then vgdisplay to confirm the new size.",
    ),
    Scenario(
        id="lvm-vgextend-0003",
        tool="lvm",
        operation="vgextend",
        permission_class=_pc("vgextend"),
        complexity="diagnostic",
        user_input="vg_db is out of free extents — add /dev/nvme1n1 to it so I can extend lv_pgdata",
        notes="Diagnostic-triggered WRITE: add capacity to a full VG before extending an LV.",
    ),
    Scenario(
        id="lvm-vgextend-0004",
        tool="lvm",
        operation="vgextend",
        permission_class=_pc("vgextend"),
        complexity="single",
        user_input="expand vg_test by adding /dev/sde as a physical volume",
        notes="WRITE: grow the test VG for a load test that needs more space.",
    ),

    # =========================================================================
    # pvremove  (DESTRUCTIVE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-pvremove-0001",
        tool="lvm",
        operation="pvremove",
        permission_class=_pc("pvremove"),
        complexity="single",
        user_input="remove LVM labels from /dev/sdb — I am decommissioning this disk",
        notes="DESTRUCTIVE: wipe PV metadata from a disk being retired.",
    ),
    Scenario(
        id="lvm-pvremove-0002",
        tool="lvm",
        operation="pvremove",
        permission_class=_pc("pvremove"),
        complexity="multi",
        user_input="take /dev/sdc out of vg_archive and then remove its LVM label",
        notes="Multi-step: vgreduce to remove from VG then pvremove to clear labels.",
    ),
    Scenario(
        id="lvm-pvremove-0003",
        tool="lvm",
        operation="pvremove",
        permission_class=_pc("pvremove"),
        complexity="diagnostic",
        user_input="the disk /dev/sdd shows as a PV but belongs to a dead VG — remove it so I can reuse it",
        notes="DESTRUCTIVE: cleanup of a PV belonging to a no-longer-existent VG.",
    ),
    Scenario(
        id="lvm-pvremove-0004",
        tool="lvm",
        operation="pvremove",
        permission_class=_pc("pvremove"),
        complexity="single",
        user_input="wipe the LVM header from /dev/sdb1 before returning the partition to raw use",
        notes="DESTRUCTIVE: remove PV designation from a partition being repurposed.",
    ),

    # =========================================================================
    # vgremove  (DESTRUCTIVE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-vgremove-0001",
        tool="lvm",
        operation="vgremove",
        permission_class=_pc("vgremove"),
        complexity="single",
        user_input="remove the volume group vg_test — this environment is being torn down",
        notes="DESTRUCTIVE: decommission a temporary test VG and all its LVs.",
    ),
    Scenario(
        id="lvm-vgremove-0002",
        tool="lvm",
        operation="vgremove",
        permission_class=_pc("vgremove"),
        complexity="multi",
        user_input="remove vg_archive and then run pvremove on its underlying devices",
        notes="Multi-step: vgremove then pvremove to fully clean up the storage stack.",
    ),
    Scenario(
        id="lvm-vgremove-0003",
        tool="lvm",
        operation="vgremove",
        permission_class=_pc("vgremove"),
        complexity="diagnostic",
        user_input="the old reporting VG vg_reports is empty and unused — delete it",
        notes="DESTRUCTIVE: remove an empty VG that was left over from a retired workload.",
    ),
    Scenario(
        id="lvm-vgremove-0004",
        tool="lvm",
        operation="vgremove",
        permission_class=_pc("vgremove"),
        complexity="single",
        user_input="I need to reprovision this server — delete vg_data",
        notes="DESTRUCTIVE: full decommission of the primary data VG before reimaging.",
    ),

    # =========================================================================
    # lvremove  (DESTRUCTIVE) — 5 entries
    # =========================================================================

    Scenario(
        id="lvm-lvremove-0001",
        tool="lvm",
        operation="lvremove",
        permission_class=_pc("lvremove"),
        complexity="single",
        user_input="delete the logical volume /dev/vg_data/lv_old_backup",
        notes="DESTRUCTIVE: remove an LV that is no longer needed.",
    ),
    Scenario(
        id="lvm-lvremove-0002",
        tool="lvm",
        operation="lvremove",
        permission_class=_pc("lvremove"),
        complexity="multi",
        user_input="unmount /mnt/backup and then remove lv_backup from vg_archive",
        notes="Multi-step: umount then lvremove — standard decommission sequence.",
    ),
    Scenario(
        id="lvm-lvremove-0003",
        tool="lvm",
        operation="lvremove",
        permission_class=_pc("lvremove"),
        complexity="diagnostic",
        user_input="vg_data is full and we need space — remove the unused test LV /dev/vg_data/lv_test",
        notes="DESTRUCTIVE: free up VG space by removing an idle LV.",
    ),
    Scenario(
        id="lvm-lvremove-0004",
        tool="lvm",
        operation="lvremove",
        permission_class=_pc("lvremove"),
        complexity="single",
        user_input="remove the logical volume vg_db/lv_staging — staging is migrating to another host",
        notes="DESTRUCTIVE: remove staging LV as part of a migration cleanup.",
    ),
    Scenario(
        id="lvm-lvremove-0005",
        tool="lvm",
        operation="lvremove",
        permission_class=_pc("lvremove"),
        complexity="single",
        user_input="delete lv_swap from vg_data so I can reclaim the space for lv_home",
        notes="DESTRUCTIVE: remove swap LV to reclaim extents for another LV.",
    ),

    # =========================================================================
    # lvreduce  (DESTRUCTIVE) — 4 entries
    # =========================================================================

    Scenario(
        id="lvm-lvreduce-0001",
        tool="lvm",
        operation="lvreduce",
        permission_class=_pc("lvreduce"),
        complexity="single",
        user_input="shrink /dev/vg_data/lv_home down to 8G",
        notes="DESTRUCTIVE: reduce LV size — filesystem must already be shrunk before calling this.",
    ),
    Scenario(
        id="lvm-lvreduce-0002",
        tool="lvm",
        operation="lvreduce",
        permission_class=_pc("lvreduce"),
        complexity="multi",
        user_input="resize2fs lv_home to 6G first, then reduce the LV to 6G",
        notes="Multi-step: filesystem shrink then lvreduce — correct safe order.",
    ),
    Scenario(
        id="lvm-lvreduce-0003",
        tool="lvm",
        operation="lvreduce",
        permission_class=_pc("lvreduce"),
        complexity="diagnostic",
        user_input="I over-allocated lv_swap at 8G — shrink it to 2G to free up VG extents",
        notes="DESTRUCTIVE: right-size an over-provisioned swap LV.",
    ),
    Scenario(
        id="lvm-lvreduce-0004",
        tool="lvm",
        operation="lvreduce",
        permission_class=_pc("lvreduce"),
        complexity="single",
        user_input="reduce vg_db/lv_pgdata from 60G to 40G after data was migrated off",
        notes="DESTRUCTIVE: shrink an LV after data migration freed up space.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("lvm").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "lvm", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("lvm").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
