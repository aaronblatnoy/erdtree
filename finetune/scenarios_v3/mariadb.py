"""finetune/scenarios_v3/mariadb.py — corpus v3 multi-turn scenarios for 'mariadb'."""
from finetune.scenarios_v3 import V3, Turn

SCENARIOS_V3 = [
    V3(id="mariadb-v3-0001", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Check MariaDB status on db-primary-01.", tool="mariadb", operation="status",
             args={"operation": "status", "host": "db-primary-01"}),
        Turn(user_input="Now the same for db-replica-04.", tool="mariadb", operation="status",
             args={"operation": "status", "host": "db-replica-04"}),
    )),
    V3(id="mariadb-v3-0002", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Dump the orders database to a file for the migration.", tool="mariadb", operation="dump",
             args={"operation": "dump", "database": "orders"}),
        Turn(user_input="Also grant readonly access on that same database to the reporting user.", tool="mariadb", operation="grant",
             args={"operation": "grant", "user": "reporting", "database": "orders", "privileges": "SELECT"}),
    )),
    V3(id="mariadb-v3-0003", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Run SELECT COUNT(*) FROM sessions against the auth database.", tool="mariadb", operation="query",
             args={"operation": "query", "sql": "SELECT COUNT(*) FROM sessions", "database": "auth"}),
        Turn(user_input="Yes, go ahead and grant the app_svc user full privileges on that database too.", tool="mariadb", operation="grant",
             args={"operation": "grant", "user": "app_svc", "database": "auth", "privileges": "ALL PRIVILEGES"}),
    )),
    V3(id="mariadb-v3-0004", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Grant SELECT on catalog to the etl user on host 10.2.4.5.", tool="mariadb", operation="grant",
             args={"operation": "grant", "user": "etl", "database": "catalog", "privileges": "SELECT", "host": "10.2.4.5"}),
        Turn(user_input="Undo that, we ended up not needing the etl account yet.", tool="mariadb", operation="query",
             args={"operation": "query", "sql": "SHOW GRANTS FOR 'etl'@'localhost'", "host": "10.2.4.5"}),
    )),
    V3(id="mariadb-v3-0005", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Check status on the staging database server.", tool="mariadb", operation="status",
             args={"operation": "status", "host": "staging-db"}),
        Turn(user_input="No, use prod-db instead, wrong host.", tool="mariadb", operation="status",
             args={"operation": "status", "host": "prod-db"}),
    )),
    V3(id="mariadb-v3-0006", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Drop the scratch_temp database, it's leftover from testing.", tool="mariadb", operation="drop_database",
             args={"operation": "drop_database", "database": "scratch_temp"}),
        Turn(user_input="Confirm, do it.", tool="mariadb", operation="drop_database",
             args={"operation": "drop_database", "database": "scratch_temp"}),
    )),
    V3(id="mariadb-v3-0007", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Dump the inventory database before we touch anything.", tool="mariadb", operation="dump",
             args={"operation": "dump", "database": "inventory"}),
        Turn(user_input="Also check the disk space on that host, I want to make sure the dump had room to land.", tool="disk", operation="usage",
             args={"operation": "usage"}),
    )),
    V3(id="mariadb-v3-0008", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Grant ALL PRIVILEGES on billing to the finance_ro user.", tool="mariadb", operation="grant",
             args={"operation": "grant", "user": "finance_ro", "database": "billing", "privileges": "ALL PRIVILEGES"}),
        Turn(user_input="Actually no, use SELECT only instead, that's too broad.", tool="mariadb", operation="grant",
             args={"operation": "grant", "user": "finance_ro", "database": "billing", "privileges": "SELECT"}),
    )),
    V3(id="mariadb-v3-0009", tool="mariadb", kind="followup", turns=(
        Turn(user_input="Check status on db02.", tool="mariadb", operation="status",
             args={"operation": "status", "host": "db02"}),
        Turn(user_input="Run SHOW PROCESSLIST against it, I want to see what's active.", tool="mariadb", operation="query",
             args={"operation": "query", "sql": "SHOW PROCESSLIST", "host": "db02"}),
        Turn(user_input="Also dump the sessions database from that same host.", tool="mariadb", operation="dump",
             args={"operation": "dump", "database": "sessions", "host": "db02"}),
    )),
    V3(id="mariadb-v3-0010", tool="mariadb", kind="question", turns=(
        Turn(user_input="Check status on db-primary-01.", tool="mariadb", operation="status",
             args={"operation": "status", "host": "db-primary-01"}),
        Turn(user_input="what does that thread count mean",
             answer="It's the number of client connections currently open on the server, not the number of active queries.\nA high connected count with low running usually means idle connections piling up, not overload."),
    )),
    V3(id="mariadb-v3-0011", tool="mariadb", kind="question", turns=(
        Turn(user_input="Run DELETE FROM sessions WHERE expired = 1 against the auth database.", tool="mariadb", operation="query",
             args={"operation": "query", "sql": "DELETE FROM sessions WHERE expired = 1", "database": "auth"}),
        Turn(user_input="why did that get flagged as destructive",
             answer="The query classifier inspects the SQL text itself, not just the advisory read class on the query operation.\nDELETE, DROP, TRUNCATE, and ALTER statements escalate to destructive regardless of which operation ran them."),
    )),
    V3(id="mariadb-v3-0012", tool="mariadb", kind="question", turns=(
        Turn(user_input="Dump the catalog database.", tool="mariadb", operation="dump",
             args={"operation": "dump", "database": "catalog"}),
        Turn(user_input="what does that dump actually contain",
             answer="It's the full schema and data for catalog as SQL statements, suitable for restoring with mysql < dumpfile.\nIt does not include the mysql grants table, so user permissions have to be recreated separately."),
    )),
]

from finetune.scenarios_v3 import check_module; check_module("mariadb", SCENARIOS_V3)
