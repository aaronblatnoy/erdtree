"""finetune/scenarios_v3/postgresql.py — corpus v3 multi-turn scenarios for 'postgresql'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="postgresql-v3-0001", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Create a database called analytics_v2.", tool="postgresql", operation="createdb",
             args={"operation": "createdb", "dbname": "analytics_v2"}),
        Turn(user_input="Now the same for analytics_v2_staging.", tool="postgresql", operation="createdb",
             args={"operation": "createdb", "dbname": "analytics_v2_staging"}),
    )),
    V3(id="postgresql-v3-0002", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Create a role called svc_reporting.", tool="postgresql", operation="createuser",
             args={"operation": "createuser", "rolename": "svc_reporting"}),
        Turn(user_input="Ok, now run a query to grant it SELECT on the sales schema.", tool="postgresql", operation="query",
             args={"operation": "query", "sql": "GRANT SELECT ON ALL TABLES IN SCHEMA sales TO svc_reporting"}),
    )),
    V3(id="postgresql-v3-0003", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Run SELECT pg_size_pretty(pg_database_size('warehouse')) against warehouse.", tool="postgresql", operation="query",
             args={"operation": "query", "sql": "SELECT pg_size_pretty(pg_database_size('warehouse'))", "database": "warehouse"}),
        Turn(user_input="Yes, go ahead and dump that database to /backups/warehouse.sql.", tool="postgresql", operation="pg_dump",
             args={"operation": "pg_dump", "dbname": "warehouse", "output_file": "/backups/warehouse.sql"}),
    )),
    V3(id="postgresql-v3-0004", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Create user svc_migrate connecting as the migrate_admin superuser.", tool="postgresql", operation="createuser",
             args={"operation": "createuser", "rolename": "svc_migrate", "username": "migrate_admin"}),
        Turn(user_input="Undo that, we're routing through the shared service account instead.", tool="postgresql", operation="query",
             args={"operation": "query", "sql": "SELECT rolname FROM pg_roles WHERE rolname = 'svc_migrate'", "username": "migrate_admin"}),
    )),
    V3(id="postgresql-v3-0005", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Check PostgreSQL status.", tool="postgresql", operation="status",
             args={"operation": "status"}),
        Turn(user_input="Instead connect as the readonly user and rerun that same check.", tool="postgresql", operation="query",
             args={"operation": "query", "sql": "SELECT 1", "username": "readonly"}),
    )),
    V3(id="postgresql-v3-0006", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Drop the scratch_import database, it was only for the one-off load.", tool="postgresql", operation="dropdb",
             args={"operation": "dropdb", "dbname": "scratch_import"}),
        Turn(user_input="Confirm, do it.", tool="postgresql", operation="dropdb",
             args={"operation": "dropdb", "dbname": "scratch_import"}),
    )),
    V3(id="postgresql-v3-0007", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Dump the crm database to /backups/crm_pre_migrate.sql.", tool="postgresql", operation="pg_dump",
             args={"operation": "pg_dump", "dbname": "crm", "output_file": "/backups/crm_pre_migrate.sql"}),
        Turn(user_input="Also check disk usage on that backups volume, I want headroom confirmed.", tool="disk", operation="usage",
             args={"operation": "usage"}),
    )),
    V3(id="postgresql-v3-0008", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Create database events_2026 as the app_admin user.", tool="postgresql", operation="createdb",
             args={"operation": "createdb", "dbname": "events_2026", "username": "app_admin"}),
        Turn(user_input="And events_2026_archive too, same account.", tool="postgresql", operation="createdb",
             args={"operation": "createdb", "dbname": "events_2026_archive", "username": "app_admin"}),
    )),
    V3(id="postgresql-v3-0009", tool="postgresql", kind="followup", turns=(
        Turn(user_input="Check status on the postgres service.", tool="postgresql", operation="status",
             args={"operation": "status"}),
        Turn(user_input="Also run SELECT count(*) FROM pg_stat_activity against the metrics database.", tool="postgresql", operation="query",
             args={"operation": "query", "sql": "SELECT count(*) FROM pg_stat_activity", "database": "metrics"}),
        Turn(user_input="Also dump metrics to /backups/metrics.sql before we touch anything.", tool="postgresql", operation="pg_dump",
             args={"operation": "pg_dump", "dbname": "metrics", "output_file": "/backups/metrics.sql"}),
    )),
    V3(id="postgresql-v3-0010", tool="postgresql", kind="question", turns=(
        Turn(user_input="Check PostgreSQL status.", tool="postgresql", operation="status",
             args={"operation": "status"}),
        Turn(user_input="what does that status output tell me",
             answer="It reports whether the postgres service is accepting connections right now, not query load.\nIf it shows down, connections will be refused until the service is restarted."),
    )),
    V3(id="postgresql-v3-0011", tool="postgresql", kind="question", turns=(
        Turn(user_input="Run DELETE FROM sessions WHERE expires_at < now() against the auth database.", tool="postgresql", operation="query",
             args={"operation": "query", "sql": "DELETE FROM sessions WHERE expires_at < now()", "database": "auth"}),
        Turn(user_input="why did that get flagged as destructive when query is a read op",
             answer="The query operation's class is only advisory; the gate parses the actual SQL text before allowing it.\nDELETE, DROP, TRUNCATE, and ALTER trigger the destructive path no matter which operation submitted them."),
    )),
    V3(id="postgresql-v3-0012", tool="postgresql", kind="question", turns=(
        Turn(user_input="Create a role called svc_backup.", tool="postgresql", operation="createuser",
             args={"operation": "createuser", "rolename": "svc_backup"}),
        Turn(user_input="what privileges does that role have by default",
             answer="A freshly created role has no privileges beyond connecting — no table access, no database ownership, no login by default depending on flags.\nGrant it explicit permissions with a follow-up GRANT before anything depends on it."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("postgresql", SCENARIOS_V3)
