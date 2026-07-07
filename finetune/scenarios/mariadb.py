"""finetune/scenarios/mariadb.py — Scenario corpus for the 'mariadb' tool.

Operations and their permission classes (derived LIVE from the registry at
import time — never hardcoded, per INV-schema-sync):

  status        READ        — show MariaDB server status via mysqladmin
  query         READ        — execute a SQL statement via mysql -e (advisory;
                              authoritative gate inspects the SQL payload)
  dump          WRITE       — dump a database to stdout via mysqldump
  grant         WRITE       — grant privileges to a database user
  drop_database DESTRUCTIVE — permanently drop a database (irreversible)

Coverage targets
----------------
  >= 40 entries total across all 5 operations.
  All three complexities represented: single | multi | diagnostic.
  DESTRUCTIVE scenarios are honestly labeled so downstream traces teach the
  destructive-confirmation gate.

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
    """Return the live permission class for a mariadb operation."""
    return registry.get("mariadb").permission_class_for(op)


# ---------------------------------------------------------------------------
# Scenario entries
# ---------------------------------------------------------------------------

SCENARIOS: list[Scenario] = [

    # =========================================================================
    # status  (READ) — 9 entries
    # =========================================================================

    Scenario(
        id="mariadb-status-0001",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="is MariaDB running?",
        notes="Simple health check via mysqladmin status.",
    ),
    Scenario(
        id="mariadb-status-0002",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="show me the MariaDB server status",
        notes="Basic server status — uptime, threads, query count.",
    ),
    Scenario(
        id="mariadb-status-0003",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="check if the database server is up on db1.internal",
        notes="Status check on a named remote host.",
    ),
    Scenario(
        id="mariadb-status-0004",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="the web app is timing out on database queries — is MariaDB even reachable?",
        notes="Diagnostic entry point: verify server reachability before deeper investigation.",
    ),
    Scenario(
        id="mariadb-status-0005",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check the MariaDB status and tell me how many threads are connected",
        notes="Multi-step: status then parse thread count from output.",
    ),
    Scenario(
        id="mariadb-status-0006",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="how long has the database server been running?",
        notes="Uptime check via mysqladmin status output.",
    ),
    Scenario(
        id="mariadb-status-0007",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="diagnostic",
        user_input="we're getting connection errors — check the MariaDB server status on 10.0.1.20",
        notes="Diagnostic: connection errors prompt a status check on the DB host.",
    ),
    Scenario(
        id="mariadb-status-0008",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="single",
        user_input="verify the database server is healthy before the deployment",
        notes="Pre-deployment health check gate.",
    ),
    Scenario(
        id="mariadb-status-0009",
        tool="mariadb",
        operation="status",
        permission_class=_pc("status"),
        complexity="multi",
        user_input="check MariaDB status and then show me the slow query count",
        notes="Multi-step: status then interpret slow query metric.",
    ),

    # =========================================================================
    # query  (READ — advisory) — 12 entries
    # =========================================================================

    Scenario(
        id="mariadb-query-0001",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="what version of MariaDB is running?",
        notes="SELECT VERSION() — a simple read query.",
    ),
    Scenario(
        id="mariadb-query-0002",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="list all databases on the server",
        notes="SHOW DATABASES — read-only inspection.",
    ),
    Scenario(
        id="mariadb-query-0003",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="show me the tables in the myapp database",
        notes="SHOW TABLES — inspect a specific database.",
    ),
    Scenario(
        id="mariadb-query-0004",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="diagnostic",
        user_input="how many rows are in the orders table in the store database?",
        notes="Diagnostic SELECT COUNT(*) — read query to gauge table size.",
    ),
    Scenario(
        id="mariadb-query-0005",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="show me the current connections to MariaDB",
        notes="SHOW STATUS LIKE 'Threads_connected' — read query.",
    ),
    Scenario(
        id="mariadb-query-0006",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="check the global variables for max_connections",
        notes="SHOW VARIABLES LIKE 'max_connections' — read-only config check.",
    ),
    Scenario(
        id="mariadb-query-0007",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="diagnostic",
        user_input="show me all running queries on the database server",
        notes="SHOW PROCESSLIST — diagnostic read to find long-running queries.",
    ),
    Scenario(
        id="mariadb-query-0008",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="multi",
        user_input="list all users that have access to the reporting database",
        notes="Multi-step: SHOW GRANTS / SELECT on mysql.user — read inspection.",
    ),
    Scenario(
        id="mariadb-query-0009",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="describe the schema of the users table in the auth database",
        notes="DESCRIBE users — read-only schema inspection.",
    ),
    Scenario(
        id="mariadb-query-0010",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="diagnostic",
        user_input="the login page is broken — check if the sessions table exists in the webapp database",
        notes="Diagnostic: read check to confirm table existence before assuming code bug.",
    ),
    Scenario(
        id="mariadb-query-0011",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="single",
        user_input="show the InnoDB engine status",
        notes="SHOW ENGINE INNODB STATUS — read-only storage engine diagnostics.",
    ),
    Scenario(
        id="mariadb-query-0012",
        tool="mariadb",
        operation="query",
        permission_class=_pc("query"),
        complexity="multi",
        user_input="check the binary log status and list current binary log files",
        notes="SHOW MASTER STATUS then SHOW BINARY LOGS — replication read checks.",
    ),

    # =========================================================================
    # dump  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="mariadb-dump-0001",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="single",
        user_input="dump the myapp database so I can back it up",
        notes="WRITE: mysqldump of a named database.",
    ),
    Scenario(
        id="mariadb-dump-0002",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="single",
        user_input="take a backup of the wordpress database",
        notes="WRITE: pre-maintenance backup of a CMS database.",
    ),
    Scenario(
        id="mariadb-dump-0003",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="multi",
        user_input="dump the production orders database before the migration starts",
        notes="Multi-step: dump as a pre-migration safety backup.",
    ),
    Scenario(
        id="mariadb-dump-0004",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="single",
        user_input="export the auth database from the db.internal host",
        notes="WRITE: dump from a named remote host.",
    ),
    Scenario(
        id="mariadb-dump-0005",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="diagnostic",
        user_input="something corrupted the sessions table — dump the webapp database so we have a snapshot",
        notes="Diagnostic-triggered WRITE: dump for data-recovery baseline.",
    ),
    Scenario(
        id="mariadb-dump-0006",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="single",
        user_input="create a database export for the reporting database",
        notes="WRITE: scheduled export of a reporting database.",
    ),
    Scenario(
        id="mariadb-dump-0007",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="multi",
        user_input="dump the inventory database and confirm the file is non-empty",
        notes="Multi-step: dump then verify output size.",
    ),
    Scenario(
        id="mariadb-dump-0008",
        tool="mariadb",
        operation="dump",
        permission_class=_pc("dump"),
        complexity="single",
        user_input="make a copy of the legacy database before decommissioning",
        notes="WRITE: pre-decommission backup dump.",
    ),

    # =========================================================================
    # grant  (WRITE) — 8 entries
    # =========================================================================

    Scenario(
        id="mariadb-grant-0001",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="single",
        user_input="give the appuser account full access to the myapp database",
        notes="WRITE: grant ALL PRIVILEGES to an application user.",
    ),
    Scenario(
        id="mariadb-grant-0002",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="single",
        user_input="grant SELECT and INSERT permissions on the reporting database to the analyst user",
        notes="WRITE: restricted privilege grant for a read-heavy analytics user.",
    ),
    Scenario(
        id="mariadb-grant-0003",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="single",
        user_input="set up the backup user with SELECT rights on all databases",
        notes="WRITE: grant for a backup service account.",
    ),
    Scenario(
        id="mariadb-grant-0004",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="multi",
        user_input="create the deploy user and grant it all privileges on the webapp database",
        notes="Multi-step: create user then grant — deployment account setup.",
    ),
    Scenario(
        id="mariadb-grant-0005",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="single",
        user_input="grant the monitoring user SELECT access to the mysql system database",
        notes="WRITE: grant for a monitoring tool's read-only account.",
    ),
    Scenario(
        id="mariadb-grant-0006",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="diagnostic",
        user_input="the API is getting access denied errors — check and re-grant SELECT on the store database to apiuser",
        notes="Diagnostic-triggered WRITE: re-grant after permissions issue.",
    ),
    Scenario(
        id="mariadb-grant-0007",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="single",
        user_input="give the replication user REPLICATION SLAVE privileges on all databases",
        notes="WRITE: replication user privilege setup.",
    ),
    Scenario(
        id="mariadb-grant-0008",
        tool="mariadb",
        operation="grant",
        permission_class=_pc("grant"),
        complexity="multi",
        user_input="grant the developer account all privileges on the dev database and then verify the grants",
        notes="Multi-step: grant then SHOW GRANTS to confirm.",
    ),

    # =========================================================================
    # drop_database  (DESTRUCTIVE) — 9 entries
    # =========================================================================

    Scenario(
        id="mariadb-drop_database-0001",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="single",
        user_input="drop the old_legacy database — it is no longer needed",
        notes="DESTRUCTIVE: drop a database that has been decommissioned.",
    ),
    Scenario(
        id="mariadb-drop_database-0002",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="single",
        user_input="delete the test_db database from the server",
        notes="DESTRUCTIVE: remove a test database after testing is complete.",
    ),
    Scenario(
        id="mariadb-drop_database-0003",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="multi",
        user_input="we are migrating off the old CMS — dump the cms_db first and then drop it",
        notes="Multi-step: dump then drop — migration cleanup with safety backup first.",
    ),
    Scenario(
        id="mariadb-drop_database-0004",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="single",
        user_input="permanently remove the staging_data database",
        notes="DESTRUCTIVE: drop a staging environment database.",
    ),
    Scenario(
        id="mariadb-drop_database-0005",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="diagnostic",
        user_input="the old inventory system is fully decommissioned — drop the inventory_v1 database",
        notes="Diagnostic-triggered DESTRUCTIVE: clean up after verified decommission.",
    ),
    Scenario(
        id="mariadb-drop_database-0006",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="single",
        user_input="drop the scratch_db database on the dev server",
        notes="DESTRUCTIVE: clean up a temporary scratch database.",
    ),
    Scenario(
        id="mariadb-drop_database-0007",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="multi",
        user_input="verify the archive_2024 database has been backed up then drop it",
        notes="Multi-step: confirm backup exists then proceed with destructive drop.",
    ),
    Scenario(
        id="mariadb-drop_database-0008",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="single",
        user_input="remove the experimental_db — the experiment is over",
        notes="DESTRUCTIVE: drop an experimental database after project closure.",
    ),
    Scenario(
        id="mariadb-drop_database-0009",
        tool="mariadb",
        operation="drop_database",
        permission_class=_pc("drop_database"),
        complexity="diagnostic",
        user_input="the disk is almost full — identify large unused databases and drop the old_reports one",
        notes="Diagnostic-triggered DESTRUCTIVE: disk pressure prompts dropping an unused database.",
    ),
]

# ---------------------------------------------------------------------------
# Sanity check at import time
# ---------------------------------------------------------------------------

_REAL_OPS: frozenset[str] = frozenset(registry.get("mariadb").ops.keys())

for _s in SCENARIOS:
    assert _s.tool == "mariadb", f"Wrong tool on {_s.id}: {_s.tool!r}"
    assert _s.operation in _REAL_OPS, (
        f"{_s.id}: operation {_s.operation!r} not in live registry ops {_REAL_OPS}"
    )
    assert _s.permission_class == registry.get("mariadb").permission_class_for(_s.operation), (
        f"{_s.id}: permission_class mismatch for op {_s.operation!r}"
    )

_ids = [_s.id for _s in SCENARIOS]
assert len(_ids) == len(set(_ids)), "Duplicate scenario ids detected"
assert len(SCENARIOS) >= 40, f"Need >= 40 scenarios, got {len(SCENARIOS)}"
