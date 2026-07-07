"""finetune/scenarios/postgresql.py — Scenario corpus for the 'postgresql' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status     READ        — show PostgreSQL service status via systemctl
  query      READ        — run a user-supplied SQL statement via psql -c
                           (advisory READ; authoritative gate inspects SQL argv)
  createdb   WRITE       — create a new database via createdb
  createuser WRITE       — create a new database role via createuser
  pg_dump    WRITE       — dump a database to a file via pg_dump
  dropdb     DESTRUCTIVE — permanently drop a database via dropdb

Coverage targets
----------------
  >= 40 entries total across all 6 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach the
  explicit-confirmation gate for data-loss operations.

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
# Scenario dataclass — local definition per slice convention
# Compatible field names are EXACT so Phase-13 JOIN can unify without renames.
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
    """Return the live permission class for a postgresql operation."""
    return registry.get("postgresql").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 8 entries
    # =========================================================================

    Scenario(
        id="postgresql-status-0001",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is postgresql running?",
        notes="Basic health check on the PostgreSQL service unit.",
    ),
    Scenario(
        id="postgresql-status-0002",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check the status of the database server",
        notes="User wants a quick glance at whether the DB is up.",
    ),
    Scenario(
        id="postgresql-status-0003",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="show me postgresql service info including uptime and PID",
        notes="Diagnostic — wants systemctl status output with cgroup/PID details.",
    ),
    Scenario(
        id="postgresql-status-0004",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is postgres up on this machine?",
        notes="Colloquial phrasing; maps to status op.",
    ),
    Scenario(
        id="postgresql-status-0005",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="why is the database server not accepting connections?",
        notes="Diagnostic — user suspects service is down; check status first.",
    ),
    Scenario(
        id="postgresql-status-0006",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check if postgresql.service is active",
        notes="Explicit unit-name form.",
    ),
    Scenario(
        id="postgresql-status-0007",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check postgresql status and then show me who is connected",
        notes="Multi-step — status is first step before querying pg_stat_activity.",
    ),
    Scenario(
        id="postgresql-status-0008",
        tool="postgresql",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="postgres keeps crashing — show me its current state",
        notes="User reports instability; status reveals failed/inactive state.",
    ),

    # =========================================================================
    # query  (READ advisory) — 10 entries
    # =========================================================================

    Scenario(
        id="postgresql-query-0001",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="show me the postgresql version",
        notes="Simple SELECT version() read query.",
    ),
    Scenario(
        id="postgresql-query-0002",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="list all databases in postgres",
        notes="SELECT datname FROM pg_database — read-only catalog query.",
    ),
    Scenario(
        id="postgresql-query-0003",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="count the rows in the orders table in the shop database",
        notes="SELECT COUNT(*) — read-only aggregate.",
    ),
    Scenario(
        id="postgresql-query-0004",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="diagnostic",
        user_input="show me all active connections to the sales database",
        notes="SELECT from pg_stat_activity — diagnostic read.",
    ),
    Scenario(
        id="postgresql-query-0005",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="what tables are in the inventory database?",
        notes="SELECT tablename FROM pg_tables — schema read.",
    ),
    Scenario(
        id="postgresql-query-0006",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="diagnostic",
        user_input="check for any long-running queries in postgres",
        notes="SELECT from pg_stat_activity WHERE duration > threshold — diagnostic.",
    ),
    Scenario(
        id="postgresql-query-0007",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="show disk usage for each database",
        notes="SELECT pg_database_size() — read-only size query.",
    ),
    Scenario(
        id="postgresql-query-0008",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="list all roles in postgresql",
        notes="SELECT rolname FROM pg_roles — catalog read.",
    ),
    Scenario(
        id="postgresql-query-0009",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="multi",
        user_input="show me the 10 largest tables in the appdb database",
        notes="Multi-step diagnostic: query pg_relation_size then sort — still read.",
    ),
    Scenario(
        id="postgresql-query-0010",
        tool="postgresql",
        operation="query",
        permission_class=_pc("query"),
        complexity="diagnostic",
        user_input="are there any bloated tables in the reporting database?",
        notes="Query pg_stat_user_tables for n_dead_tup — diagnostic read.",
    ),

    # =========================================================================
    # createdb  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="postgresql-createdb-0001",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="single",
        user_input="create a new database called appdb",
        notes="Simple single-database creation.",
    ),
    Scenario(
        id="postgresql-createdb-0002",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="single",
        user_input="set up a database named inventory for our warehouse app",
        notes="Named database with domain context.",
    ),
    Scenario(
        id="postgresql-createdb-0003",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="multi",
        user_input="create a staging database and a production database for the shop app",
        notes="Multi-step: two createdb calls in sequence.",
    ),
    Scenario(
        id="postgresql-createdb-0004",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="single",
        user_input="make a test database called testdb",
        notes="Developer workflow — test environment setup.",
    ),
    Scenario(
        id="postgresql-createdb-0005",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="multi",
        user_input="create a new database for the analytics team and give them access",
        notes="Multi-step: createdb then createuser/grant.",
    ),
    Scenario(
        id="postgresql-createdb-0006",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="single",
        user_input="initialize a database called hr_data",
        notes="HR system database provisioning.",
    ),
    Scenario(
        id="postgresql-createdb-0007",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="diagnostic",
        user_input="the createdb command failed — can you try creating the orders_db database again?",
        notes="Retry after failure; diagnostic context (prior error).",
    ),
    Scenario(
        id="postgresql-createdb-0008",
        tool="postgresql",
        operation="createdb",
        permission_class=_pc("createdb"),
        complexity="single",
        user_input="create a database named metrics",
        notes="Monitoring/metrics database setup.",
    ),

    # =========================================================================
    # createuser  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="postgresql-createuser-0001",
        tool="postgresql",
        operation="createuser",
        permission_class=_pc("createuser"),
        complexity="single",
        user_input="create a postgresql user called appuser",
        notes="Application service account creation.",
    ),
    Scenario(
        id="postgresql-createuser-0002",
        tool="postgresql",
        operation="createuser",
        permission_class=_pc("createuser"),
        complexity="single",
        user_input="add a readonly role named reporter to postgres",
        notes="Read-only analytics role.",
    ),
    Scenario(
        id="postgresql-createuser-0003",
        tool="postgresql",
        operation="createuser",
        permission_class=_pc("createuser"),
        complexity="multi",
        user_input="create a new database user for the billing service and set up their permissions",
        notes="Multi-step: createuser then grant on database.",
    ),
    Scenario(
        id="postgresql-createuser-0004",
        tool="postgresql",
        operation="createuser",
        permission_class=_pc("createuser"),
        complexity="single",
        user_input="add a role called etl_runner to the database",
        notes="ETL pipeline service account.",
    ),
    Scenario(
        id="postgresql-createuser-0005",
        tool="postgresql",
        operation="createuser",
        permission_class=_pc("createuser"),
        complexity="single",
        user_input="create a postgres login role named backupuser",
        notes="Backup-specific role with login privilege.",
    ),
    Scenario(
        id="postgresql-createuser-0006",
        tool="postgresql",
        operation="createuser",
        permission_class=_pc("createuser"),
        complexity="diagnostic",
        user_input="the app cannot connect — create a new role called webapp and grant it access to the appdb",
        notes="Diagnostic-driven createuser to fix connection issues.",
    ),
    Scenario(
        id="postgresql-createuser-0007",
        tool="postgresql",
        operation="createuser",
        permission_class=_pc("createuser"),
        complexity="single",
        user_input="add a database account for the monitoring system",
        notes="Monitoring role for metrics collection.",
    ),

    # =========================================================================
    # pg_dump  (WRITE) — 7 entries
    # =========================================================================

    Scenario(
        id="postgresql-pg_dump-0001",
        tool="postgresql",
        operation="pg_dump",
        permission_class=_pc("pg_dump"),
        complexity="single",
        user_input="dump the appdb database to /backup/appdb.sql",
        notes="Simple backup to a file.",
    ),
    Scenario(
        id="postgresql-pg_dump-0002",
        tool="postgresql",
        operation="pg_dump",
        permission_class=_pc("pg_dump"),
        complexity="single",
        user_input="back up the inventory database before the upgrade",
        notes="Pre-upgrade safety dump.",
    ),
    Scenario(
        id="postgresql-pg_dump-0003",
        tool="postgresql",
        operation="pg_dump",
        permission_class=_pc("pg_dump"),
        complexity="multi",
        user_input="back up all three application databases to /var/backup/pg/",
        notes="Multi-step: three pg_dump calls for appdb, orderdb, reportdb.",
    ),
    Scenario(
        id="postgresql-pg_dump-0004",
        tool="postgresql",
        operation="pg_dump",
        permission_class=_pc("pg_dump"),
        complexity="diagnostic",
        user_input="the last dump failed — retry backing up the sales database to /tmp/sales.sql",
        notes="Retry scenario after a prior pg_dump failure.",
    ),
    Scenario(
        id="postgresql-pg_dump-0005",
        tool="postgresql",
        operation="pg_dump",
        permission_class=_pc("pg_dump"),
        complexity="single",
        user_input="export the production database to /mnt/nfs/backups/prod_20260706.sql",
        notes="NFS-backed backup of production database.",
    ),
    Scenario(
        id="postgresql-pg_dump-0006",
        tool="postgresql",
        operation="pg_dump",
        permission_class=_pc("pg_dump"),
        complexity="multi",
        user_input="dump the hr_data database and then move it to the backup server",
        notes="Multi-step: pg_dump then scp/rsync transfer.",
    ),
    Scenario(
        id="postgresql-pg_dump-0007",
        tool="postgresql",
        operation="pg_dump",
        permission_class=_pc("pg_dump"),
        complexity="single",
        user_input="create a snapshot of the metrics database",
        notes="Snapshot phrasing; maps to pg_dump.",
    ),

    # =========================================================================
    # dropdb  (DESTRUCTIVE) — 8 entries
    # =========================================================================

    Scenario(
        id="postgresql-dropdb-0001",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="single",
        user_input="drop the testdb database — I no longer need it",
        notes="Clean-up of a test database; DESTRUCTIVE requires confirmation.",
    ),
    Scenario(
        id="postgresql-dropdb-0002",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="single",
        user_input="delete the old_archive database from postgres",
        notes="Removing an obsolete archive DB permanently.",
    ),
    Scenario(
        id="postgresql-dropdb-0003",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="multi",
        user_input="dump the legacy_db database first and then drop it",
        notes="Multi-step safe pattern: pg_dump then dropdb.",
    ),
    Scenario(
        id="postgresql-dropdb-0004",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="single",
        user_input="remove the staging_db — decommissioning the staging environment",
        notes="Decommission workflow; DESTRUCTIVE gating is critical here.",
    ),
    Scenario(
        id="postgresql-dropdb-0005",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="diagnostic",
        user_input="the dev database is corrupt and unrecoverable — drop it so we can recreate it",
        notes="Recovery scenario: drop corrupted DB before recreating.",
    ),
    Scenario(
        id="postgresql-dropdb-0006",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="single",
        user_input="permanently delete the temp_data database",
        notes="Explicit permanent deletion — user knows it is irreversible.",
    ),
    Scenario(
        id="postgresql-dropdb-0007",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="multi",
        user_input="back up analytics_db to /backup/analytics.sql and then drop it",
        notes="Safe multi-step: backup first then drop.",
    ),
    Scenario(
        id="postgresql-dropdb-0008",
        tool="postgresql",
        operation="dropdb",
        permission_class=_pc("dropdb"),
        complexity="diagnostic",
        user_input="why does dropdb fail with 'database does not exist'?",
        notes="Diagnostic — user troubleshooting a failed dropdb attempt.",
    ),

]


# ---------------------------------------------------------------------------
# Import-time sanity checks (mirrors services.py pattern)
# ---------------------------------------------------------------------------

_spec = registry.get("postgresql")
assert _spec is not None, "postgresql tool not registered — import core.tools.postgresql first"

for _s in SCENARIOS:
    assert _s.tool == "postgresql", f"Scenario {_s.id} has wrong tool: {_s.tool!r}"
    assert _s.operation in _spec.ops, (
        f"Scenario {_s.id} references unknown op {_s.operation!r}; "
        f"valid ops: {set(_spec.ops)}"
    )
    _live_pc = _spec.permission_class_for(_s.operation)
    assert _s.permission_class == _live_pc, (
        f"Scenario {_s.id}: permission_class mismatch "
        f"(scenario={_s.permission_class}, registry={_live_pc})"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario IDs detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
