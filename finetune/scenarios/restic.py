"""finetune/scenarios/restic.py — Scenario corpus for the 'restic' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  snapshots    READ        — list all snapshots in the repository
  backup       WRITE       — create a new backup snapshot of a path
  restore      WRITE       — restore a snapshot to a target directory
  forget       WRITE       — remove a specific snapshot from the index
  forget_prune DESTRUCTIVE — remove old snapshots and prune pack data

Coverage targets
----------------
  >= 40 entries total across all 5 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach
  the explicit-confirm-before-destructive gate.

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
# Scenario dataclass — field names EXACT for Phase-13 JOIN
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
    """Return the live permission class for a restic operation."""
    return registry.get("restic").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # snapshots  (READ) — 11 entries
    # =========================================================================

    Scenario(
        id="restic-snapshots-0001",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="single",
        user_input="list all restic backup snapshots",
        notes="Basic READ: enumerate all stored snapshots.",
    ),
    Scenario(
        id="restic-snapshots-0002",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="single",
        user_input="show me the backups in /var/backup/restic",
        notes="READ with explicit repo path.",
    ),
    Scenario(
        id="restic-snapshots-0003",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="single",
        user_input="what backups do we have tagged 'weekly'?",
        notes="READ filtered by tag.",
    ),
    Scenario(
        id="restic-snapshots-0004",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="multi",
        user_input="list snapshots and check whether last night's backup completed",
        notes="Multi-step: list then inspect the most-recent timestamp.",
    ),
    Scenario(
        id="restic-snapshots-0005",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="diagnostic",
        user_input="the nightly cron says the backup ran but I'm not sure it saved — show me the snapshots",
        notes="Diagnostic: verify backup existence after cron job reports success.",
    ),
    Scenario(
        id="restic-snapshots-0006",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="single",
        user_input="list snapshots from host db-primary only",
        notes="READ filtered by hostname.",
    ),
    Scenario(
        id="restic-snapshots-0007",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="single",
        user_input="show restic snapshots tagged 'monthly'",
        notes="READ filtered by monthly retention tag.",
    ),
    Scenario(
        id="restic-snapshots-0008",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="diagnostic",
        user_input="I need to pick a snapshot to restore from — list them all with dates",
        notes="Diagnostic: enumerate snapshots to choose a restore point.",
    ),
    Scenario(
        id="restic-snapshots-0009",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="multi",
        user_input="show snapshots then tell me how many we have this week",
        notes="Multi-step: list and count weekly snapshots.",
    ),
    Scenario(
        id="restic-snapshots-0010",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="single",
        user_input="how many restic backups exist for /home?",
        notes="READ: count snapshots scoped to home path.",
    ),
    Scenario(
        id="restic-snapshots-0011",
        tool="restic",
        operation="snapshots",
        permission_class=_pc("snapshots"),
        complexity="diagnostic",
        user_input="the compliance report needs a snapshot inventory — pull the full list",
        notes="Diagnostic: generate snapshot inventory for compliance reporting.",
    ),

    # =========================================================================
    # backup  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="restic-backup-0001",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="back up /etc to the restic repo",
        notes="WRITE: create a snapshot of /etc.",
    ),
    Scenario(
        id="restic-backup-0002",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="run a restic backup on /home right now",
        notes="WRITE: back up home directory.",
    ),
    Scenario(
        id="restic-backup-0003",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="create a backup of /var/www with the tag 'pre-deploy'",
        notes="WRITE: tagged pre-deployment snapshot.",
    ),
    Scenario(
        id="restic-backup-0004",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="multi",
        user_input="back up /etc and then confirm the snapshot was saved",
        notes="Multi-step: backup then verify via snapshots.",
    ),
    Scenario(
        id="restic-backup-0005",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="diagnostic",
        user_input="the config file changed — take a backup before we apply the new version",
        notes="Diagnostic-triggered WRITE: snapshot before a config change.",
    ),
    Scenario(
        id="restic-backup-0006",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="backup /var/lib/postgresql to /mnt/backups/restic tagged 'weekly'",
        notes="WRITE: weekly database file backup.",
    ),
    Scenario(
        id="restic-backup-0007",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="take a snapshot of /opt/app before the upgrade",
        notes="WRITE: pre-upgrade snapshot of application directory.",
    ),
    Scenario(
        id="restic-backup-0008",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="multi",
        user_input="back up /etc then /home and list all snapshots when done",
        notes="Multi-step: backup two paths then list snapshots.",
    ),
    Scenario(
        id="restic-backup-0009",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="create a restic snapshot of /srv/data",
        notes="WRITE: snapshot of application data directory.",
    ),
    Scenario(
        id="restic-backup-0010",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="diagnostic",
        user_input="a disk replacement is scheduled — run a full backup of /data first",
        notes="Diagnostic-triggered WRITE: backup before storage maintenance.",
    ),
    Scenario(
        id="restic-backup-0011",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="restic backup /etc/nginx tagged 'nginx-config'",
        notes="WRITE: snapshot nginx config directory with descriptive tag.",
    ),
    Scenario(
        id="restic-backup-0012",
        tool="restic",
        operation="backup",
        permission_class=_pc("backup"),
        complexity="single",
        user_input="back up the cron jobs directory at /var/spool/cron",
        notes="WRITE: snapshot cron job definitions.",
    ),

    # =========================================================================
    # restore  (WRITE) — 10 entries
    # =========================================================================

    Scenario(
        id="restic-restore-0001",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="single",
        user_input="restore the latest restic snapshot to /tmp/restore",
        notes="WRITE: restore most-recent snapshot.",
    ),
    Scenario(
        id="restic-restore-0002",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="single",
        user_input="restore snapshot abc12345 to /mnt/recovery",
        notes="WRITE: restore specific snapshot by ID.",
    ),
    Scenario(
        id="restic-restore-0003",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="multi",
        user_input="restore the latest snapshot then verify the config files look correct",
        notes="Multi-step: restore then inspect restored content.",
    ),
    Scenario(
        id="restic-restore-0004",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="diagnostic",
        user_input="we have a corrupted /etc/nginx/nginx.conf — restore from the backup taken before the bad deploy",
        notes="Diagnostic: restore a specific snapshot to recover from a bad deployment.",
    ),
    Scenario(
        id="restic-restore-0005",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="single",
        user_input="recover /home from snapshot def67890 into /tmp/home-recovery",
        notes="WRITE: targeted recovery of home directory snapshot.",
    ),
    Scenario(
        id="restic-restore-0006",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="diagnostic",
        user_input="the database data dir is corrupted — restore the last known good snapshot",
        notes="Diagnostic: restore after data directory corruption.",
    ),
    Scenario(
        id="restic-restore-0007",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="multi",
        user_input="restore snapshot from 2026-07-01 to /tmp/audit-restore then check the files",
        notes="Multi-step: restore for audit review then verify file counts.",
    ),
    Scenario(
        id="restic-restore-0008",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="single",
        user_input="restore the weekly backup to /mnt/dr-test for a disaster-recovery drill",
        notes="WRITE: restore to a scratch target for DR testing.",
    ),
    Scenario(
        id="restic-restore-0009",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="single",
        user_input="pull back yesterday's /etc snapshot to /tmp/etc-yesterday",
        notes="WRITE: point-in-time /etc recovery.",
    ),
    Scenario(
        id="restic-restore-0010",
        tool="restic",
        operation="restore",
        permission_class=_pc("restore"),
        complexity="diagnostic",
        user_input="certs are missing after the failed update — restore from last night's snapshot",
        notes="Diagnostic: restore TLS certificates from backup after failed update.",
    ),

    # =========================================================================
    # forget  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="restic-forget-0001",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="single",
        user_input="remove snapshot abc12345 from the repository",
        notes="WRITE: forget a specific snapshot by ID.",
    ),
    Scenario(
        id="restic-forget-0002",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="single",
        user_input="delete the test snapshot def67890 — it was just a dry run",
        notes="WRITE: forget a test/throwaway snapshot.",
    ),
    Scenario(
        id="restic-forget-0003",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="multi",
        user_input="forget snapshot 1a2b3c4d then list remaining snapshots",
        notes="Multi-step: forget then verify remaining snapshots.",
    ),
    Scenario(
        id="restic-forget-0004",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="diagnostic",
        user_input="the snapshot from 2026-07-01 is known-bad — remove it from the index",
        notes="Diagnostic-triggered WRITE: forget a known-corrupt snapshot.",
    ),
    Scenario(
        id="restic-forget-0005",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="single",
        user_input="remove the snapshot tagged 'failed-deploy' from the repo",
        notes="WRITE: forget a snapshot created during a failed deployment.",
    ),
    Scenario(
        id="restic-forget-0006",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="single",
        user_input="forget snapshot 9f8e7d6c from /mnt/backups/restic",
        notes="WRITE: forget with explicit repo path.",
    ),
    Scenario(
        id="restic-forget-0007",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="multi",
        user_input="drop the pre-migration snapshot then confirm we still have at least three left",
        notes="Multi-step: forget then count remaining snapshots for retention check.",
    ),
    Scenario(
        id="restic-forget-0008",
        tool="restic",
        operation="forget",
        permission_class=_pc("forget"),
        complexity="diagnostic",
        user_input="the audit shows snapshot 0011aabb is duplicated — remove the older one",
        notes="Diagnostic: de-duplicate snapshots by forgetting the redundant one.",
    ),

    # =========================================================================
    # forget_prune  (DESTRUCTIVE) — 11 entries
    # =========================================================================

    Scenario(
        id="restic-forget_prune-0001",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="single",
        user_input="prune old backups keeping only the last 7 snapshots",
        notes="DESTRUCTIVE: prune with --keep-last 7 retention policy.",
    ),
    Scenario(
        id="restic-forget_prune-0002",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="single",
        user_input="run restic forget --prune to free up disk space",
        notes="DESTRUCTIVE: explicit prune to reclaim repository storage.",
    ),
    Scenario(
        id="restic-forget_prune-0003",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="multi",
        user_input="prune the restic repo keeping 14 snapshots then list what remains",
        notes="Multi-step: prune with keep-last 14 then verify remaining snapshots.",
    ),
    Scenario(
        id="restic-forget_prune-0004",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="diagnostic",
        user_input="the backup disk is 90% full — prune old snapshots and keep only the last 5",
        notes="Diagnostic: storage-pressure-triggered prune with tight retention.",
    ),
    Scenario(
        id="restic-forget_prune-0005",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="single",
        user_input="clean up the restic repository by removing and pruning snapshots older than 30 days",
        notes="DESTRUCTIVE: prune with no keep_last (remove all policy-expired data).",
    ),
    Scenario(
        id="restic-forget_prune-0006",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="diagnostic",
        user_input="disk alert fired on the backup server — run a prune to recover space immediately",
        notes="Diagnostic: emergency prune triggered by disk space alert.",
    ),
    Scenario(
        id="restic-forget_prune-0007",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="single",
        user_input="prune the backup repo at /mnt/nas/restic keeping the last 10 snapshots for this host",
        notes="DESTRUCTIVE: prune with repo path, keep-last 10, host filter.",
    ),
    Scenario(
        id="restic-forget_prune-0008",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="multi",
        user_input="prune monthly retention — keep 12 then confirm disk space freed",
        notes="Multi-step: prune with keep-last 12 then check disk usage.",
    ),
    Scenario(
        id="restic-forget_prune-0009",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="single",
        user_input="enforce the backup retention policy: forget and prune, keep last 30",
        notes="DESTRUCTIVE: enforce retention policy via forget --prune with keep-last 30.",
    ),
    Scenario(
        id="restic-forget_prune-0010",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="diagnostic",
        user_input="the compliance window closes tonight — prune snapshots outside the 90-day window",
        notes="Diagnostic: compliance-driven prune before retention window closes.",
    ),
    Scenario(
        id="restic-forget_prune-0011",
        tool="restic",
        operation="forget_prune",
        permission_class=_pc("forget_prune"),
        complexity="single",
        user_input="forget all old snapshots tagged 'staging' and prune the data",
        notes="DESTRUCTIVE: prune snapshots filtered by tag 'staging'.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("restic").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "restic", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("restic").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
