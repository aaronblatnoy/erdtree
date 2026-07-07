"""finetune/scenarios/cron.py — Scenario corpus for the 'cron' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  list       READ        — list the current (or specified) user's crontab entries
  list-all   READ        — list all user crontab files in /var/spool/cron/
  edit       WRITE       — replace a user's crontab with new content
  remove     DESTRUCTIVE — remove an entire crontab (irreversible)
  crond-view READ        — view /etc/cron.d/ file or list the directory
  crond-add  WRITE       — write a new drop-in file to /etc/cron.d/

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios honestly labeled so traces teach the confirmation gate.

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
    """Return the live permission class for a cron operation."""
    return registry.get("cron").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # list  (READ) — 10 entries
    # =========================================================================

    Scenario(
        id="cron-list-0001",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="show me my current crontab",
        notes="Basic crontab listing for the current user.",
    ),
    Scenario(
        id="cron-list-0002",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what cron jobs does the root user have?",
        notes="Listing root's crontab — requires root or sudo.",
    ),
    Scenario(
        id="cron-list-0003",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="list the crontab entries for user 'deploy'",
        notes="Show a service account's scheduled jobs.",
    ),
    Scenario(
        id="cron-list-0004",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="backups are not running — show me the current crontab to check the schedule",
        notes="Diagnostic: inspect crontab to verify backup job definition.",
    ),
    Scenario(
        id="cron-list-0005",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="display the postgres user's crontab",
        notes="Database service account's scheduled tasks.",
    ),
    Scenario(
        id="cron-list-0006",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="show me the crontab for the 'www-data' user and tell me how many jobs are scheduled",
        notes="Multi-step: list then count job entries.",
    ),
    Scenario(
        id="cron-list-0007",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="a script should be running every hour but isn't — check if the cron entry exists",
        notes="Diagnostic: look for a missing or misconfigured hourly entry.",
    ),
    Scenario(
        id="cron-list-0008",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="single",
        user_input="what scheduled tasks does the 'nagios' monitoring user have?",
        notes="Check monitoring service account's cron schedule.",
    ),
    Scenario(
        id="cron-list-0009",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="multi",
        user_input="show my crontab and check if the nightly backup job runs at 2 AM",
        notes="Multi-step: list crontab then verify a specific schedule.",
    ),
    Scenario(
        id="cron-list-0010",
        tool="cron",
        operation="list",
        permission_class=_pc("list"),
        complexity="diagnostic",
        user_input="the log rotation is not happening — check whether logrotate is in the crontab",
        notes="Diagnostic: verify log rotation is scheduled in crontab.",
    ),

    # =========================================================================
    # list-all  (READ) — 7 entries
    # =========================================================================

    Scenario(
        id="cron-list-all-0001",
        tool="cron",
        operation="list-all",
        permission_class=_pc("list-all"),
        complexity="single",
        user_input="show me all user crontabs on this system",
        notes="List all users who have crontab files in /var/spool/cron/.",
    ),
    Scenario(
        id="cron-list-all-0002",
        tool="cron",
        operation="list-all",
        permission_class=_pc("list-all"),
        complexity="diagnostic",
        user_input="which users have scheduled jobs on this host?",
        notes="Diagnostic: audit which accounts have crontabs — security review.",
    ),
    Scenario(
        id="cron-list-all-0003",
        tool="cron",
        operation="list-all",
        permission_class=_pc("list-all"),
        complexity="single",
        user_input="list all crontab files in /var/spool/cron/",
        notes="Direct listing of the cron spool directory.",
    ),
    Scenario(
        id="cron-list-all-0004",
        tool="cron",
        operation="list-all",
        permission_class=_pc("list-all"),
        complexity="multi",
        user_input="show all users with crontabs and then check if 'deploy' is among them",
        notes="Multi-step: list all users then verify a specific account.",
    ),
    Scenario(
        id="cron-list-all-0005",
        tool="cron",
        operation="list-all",
        permission_class=_pc("list-all"),
        complexity="diagnostic",
        user_input="we need a cron audit — show every user that has scheduled tasks",
        notes="Security audit: enumerate all scheduled task owners.",
    ),
    Scenario(
        id="cron-list-all-0006",
        tool="cron",
        operation="list-all",
        permission_class=_pc("list-all"),
        complexity="single",
        user_input="are there any unexpected user crontabs on this server?",
        notes="Security check: list all crontab owners and look for anomalies.",
    ),
    Scenario(
        id="cron-list-all-0007",
        tool="cron",
        operation="list-all",
        permission_class=_pc("list-all"),
        complexity="multi",
        user_input="list all crontabs then show me the ones that were modified recently",
        notes="Multi-step: list crontabs then sort by modification time.",
    ),

    # =========================================================================
    # edit  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="cron-edit-0001",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="single",
        user_input="add a cron job to run /usr/local/bin/backup.sh every day at 2 AM",
        notes="WRITE: install a new crontab with a daily backup entry.",
    ),
    Scenario(
        id="cron-edit-0002",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="single",
        user_input="update the deploy user's crontab to run the deployment check every 5 minutes",
        notes="WRITE: replace a service account's crontab with an updated schedule.",
    ),
    Scenario(
        id="cron-edit-0003",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="multi",
        user_input="add a weekly log cleanup job to root's crontab and verify it was installed",
        notes="Multi-step: edit crontab then list to confirm the new entry.",
    ),
    Scenario(
        id="cron-edit-0004",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="single",
        user_input="install a new crontab for the 'backup' user with the provided schedule",
        notes="WRITE: install a custom crontab for a dedicated backup account.",
    ),
    Scenario(
        id="cron-edit-0005",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="diagnostic",
        user_input="the backup job is running at the wrong time — update the crontab entry to 3 AM",
        notes="Diagnostic-triggered WRITE: correct a misconfigured cron schedule.",
    ),
    Scenario(
        id="cron-edit-0006",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="single",
        user_input="replace the monitoring user's crontab with a new healthcheck schedule",
        notes="WRITE: replace a monitoring account's crontab wholesale.",
    ),
    Scenario(
        id="cron-edit-0007",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="multi",
        user_input="update root's crontab to run disk space checks every hour and confirm the change",
        notes="Multi-step: edit then list to verify the hourly entry was added.",
    ),
    Scenario(
        id="cron-edit-0008",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="single",
        user_input="write a new crontab for the postgres user to run vacuumdb nightly",
        notes="WRITE: schedule a database maintenance task via crontab.",
    ),
    Scenario(
        id="cron-edit-0009",
        tool="cron",
        operation="edit",
        permission_class=_pc("edit"),
        complexity="diagnostic",
        user_input="the certificate renewal is failing — fix the crontab entry so certbot runs on the 1st of each month",
        notes="Diagnostic-triggered WRITE: correct a broken certificate renewal schedule.",
    ),

    # =========================================================================
    # remove  (DESTRUCTIVE) — 8 entries
    # =========================================================================

    Scenario(
        id="cron-remove-0001",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="remove my entire crontab",
        notes="DESTRUCTIVE: wipe the current user's crontab — all jobs deleted.",
    ),
    Scenario(
        id="cron-remove-0002",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="delete all cron jobs for the 'deploy' user",
        notes="DESTRUCTIVE: wipe a service account's entire crontab.",
    ),
    Scenario(
        id="cron-remove-0003",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="clear out the root user's crontab and confirm it is empty",
        notes="DESTRUCTIVE multi-step: remove then list to verify crontab is gone.",
    ),
    Scenario(
        id="cron-remove-0004",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="wipe the legacy-user's crontab — we are decommissioning that account",
        notes="DESTRUCTIVE: remove crontab as part of account decommission.",
    ),
    Scenario(
        id="cron-remove-0005",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="the old backup user keeps running stale jobs — remove its entire crontab",
        notes="DESTRUCTIVE: remove all scheduled jobs for a retired service account.",
    ),
    Scenario(
        id="cron-remove-0006",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="single",
        user_input="clear all scheduled jobs for the 'tempuser' account",
        notes="DESTRUCTIVE: remove a temporary user's entire crontab.",
    ),
    Scenario(
        id="cron-remove-0007",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="multi",
        user_input="remove the 'nagios' user's crontab and list all remaining user crontabs to confirm",
        notes="DESTRUCTIVE multi-step: remove user crontab then list all crontabs.",
    ),
    Scenario(
        id="cron-remove-0008",
        tool="cron",
        operation="remove",
        permission_class=_pc("remove"),
        complexity="diagnostic",
        user_input="there are duplicate jobs running — remove my crontab so I can reinstall it cleanly",
        notes="DESTRUCTIVE diagnostic: purge and reinstall crontab to resolve job duplication.",
    ),

    # =========================================================================
    # crond-view  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="cron-crond-view-0001",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="single",
        user_input="show me what cron drop-in files are in /etc/cron.d/",
        notes="List the /etc/cron.d/ directory — show all system cron files.",
    ),
    Scenario(
        id="cron-crond-view-0002",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="single",
        user_input="show me the contents of /etc/cron.d/backup-jobs",
        notes="View a specific cron.d drop-in file.",
    ),
    Scenario(
        id="cron-crond-view-0003",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="diagnostic",
        user_input="the logrotate job is not running — check the /etc/cron.d/logrotate file",
        notes="Diagnostic: inspect a cron.d drop-in to verify the logrotate schedule.",
    ),
    Scenario(
        id="cron-crond-view-0004",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="single",
        user_input="what jobs are defined in /etc/cron.d/sysstat?",
        notes="View the sysstat performance collection cron drop-in.",
    ),
    Scenario(
        id="cron-crond-view-0005",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="multi",
        user_input="list all files in /etc/cron.d/ and then show me the contents of each one",
        notes="Multi-step: enumerate cron.d files then display each one.",
    ),
    Scenario(
        id="cron-crond-view-0006",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="single",
        user_input="show the /etc/cron.d/aide drop-in file",
        notes="View the AIDE integrity check cron schedule.",
    ),
    Scenario(
        id="cron-crond-view-0007",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="diagnostic",
        user_input="a scheduled task in /etc/cron.d/ is failing — list the directory to audit what's there",
        notes="Diagnostic: enumerate cron.d files to find unexpected or broken entries.",
    ),
    Scenario(
        id="cron-crond-view-0008",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="single",
        user_input="read the 0hourly cron.d file",
        notes="View the built-in Rocky Linux hourly cron runner drop-in.",
    ),
    Scenario(
        id="cron-crond-view-0009",
        tool="cron",
        operation="crond-view",
        permission_class=_pc("crond-view"),
        complexity="multi",
        user_input="show all entries in /etc/cron.d/ and check if any run as root",
        notes="Multi-step: list cron.d files then examine for root-executed entries.",
    ),

    # =========================================================================
    # crond-add  (WRITE) — 9 entries
    # =========================================================================

    Scenario(
        id="cron-crond-add-0001",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="single",
        user_input="add a cron.d file to run the nightly backup script at 2 AM",
        notes="WRITE: create a system-wide cron.d drop-in for the backup job.",
    ),
    Scenario(
        id="cron-crond-add-0002",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="single",
        user_input="create /etc/cron.d/healthcheck to run a monitoring script every minute",
        notes="WRITE: deploy a frequently-running health check via cron.d.",
    ),
    Scenario(
        id="cron-crond-add-0003",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="multi",
        user_input="install the backup-jobs cron.d file and then confirm it exists in /etc/cron.d/",
        notes="Multi-step: add the drop-in then verify it is present.",
    ),
    Scenario(
        id="cron-crond-add-0004",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="single",
        user_input="deploy a cron.d entry for daily certificate renewal with certbot",
        notes="WRITE: create a system-wide Let's Encrypt renewal cron job.",
    ),
    Scenario(
        id="cron-crond-add-0005",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="diagnostic",
        user_input="the cleanup job was accidentally removed — re-create the /etc/cron.d/cleanup drop-in",
        notes="Diagnostic-triggered WRITE: restore a missing cron.d file.",
    ),
    Scenario(
        id="cron-crond-add-0006",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="single",
        user_input="write a /etc/cron.d/db-vacuum file to run vacuumdb weekly on Sundays",
        notes="WRITE: add a system-wide database maintenance cron job.",
    ),
    Scenario(
        id="cron-crond-add-0007",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="multi",
        user_input="create the metrics-collect cron.d entry and verify the schedule is correct",
        notes="Multi-step: install cron.d drop-in then view it to confirm contents.",
    ),
    Scenario(
        id="cron-crond-add-0008",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="single",
        user_input="add a /etc/cron.d/disk-check file to alert on disk usage every 30 minutes",
        notes="WRITE: create a frequent disk-space monitoring cron job.",
    ),
    Scenario(
        id="cron-crond-add-0009",
        tool="cron",
        operation="crond-add",
        permission_class=_pc("crond-add"),
        complexity="diagnostic",
        user_input="log rotation stopped working because the cron.d file is missing — re-install it",
        notes="Diagnostic-triggered WRITE: restore a deleted logrotate cron.d entry.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("cron").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "cron", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("cron").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
