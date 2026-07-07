"""finetune/scenarios/rsync.py — Scenario corpus for the 'rsync' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  dry-run      READ        — preview what rsync would transfer without changes
  sync         WRITE       — synchronise source to destination
  sync-delete  DESTRUCTIVE — sync and remove destination files absent from source
  progress     READ        — dry-run with progress/stats display, no data transferred

Coverage targets
----------------
  >= 40 entries total across all 4 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach
  the typed-confirmation gate.

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
    """Return the live permission class for an rsync operation.

    The lazy import of core.tools.rsync here ensures the tool is registered
    into the registry before the lookup, without triggering the import at
    module-load time (which would cause finetune.coreimports' 11-tool assertion
    to fire before Phase 13 wires all tools).
    """
    import core.tools.rsync  # noqa: F401 — side-effect: registers tool if not yet present
    return registry.get("rsync").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # dry-run  (READ) — 12 entries
    # =========================================================================

    Scenario(
        id="rsync-dry-run-0001",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="single",
        user_input="what files would rsync transfer from /data/app/ to /mnt/backup/app/?",
        notes="Simple dry run preview between two local directories.",
    ),
    Scenario(
        id="rsync-dry-run-0002",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="single",
        user_input="show me what would change if I rsync /etc/ to /backup/etc/",
        notes="Dry run of /etc configuration directory to a backup location.",
    ),
    Scenario(
        id="rsync-dry-run-0003",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="single",
        user_input="preview the rsync from /home/alice/ to /nfs/shares/alice/",
        notes="Dry run for a user home directory to an NFS share target.",
    ),
    Scenario(
        id="rsync-dry-run-0004",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="single",
        user_input="do a dry run of syncing /var/log/ to /archive/logs/",
        notes="Log directory dry-run — checking what log files would be transferred.",
    ),
    Scenario(
        id="rsync-dry-run-0005",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="single",
        user_input="check what rsync would do between /srv/www/ and /mnt/mirror/www/",
        notes="Web root dry run to a mirror mount.",
    ),
    Scenario(
        id="rsync-dry-run-0006",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="multi",
        user_input="preview the rsync from /data/db-dumps/ to /backup/db/ and tell me how many files would transfer",
        notes="Multi-step: dry run then parse output for file count.",
    ),
    Scenario(
        id="rsync-dry-run-0007",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="multi",
        user_input="run a dry run from /opt/app/ to /mnt/offsite/ and flag any files that are new",
        notes="Multi-step: dry run then identify newly created files in the output.",
    ),
    Scenario(
        id="rsync-dry-run-0008",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="diagnostic",
        user_input="the nightly backup seems to be missing files — do a dry run from /data/ to /backup/ so I can see what it would pick up",
        notes="Diagnostic: dry run to investigate a suspected incomplete backup.",
    ),
    Scenario(
        id="rsync-dry-run-0009",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="diagnostic",
        user_input="before I sync /home/ to the new server, preview what rsync would do so I can check for unexpected files",
        notes="Diagnostic: pre-sync review before a migration to detect surprises.",
    ),
    Scenario(
        id="rsync-dry-run-0010",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="single",
        user_input="preview rsync from /var/spool/mail/ to /backup/mail/",
        notes="Dry run of mail spool directory backup.",
    ),
    Scenario(
        id="rsync-dry-run-0011",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="single",
        user_input="do a dry run rsync between /srv/git-repos/ and /mnt/git-backup/",
        notes="Dry run for a git repository mirror.",
    ),
    Scenario(
        id="rsync-dry-run-0012",
        tool="rsync",
        operation="dry-run",
        permission_class=_pc("dry-run"),
        complexity="diagnostic",
        user_input="we suspect some configs drifted — dry run rsync from /etc/nginx/ to /backup/nginx/ to see if anything changed",
        notes="Diagnostic: configuration drift detection via dry run.",
    ),

    # =========================================================================
    # sync  (WRITE) — 12 entries
    # =========================================================================

    Scenario(
        id="rsync-sync-0001",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="sync /data/app/ to /mnt/backup/app/",
        notes="WRITE: straightforward local directory sync.",
    ),
    Scenario(
        id="rsync-sync-0002",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="rsync /etc/nginx/ to /backup/nginx/ to back up the config",
        notes="WRITE: back up an nginx configuration directory.",
    ),
    Scenario(
        id="rsync-sync-0003",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="copy /home/deploy/ to /mnt/nfs/deploy-backup/",
        notes="WRITE: sync a deploy user's home directory to NFS.",
    ),
    Scenario(
        id="rsync-sync-0004",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="sync /var/lib/postgresql/ to /backup/postgres/ for a backup",
        notes="WRITE: PostgreSQL data directory sync for backup.",
    ),
    Scenario(
        id="rsync-sync-0005",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="rsync /opt/app/releases/current/ to /mnt/archive/current/",
        notes="WRITE: archive a release directory via rsync.",
    ),
    Scenario(
        id="rsync-sync-0006",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="multi",
        user_input="sync /data/ to /backup/data/ and then confirm the transfer completed with no errors",
        notes="Multi-step: sync then verify exit code and summary.",
    ),
    Scenario(
        id="rsync-sync-0007",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="multi",
        user_input="rsync /srv/www/ to /mnt/mirror/www/ and tell me how many bytes were transferred",
        notes="Multi-step: sync then parse stats from output.",
    ),
    Scenario(
        id="rsync-sync-0008",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="diagnostic",
        user_input="the standby server has stale data — sync /var/lib/app/ from the primary to /mnt/standby/app/",
        notes="Diagnostic-triggered WRITE: sync to bring a standby up to date.",
    ),
    Scenario(
        id="rsync-sync-0009",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="sync /etc/ to /backup/etc/ before making any system changes",
        notes="WRITE: pre-change configuration backup.",
    ),
    Scenario(
        id="rsync-sync-0010",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="transfer /data/uploads/ to /mnt/cold-storage/uploads/",
        notes="WRITE: move uploaded files to cold storage via rsync.",
    ),
    Scenario(
        id="rsync-sync-0011",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="diagnostic",
        user_input="we had a disk failure on node2 — sync /data/ from node1 to the replacement disk at /mnt/new-disk/",
        notes="Diagnostic-triggered WRITE: disaster recovery data copy.",
    ),
    Scenario(
        id="rsync-sync-0012",
        tool="rsync",
        operation="sync",
        permission_class=_pc("sync"),
        complexity="single",
        user_input="rsync /var/log/ to /backup/logs/ to archive today's logs",
        notes="WRITE: daily log archive sync.",
    ),

    # =========================================================================
    # sync-delete  (DESTRUCTIVE) — 9 entries
    # =========================================================================

    Scenario(
        id="rsync-sync-delete-0001",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="single",
        user_input="sync /data/app/ to /backup/app/ and remove any files in the backup that no longer exist in source",
        notes="DESTRUCTIVE: mirror sync with --delete; extraneous backup files removed.",
    ),
    Scenario(
        id="rsync-sync-delete-0002",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="single",
        user_input="do a mirror rsync from /srv/www/ to /mnt/mirror/www/ deleting stale files",
        notes="DESTRUCTIVE: full mirror of web root, stale mirror files deleted.",
    ),
    Scenario(
        id="rsync-sync-delete-0003",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="single",
        user_input="rsync --delete /etc/ to /backup/etc/ so the backup exactly matches the live config",
        notes="DESTRUCTIVE: exact mirror of /etc; deleted source files are removed from backup.",
    ),
    Scenario(
        id="rsync-sync-delete-0004",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="multi",
        user_input="mirror /data/releases/ to /mnt/archive/releases/ deleting old entries, then confirm what was removed",
        notes="Multi-step DESTRUCTIVE: sync-delete then review deleted-file list in output.",
    ),
    Scenario(
        id="rsync-sync-delete-0005",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="diagnostic",
        user_input="the backup volume has drifted from the source — mirror /data/ to /backup/ with --delete to bring them back in sync",
        notes="Diagnostic-triggered DESTRUCTIVE: re-mirror to fix drift, removing extraneous backup files.",
    ),
    Scenario(
        id="rsync-sync-delete-0006",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="single",
        user_input="sync /home/shared/ to /nfs/shared/ and clean up files that were deleted from source",
        notes="DESTRUCTIVE: shared directory mirror with deleted-file cleanup.",
    ),
    Scenario(
        id="rsync-sync-delete-0007",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="multi",
        user_input="do a full mirror of /var/www/ to /mnt/offsite/www/ with deletion, and tell me how many files were removed",
        notes="Multi-step DESTRUCTIVE: mirror then count deleted files from output.",
    ),
    Scenario(
        id="rsync-sync-delete-0008",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="diagnostic",
        user_input="the DR site is out of date — mirror /opt/app/ to /dr/app/ with delete so the DR copy exactly matches production",
        notes="Diagnostic DESTRUCTIVE: disaster-recovery site sync with full mirror semantics.",
    ),
    Scenario(
        id="rsync-sync-delete-0009",
        tool="rsync",
        operation="sync-delete",
        permission_class=_pc("sync-delete"),
        complexity="single",
        user_input="keep /backup/db-dumps/ exactly in sync with /data/db-dumps/ by deleting anything not in source",
        notes="DESTRUCTIVE: automated backup mirror with delete for database dump directory.",
    ),

    # =========================================================================
    # progress  (READ) — 11 entries
    # =========================================================================

    Scenario(
        id="rsync-progress-0001",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="single",
        user_input="how much data would rsync transfer from /data/ to /backup/?",
        notes="Progress/stats dry run to estimate transfer size before committing.",
    ),
    Scenario(
        id="rsync-progress-0002",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="single",
        user_input="show me the estimated transfer size for syncing /home/ to /mnt/backup/home/",
        notes="Size estimate for home directory backup planning.",
    ),
    Scenario(
        id="rsync-progress-0003",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="single",
        user_input="get transfer stats for rsync from /var/lib/postgresql/ to /backup/postgres/",
        notes="Stats preview for a PostgreSQL data directory sync.",
    ),
    Scenario(
        id="rsync-progress-0004",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="single",
        user_input="estimate how long rsync will take to copy /srv/media/ to /mnt/archive/media/",
        notes="Transfer stats to estimate duration before a large media sync.",
    ),
    Scenario(
        id="rsync-progress-0005",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="multi",
        user_input="get transfer statistics from /data/app/ to /backup/app/ and tell me if it will exceed 10GB",
        notes="Multi-step: progress stats then threshold check.",
    ),
    Scenario(
        id="rsync-progress-0006",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="diagnostic",
        user_input="the backup window is only 2 hours — estimate the rsync transfer from /data/ to /backup/ to see if it will fit",
        notes="Diagnostic: transfer size estimate to assess feasibility within a maintenance window.",
    ),
    Scenario(
        id="rsync-progress-0007",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="single",
        user_input="show rsync progress stats for /etc/ to /backup/etc/ without copying anything",
        notes="Read-only stats view for a configuration directory backup.",
    ),
    Scenario(
        id="rsync-progress-0008",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="single",
        user_input="count the files that rsync would process from /opt/releases/ to /mnt/archive/",
        notes="File count estimate via progress dry run.",
    ),
    Scenario(
        id="rsync-progress-0009",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="multi",
        user_input="get rsync transfer stats from /var/log/ to /archive/logs/ and show me the total bytes",
        notes="Multi-step: progress output then extract total bytes figure.",
    ),
    Scenario(
        id="rsync-progress-0010",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="diagnostic",
        user_input="disk usage spiked on the backup volume — preview the rsync stats from /data/ to /backup/ to see what is being copied",
        notes="Diagnostic: stats preview to investigate unexpected backup volume growth.",
    ),
    Scenario(
        id="rsync-progress-0011",
        tool="rsync",
        operation="progress",
        permission_class=_pc("progress"),
        complexity="single",
        user_input="estimate rsync transfer totals for /srv/www/ to /mnt/offsite/www/",
        notes="Offsite backup sizing estimate via progress dry run.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("rsync").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "rsync", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("rsync").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
