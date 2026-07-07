"""finetune/scenarios/stratis.py — Scenario corpus for the 'stratis' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  pool-list        READ        — list all Stratis pools
  pool-create      WRITE       — create a new Stratis pool
  pool-destroy     DESTRUCTIVE — destroy a pool (data loss)
  filesystem-list  READ        — list filesystems in a pool
  filesystem-create WRITE      — create a new filesystem
  filesystem-snapshot WRITE    — snapshot a filesystem
  filesystem-destroy DESTRUCTIVE — destroy a filesystem (data loss)

Coverage targets
----------------
  >= 40 entries total across all 7 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios honestly labeled so downstream traces teach the
  confirm-before-destroy gate.

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
# Scenario dataclass
# Compatible field names are EXACT so the P13 JOIN can unify without renames.
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
    """Return the live permission class for a stratis operation."""
    return registry.get("stratis").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # pool-list  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="stratis-pool-list-0001",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="single",
        user_input="show me all stratis pools",
        notes="Simple READ: list all Stratis pools on the system.",
    ),
    Scenario(
        id="stratis-pool-list-0002",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="single",
        user_input="what stratis pools exist on this host?",
        notes="Pool inventory check.",
    ),
    Scenario(
        id="stratis-pool-list-0003",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="diagnostic",
        user_input="I think stratis is installed — list the pools so I can see what storage is configured",
        notes="Diagnostic starting point: discover stratis pool topology.",
    ),
    Scenario(
        id="stratis-pool-list-0004",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="multi",
        user_input="list stratis pools and tell me how much capacity each one has",
        notes="Multi-step: list pools then interpret size columns.",
    ),
    Scenario(
        id="stratis-pool-list-0005",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="single",
        user_input="check available stratis pools",
        notes="Quick inventory scan before creating a new filesystem.",
    ),
    Scenario(
        id="stratis-pool-list-0006",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="diagnostic",
        user_input="the application server says its stratis volume is missing — first show me all pools",
        notes="Incident triage: pool list is the first diagnostic step.",
    ),
    Scenario(
        id="stratis-pool-list-0007",
        tool="stratis",
        operation="pool-list",
        permission_class=_pc("pool-list"),
        complexity="multi",
        user_input="list stratis pools and then list the filesystems in each one",
        notes="Multi-step: pool list followed by filesystem list per pool.",
    ),

    # =========================================================================
    # pool-create  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="stratis-pool-create-0001",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="single",
        user_input="create a stratis pool called datapool on /dev/sdb",
        notes="WRITE: basic pool creation on a single device.",
    ),
    Scenario(
        id="stratis-pool-create-0002",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="single",
        user_input="set up a new stratis pool named backuppool using /dev/sdc",
        notes="WRITE: pool creation for backup storage.",
    ),
    Scenario(
        id="stratis-pool-create-0003",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="multi",
        user_input="create a stratis pool named prodpool on /dev/nvme1n1 and then verify it appears in the pool list",
        notes="Multi-step: create pool then verify with pool-list.",
    ),
    Scenario(
        id="stratis-pool-create-0004",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="single",
        user_input="make a stratis pool called homespool on /dev/sdd for user home directories",
        notes="WRITE: pool creation for home directory storage.",
    ),
    Scenario(
        id="stratis-pool-create-0005",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="diagnostic",
        user_input="the disk /dev/sdb was just added — create a stratis pool on it",
        notes="Diagnostic-triggered WRITE: new disk provisioning via Stratis.",
    ),
    Scenario(
        id="stratis-pool-create-0006",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="single",
        user_input="create a stratis storage pool named testpool on /dev/vdb",
        notes="WRITE: test pool creation in a VM.",
    ),
    Scenario(
        id="stratis-pool-create-0007",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="multi",
        user_input="create pool apppool on /dev/sde and then create a filesystem called appdata inside it",
        notes="Multi-step: pool creation followed by filesystem creation.",
    ),
    Scenario(
        id="stratis-pool-create-0008",
        tool="stratis",
        operation="pool-create",
        permission_class=_pc("pool-create"),
        complexity="single",
        user_input="provision a new stratis pool named logpool on /dev/sdf for log storage",
        notes="WRITE: dedicated pool for log data.",
    ),

    # =========================================================================
    # pool-destroy  (DESTRUCTIVE) — 6 entries
    # =========================================================================

    Scenario(
        id="stratis-pool-destroy-0001",
        tool="stratis",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="single",
        user_input="destroy the stratis pool named testpool",
        notes="DESTRUCTIVE: remove a test pool; all data in the pool is lost.",
    ),
    Scenario(
        id="stratis-pool-destroy-0002",
        tool="stratis",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="single",
        user_input="tear down the oldpool stratis pool — it is decommissioned",
        notes="DESTRUCTIVE: decommission an unused pool.",
    ),
    Scenario(
        id="stratis-pool-destroy-0003",
        tool="stratis",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="multi",
        user_input="destroy the stratis pool temppool after confirming no filesystems remain in it",
        notes="Multi-step DESTRUCTIVE: verify empty then destroy.",
    ),
    Scenario(
        id="stratis-pool-destroy-0004",
        tool="stratis",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="diagnostic",
        user_input="the disk backing stgpool is failing — destroy the pool before the disk dies completely",
        notes="Diagnostic-triggered DESTRUCTIVE: emergency pool removal before hardware failure.",
    ),
    Scenario(
        id="stratis-pool-destroy-0005",
        tool="stratis",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="single",
        user_input="remove the stratis pool devpool used only in development",
        notes="DESTRUCTIVE: remove a development-only pool.",
    ),
    Scenario(
        id="stratis-pool-destroy-0006",
        tool="stratis",
        operation="pool-destroy",
        permission_class=_pc("pool-destroy"),
        complexity="multi",
        user_input="destroy archivepool and reclaim its block devices for reuse",
        notes="Multi-step DESTRUCTIVE: pool destruction followed by block device reuse planning.",
    ),

    # =========================================================================
    # filesystem-list  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="stratis-filesystem-list-0001",
        tool="stratis",
        operation="filesystem-list",
        permission_class=_pc("filesystem-list"),
        complexity="single",
        user_input="show all stratis filesystems",
        notes="READ: list all Stratis filesystems across all pools.",
    ),
    Scenario(
        id="stratis-filesystem-list-0002",
        tool="stratis",
        operation="filesystem-list",
        permission_class=_pc("filesystem-list"),
        complexity="single",
        user_input="list the filesystems in the datapool stratis pool",
        notes="READ: list filesystems scoped to a specific pool.",
    ),
    Scenario(
        id="stratis-filesystem-list-0003",
        tool="stratis",
        operation="filesystem-list",
        permission_class=_pc("filesystem-list"),
        complexity="diagnostic",
        user_input="what filesystems exist in the prodpool — I need to check before running maintenance",
        notes="Diagnostic: pre-maintenance inventory of filesystems.",
    ),
    Scenario(
        id="stratis-filesystem-list-0004",
        tool="stratis",
        operation="filesystem-list",
        permission_class=_pc("filesystem-list"),
        complexity="multi",
        user_input="list all stratis filesystems and identify which ones are using more than 10 GiB",
        notes="Multi-step: list then interpret usage columns.",
    ),
    Scenario(
        id="stratis-filesystem-list-0005",
        tool="stratis",
        operation="filesystem-list",
        permission_class=_pc("filesystem-list"),
        complexity="single",
        user_input="what stratis filesystems are in the backuppool?",
        notes="READ: filesystem inventory for backup pool.",
    ),
    Scenario(
        id="stratis-filesystem-list-0006",
        tool="stratis",
        operation="filesystem-list",
        permission_class=_pc("filesystem-list"),
        complexity="diagnostic",
        user_input="a mount point is missing — check which stratis filesystems exist in logpool",
        notes="Diagnostic: trace a missing mount to its Stratis filesystem.",
    ),
    Scenario(
        id="stratis-filesystem-list-0007",
        tool="stratis",
        operation="filesystem-list",
        permission_class=_pc("filesystem-list"),
        complexity="single",
        user_input="list all stratis filesystems on this system",
        notes="READ: full filesystem inventory across all pools.",
    ),

    # =========================================================================
    # filesystem-create  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="stratis-filesystem-create-0001",
        tool="stratis",
        operation="filesystem-create",
        permission_class=_pc("filesystem-create"),
        complexity="single",
        user_input="create a stratis filesystem called appdata in the datapool",
        notes="WRITE: create an application data filesystem.",
    ),
    Scenario(
        id="stratis-filesystem-create-0002",
        tool="stratis",
        operation="filesystem-create",
        permission_class=_pc("filesystem-create"),
        complexity="single",
        user_input="set up a new stratis filesystem named homefs in homespool",
        notes="WRITE: create a filesystem for home directories.",
    ),
    Scenario(
        id="stratis-filesystem-create-0003",
        tool="stratis",
        operation="filesystem-create",
        permission_class=_pc("filesystem-create"),
        complexity="multi",
        user_input="create a filesystem called logdata in logpool and then mount it at /var/log/app",
        notes="Multi-step: create filesystem then mount it.",
    ),
    Scenario(
        id="stratis-filesystem-create-0004",
        tool="stratis",
        operation="filesystem-create",
        permission_class=_pc("filesystem-create"),
        complexity="single",
        user_input="add a stratis filesystem named dbdata to the prodpool for postgres storage",
        notes="WRITE: create a filesystem for database storage.",
    ),
    Scenario(
        id="stratis-filesystem-create-0005",
        tool="stratis",
        operation="filesystem-create",
        permission_class=_pc("filesystem-create"),
        complexity="diagnostic",
        user_input="the app team needs more storage — create a stratis filesystem tmpdata in devpool",
        notes="Diagnostic-triggered WRITE: provision new storage based on a request.",
    ),
    Scenario(
        id="stratis-filesystem-create-0006",
        tool="stratis",
        operation="filesystem-create",
        permission_class=_pc("filesystem-create"),
        complexity="single",
        user_input="create filesystem backupdata in backuppool for daily backup targets",
        notes="WRITE: filesystem creation for backup target storage.",
    ),
    Scenario(
        id="stratis-filesystem-create-0007",
        tool="stratis",
        operation="filesystem-create",
        permission_class=_pc("filesystem-create"),
        complexity="multi",
        user_input="create a stratis filesystem testfs in testpool and list the pool filesystems to confirm",
        notes="Multi-step: create then verify with filesystem-list.",
    ),

    # =========================================================================
    # filesystem-snapshot  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="stratis-filesystem-snapshot-0001",
        tool="stratis",
        operation="filesystem-snapshot",
        permission_class=_pc("filesystem-snapshot"),
        complexity="single",
        user_input="take a snapshot of the appdata filesystem in datapool called appdata-snap1",
        notes="WRITE: point-in-time snapshot before a deployment.",
    ),
    Scenario(
        id="stratis-filesystem-snapshot-0002",
        tool="stratis",
        operation="filesystem-snapshot",
        permission_class=_pc("filesystem-snapshot"),
        complexity="single",
        user_input="snapshot the dbdata filesystem in prodpool as dbdata-before-migration",
        notes="WRITE: pre-migration snapshot for rollback safety.",
    ),
    Scenario(
        id="stratis-filesystem-snapshot-0003",
        tool="stratis",
        operation="filesystem-snapshot",
        permission_class=_pc("filesystem-snapshot"),
        complexity="multi",
        user_input="create a snapshot of homefs in homespool named homefs-backup and verify it appears in the filesystem list",
        notes="Multi-step: snapshot then verify with filesystem-list.",
    ),
    Scenario(
        id="stratis-filesystem-snapshot-0004",
        tool="stratis",
        operation="filesystem-snapshot",
        permission_class=_pc("filesystem-snapshot"),
        complexity="diagnostic",
        user_input="before the upgrade, snapshot the rootfs in datapool as rootfs-pre-upgrade",
        notes="Diagnostic-triggered WRITE: snapshot before a risky operation.",
    ),
    Scenario(
        id="stratis-filesystem-snapshot-0005",
        tool="stratis",
        operation="filesystem-snapshot",
        permission_class=_pc("filesystem-snapshot"),
        complexity="single",
        user_input="create a stratis snapshot of logdata in logpool called logdata-snap-20260704",
        notes="WRITE: daily snapshot of log filesystem.",
    ),
    Scenario(
        id="stratis-filesystem-snapshot-0006",
        tool="stratis",
        operation="filesystem-snapshot",
        permission_class=_pc("filesystem-snapshot"),
        complexity="single",
        user_input="snapshot appdata in datapool as appdata-snap-rollback so we can roll back if needed",
        notes="WRITE: rollback snapshot before configuration change.",
    ),
    Scenario(
        id="stratis-filesystem-snapshot-0007",
        tool="stratis",
        operation="filesystem-snapshot",
        permission_class=_pc("filesystem-snapshot"),
        complexity="multi",
        user_input="take a snapshot of backupdata in backuppool as backupdata-snap and then check disk usage",
        notes="Multi-step: snapshot then check pool usage.",
    ),

    # =========================================================================
    # filesystem-destroy  (DESTRUCTIVE) — 6 entries
    # =========================================================================

    Scenario(
        id="stratis-filesystem-destroy-0001",
        tool="stratis",
        operation="filesystem-destroy",
        permission_class=_pc("filesystem-destroy"),
        complexity="single",
        user_input="destroy the testfs stratis filesystem in testpool",
        notes="DESTRUCTIVE: remove a test filesystem; data is permanently lost.",
    ),
    Scenario(
        id="stratis-filesystem-destroy-0002",
        tool="stratis",
        operation="filesystem-destroy",
        permission_class=_pc("filesystem-destroy"),
        complexity="single",
        user_input="delete the stratis filesystem olddata from archivepool — it is no longer needed",
        notes="DESTRUCTIVE: remove a decommissioned filesystem.",
    ),
    Scenario(
        id="stratis-filesystem-destroy-0003",
        tool="stratis",
        operation="filesystem-destroy",
        permission_class=_pc("filesystem-destroy"),
        complexity="multi",
        user_input="unmount the tmpfs filesystem and then destroy it from devpool",
        notes="Multi-step DESTRUCTIVE: unmount then destroy.",
    ),
    Scenario(
        id="stratis-filesystem-destroy-0004",
        tool="stratis",
        operation="filesystem-destroy",
        permission_class=_pc("filesystem-destroy"),
        complexity="diagnostic",
        user_input="the filesystem snapdata in logpool is stale — destroy it to free space",
        notes="Diagnostic-triggered DESTRUCTIVE: destroy a stale snapshot filesystem to reclaim space.",
    ),
    Scenario(
        id="stratis-filesystem-destroy-0005",
        tool="stratis",
        operation="filesystem-destroy",
        permission_class=_pc("filesystem-destroy"),
        complexity="single",
        user_input="remove the dev-scratch filesystem from devpool permanently",
        notes="DESTRUCTIVE: remove a temporary development filesystem.",
    ),
    Scenario(
        id="stratis-filesystem-destroy-0006",
        tool="stratis",
        operation="filesystem-destroy",
        permission_class=_pc("filesystem-destroy"),
        complexity="multi",
        user_input="destroy the appdata-snap-old snapshot filesystem in datapool and confirm it is gone",
        notes="Multi-step DESTRUCTIVE: destroy an old snapshot then verify removal via filesystem-list.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("stratis").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "stratis", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("stratis").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
