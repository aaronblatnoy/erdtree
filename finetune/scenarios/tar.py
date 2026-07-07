"""finetune/scenarios/tar.py — Scenario corpus for the 'tar' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list       READ   — list the contents of a tar archive
  create     WRITE  — create an uncompressed tar archive
  extract    WRITE  — extract files from a tar archive
  verify     READ   — compare archive contents against the filesystem
  create_gz  WRITE  — create a gzip-compressed tar archive
  create_bz2 WRITE  — create a bzip2-compressed tar archive
  create_xz  WRITE  — create an xz-compressed tar archive

Coverage targets
----------------
  >= 40 entries total across all 7 operations.
  All three complexities represented: single | multi | diagnostic.

INV-schema-sync: permission_class for each entry is derived from the LIVE
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
# Compatible field names are EXACT so the Phase-13 JOIN can unify without renames.
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
    """Return the live permission class for a tar operation."""
    return registry.get("tar").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="tar-list-0001",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what files are in /backup/etc-backup.tar?",
        notes="Basic archive content inspection.",
    ),
    Scenario(
        id="tar-list-0002",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list the contents of the weekly-backup.tar.gz archive",
        notes="List contents of a compressed archive.",
    ),
    Scenario(
        id="tar-list-0003",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me what is inside /var/backups/home-2026-07-01.tar.xz",
        notes="Listing an xz-compressed backup archive.",
    ),
    Scenario(
        id="tar-list-0004",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list the files in /backup/configs.tar and check if nginx.conf is included",
        notes="Multi-step: list then search output for a specific file.",
    ),
    Scenario(
        id="tar-list-0005",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="the restore failed — show me what files are actually in the archive so I can see what we have",
        notes="Diagnostic: inspect archive contents after a failed restore attempt.",
    ),
    Scenario(
        id="tar-list-0006",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what is in /mnt/nas/database-dump.tar.bz2?",
        notes="Listing a bzip2-compressed database dump archive.",
    ),
    Scenario(
        id="tar-list-0007",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="before I extract the archive, show me its contents so I know where files will land",
        notes="Diagnostic: pre-extract inspection to avoid path collisions.",
    ),
    Scenario(
        id="tar-list-0008",
        tool="tar",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="list the contents of last night's backup tarball and count how many files it contains",
        notes="Multi-step: list archive and aggregate file count from output.",
    ),

    # =========================================================================
    # create  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="tar-create-0001",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="create a tar archive of /etc and save it to /backup/etc-backup.tar",
        notes="WRITE: archive the system config directory.",
    ),
    Scenario(
        id="tar-create-0002",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="pack up /var/log into /backup/logs-2026-07-01.tar",
        notes="WRITE: archive log directory for off-host storage.",
    ),
    Scenario(
        id="tar-create-0003",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="tar up the /home/deploy directory before we do the upgrade",
        notes="WRITE: pre-upgrade user directory backup.",
    ),
    Scenario(
        id="tar-create-0004",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="multi",
        user_input="create a tar archive of /etc and then list its contents to verify",
        notes="Multi-step: create then verify by listing contents.",
    ),
    Scenario(
        id="tar-create-0005",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="diagnostic",
        user_input="before rolling back nginx, archive /etc/nginx so we can restore it if needed",
        notes="Diagnostic-triggered WRITE: backup before a config rollback.",
    ),
    Scenario(
        id="tar-create-0006",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="bundle /opt/app into /backup/app-snapshot.tar for the release cutover",
        notes="WRITE: application snapshot before cutover.",
    ),
    Scenario(
        id="tar-create-0007",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="single",
        user_input="archive /var/lib/postgresql/data to /backup/pgdata.tar",
        notes="WRITE: database data directory tar backup (no compression).",
    ),
    Scenario(
        id="tar-create-0008",
        tool="tar",
        operation="create",
        permission_class=_pc("create"),
        complexity="multi",
        user_input="create a tar of /etc/ssl and then check its size on disk",
        notes="Multi-step: create archive then inspect size for storage planning.",
    ),

    # =========================================================================
    # extract  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="tar-extract-0001",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="single",
        user_input="extract /backup/etc-backup.tar to /restore/etc",
        notes="WRITE: restore config directory from backup.",
    ),
    Scenario(
        id="tar-extract-0002",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="single",
        user_input="unpack the weekly-backup.tar.gz into /tmp/restore",
        notes="WRITE: extract compressed backup to a staging directory.",
    ),
    Scenario(
        id="tar-extract-0003",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="single",
        user_input="extract the app tarball to /opt/app-restore",
        notes="WRITE: deploy application from a tar archive.",
    ),
    Scenario(
        id="tar-extract-0004",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="multi",
        user_input="extract /backup/configs.tar.xz to /tmp and then check that the files landed correctly",
        notes="Multi-step: extract then verify extracted files exist.",
    ),
    Scenario(
        id="tar-extract-0005",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="diagnostic",
        user_input="nginx config got corrupted — restore it from the backup archive to /etc/nginx",
        notes="Diagnostic-triggered WRITE: emergency restore of a corrupted config.",
    ),
    Scenario(
        id="tar-extract-0006",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="single",
        user_input="untar the database snapshot into /var/lib/postgresql/data",
        notes="WRITE: restore database data directory from backup.",
    ),
    Scenario(
        id="tar-extract-0007",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="single",
        user_input="extract /mnt/backup/home-archive.tar.bz2 to /home",
        notes="WRITE: restore home directories from bzip2 backup.",
    ),
    Scenario(
        id="tar-extract-0008",
        tool="tar",
        operation="extract",
        permission_class=_pc("extract"),
        complexity="multi",
        user_input="unpack the SSL certs archive to /etc/ssl and then restart nginx to pick up the new certs",
        notes="Multi-step: extract certs then restart the service.",
    ),

    # =========================================================================
    # verify  (READ) — 6 entries
    # =========================================================================

    Scenario(
        id="tar-verify-0001",
        tool="tar",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="single",
        user_input="verify that the /backup/etc-backup.tar archive matches what is on disk",
        notes="Read: compare archive to filesystem to detect drift.",
    ),
    Scenario(
        id="tar-verify-0002",
        tool="tar",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="single",
        user_input="check if last night's backup is consistent with the current state of /etc",
        notes="Read: backup consistency check before removing old copies.",
    ),
    Scenario(
        id="tar-verify-0003",
        tool="tar",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="multi",
        user_input="verify the app backup and if there are differences report which files changed",
        notes="Multi-step: verify archive and interpret diff output.",
    ),
    Scenario(
        id="tar-verify-0004",
        tool="tar",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="diagnostic",
        user_input="before I delete the source files I need to verify the archive is intact",
        notes="Diagnostic: verify archive integrity before removing source data.",
    ),
    Scenario(
        id="tar-verify-0005",
        tool="tar",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="single",
        user_input="does the /backup/ssl-certs.tar match the certs that are currently installed?",
        notes="Read: certificate backup integrity check.",
    ),
    Scenario(
        id="tar-verify-0006",
        tool="tar",
        operation="verify",
        permission_class=_pc("verify"),
        complexity="diagnostic",
        user_input="the backup job ran but I am not sure it captured everything — verify the archive against the source",
        notes="Diagnostic: post-backup integrity verification.",
    ),

    # =========================================================================
    # create_gz  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="tar-create_gz-0001",
        tool="tar",
        operation="create_gz",
        permission_class=_pc("create_gz"),
        complexity="single",
        user_input="create a gzip-compressed tar of /etc and save it as /backup/etc-2026-07-01.tar.gz",
        notes="WRITE: compressed config backup.",
    ),
    Scenario(
        id="tar-create_gz-0002",
        tool="tar",
        operation="create_gz",
        permission_class=_pc("create_gz"),
        complexity="single",
        user_input="compress /var/log into a .tar.gz for archiving",
        notes="WRITE: compressed log archive for off-host transfer.",
    ),
    Scenario(
        id="tar-create_gz-0003",
        tool="tar",
        operation="create_gz",
        permission_class=_pc("create_gz"),
        complexity="multi",
        user_input="create a .tar.gz of the web root and then verify the archive before uploading",
        notes="Multi-step: create compressed archive then verify integrity.",
    ),
    Scenario(
        id="tar-create_gz-0004",
        tool="tar",
        operation="create_gz",
        permission_class=_pc("create_gz"),
        complexity="single",
        user_input="make a tgz of /opt/app for deployment to the staging server",
        notes="WRITE: application deployment package as .tar.gz.",
    ),
    Scenario(
        id="tar-create_gz-0005",
        tool="tar",
        operation="create_gz",
        permission_class=_pc("create_gz"),
        complexity="diagnostic",
        user_input="we are running low on disk — compress the old log files into a .tar.gz to free space",
        notes="Diagnostic-triggered WRITE: compress logs to recover disk space.",
    ),

    # =========================================================================
    # create_bz2  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="tar-create_bz2-0001",
        tool="tar",
        operation="create_bz2",
        permission_class=_pc("create_bz2"),
        complexity="single",
        user_input="create a bzip2-compressed backup of /etc/nginx as /backup/nginx-conf.tar.bz2",
        notes="WRITE: bzip2-compressed nginx config backup.",
    ),
    Scenario(
        id="tar-create_bz2-0002",
        tool="tar",
        operation="create_bz2",
        permission_class=_pc("create_bz2"),
        complexity="single",
        user_input="archive /var/lib/mysql with bzip2 compression to /backup/mysql-data.tar.bz2",
        notes="WRITE: bzip2-compressed database data backup.",
    ),
    Scenario(
        id="tar-create_bz2-0003",
        tool="tar",
        operation="create_bz2",
        permission_class=_pc("create_bz2"),
        complexity="multi",
        user_input="create a .tar.bz2 of the home directories and then check how big the archive is",
        notes="Multi-step: create bzip2 archive then inspect size.",
    ),
    Scenario(
        id="tar-create_bz2-0004",
        tool="tar",
        operation="create_bz2",
        permission_class=_pc("create_bz2"),
        complexity="single",
        user_input="pack up /srv/www with bzip2 compression for the weekly offsite backup",
        notes="WRITE: bzip2-compressed web content backup.",
    ),
    Scenario(
        id="tar-create_bz2-0005",
        tool="tar",
        operation="create_bz2",
        permission_class=_pc("create_bz2"),
        complexity="diagnostic",
        user_input="before migrating the database host, create a bzip2 archive of all data in /var/lib/pgsql",
        notes="Diagnostic-triggered WRITE: pre-migration bzip2 archive.",
    ),

    # =========================================================================
    # create_xz  (WRITE) — 5 entries
    # =========================================================================

    Scenario(
        id="tar-create_xz-0001",
        tool="tar",
        operation="create_xz",
        permission_class=_pc("create_xz"),
        complexity="single",
        user_input="create an xz-compressed archive of /etc for long-term storage",
        notes="WRITE: xz-compressed config archive — best compression ratio for cold storage.",
    ),
    Scenario(
        id="tar-create_xz-0002",
        tool="tar",
        operation="create_xz",
        permission_class=_pc("create_xz"),
        complexity="single",
        user_input="compress /var/lib/postgresql/data into a .tar.xz backup",
        notes="WRITE: xz-compressed database backup for maximum compression.",
    ),
    Scenario(
        id="tar-create_xz-0003",
        tool="tar",
        operation="create_xz",
        permission_class=_pc("create_xz"),
        complexity="multi",
        user_input="create a .tar.xz of the entire /opt directory and verify the result",
        notes="Multi-step: create xz archive then verify integrity.",
    ),
    Scenario(
        id="tar-create_xz-0004",
        tool="tar",
        operation="create_xz",
        permission_class=_pc("create_xz"),
        complexity="single",
        user_input="archive /home with xz compression to save space on the backup server",
        notes="WRITE: xz-compressed home directory backup.",
    ),
    Scenario(
        id="tar-create_xz-0005",
        tool="tar",
        operation="create_xz",
        permission_class=_pc("create_xz"),
        complexity="diagnostic",
        user_input="the NFS backup target has limited space — use xz compression to make the archive as small as possible",
        notes="Diagnostic-triggered WRITE: use xz compression for space-constrained backup target.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("tar").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "tar", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("tar").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
