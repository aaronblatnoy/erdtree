"""finetune/simulate/mariadb.py — Rocky Linux 9 output simulator for the 'mariadb' tool.

Public API
----------
simulate_mariadb(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 5 real operations declared in core/tools/mariadb.py
           (status, query, dump, grant, drop_database)
    args : dict of op arguments (may be sparse; defaults applied per-op)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Checked via isinstance; both forms are supported.

Realism model
-------------
* Exit codes mirror real mysqladmin/mysql/mysqldump behaviour on Rocky Linux 9:
    0  — success
    1  — generic operation failure
    2  — mysqladmin: server not reachable / connection refused
  127  — command not found (binary missing)
* stdout/stderr reflect actual Rocky 9 MariaDB CLI output format.
* Failure triggers are deterministic: database/host names containing "notfound",
  "missing", "broken", "fail", "noexist", or "bogus" trigger failure cases.
  A hash-based ~15% scatter adds variety among otherwise valid-looking names.

I2 compliance
-------------
All summary strings are I2-clean (no AI/LLM/model/agent/agentic/neural/
language model).

INV-read-only-core: imports NOTHING from core/ directly.
Does not import finetune.coreimports (avoids circular deps when __init__
imports simulators before coreimports is fully settled). The 4-key dict
mirrors ToolResult with no class dependency.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for realistic output lines."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "db-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "db-host"


def _db_not_found(name: str) -> bool:
    """Deterministically decide if a database/host name should trigger an error."""
    lower = name.lower()
    for tok in ("notfound", "noexist", "broken", "fail", "missing", "bogus"):
        if tok in lower:
            return True
    # Hash-based deterministic scatter (~15%)
    h = int(hashlib.md5(name.encode()).hexdigest(), 16)
    return h % 20 == 0


def _make_result(
    exit_code: int,
    stdout: str,
    stderr: str,
    summary: str,
) -> dict[str, Any]:
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# Per-operation simulators
# ---------------------------------------------------------------------------

def _sim_status(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    host = args.get("host", "localhost")

    if _db_not_found(host):
        stderr = (
            f"mysqladmin: connect to server at '{host}' failed\n"
            f"error: 'Can't connect to MySQL server on '{host}' (111 Connection refused)'\n"
            f"Check that mysqld is running on {host} and that the port is accessible.\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Could not connect to MariaDB server at '{host}' — connection refused.",
        )

    stdout = (
        f"Uptime: 86423  Threads: 3  Questions: 18472  Slow queries: 0  "
        f"Opens: 28  Flush tables: 1  Open tables: 21  "
        f"Queries per second avg: 0.213\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"MariaDB server at '{host}' is reachable and returned status.",
    )


def _sim_query(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    sql = args.get("sql", "SELECT 1")
    database = args.get("database", "")
    host = args.get("host", "localhost")

    # Connection failure check
    if _db_not_found(host):
        stderr = (
            f"ERROR 2003 (HY000): Can't connect to MySQL server on '{host}' (111)\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"SQL statement could not be executed — MariaDB connection to '{host}' failed.",
        )

    # Database not found check
    if database and _db_not_found(database):
        stderr = f"ERROR 1049 (42000): Unknown database '{database}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"SQL statement failed — database '{database}' does not exist (exit 1).",
        )

    # Simulate plausible SELECT output
    sql_upper = sql.strip().upper()
    if sql_upper.startswith("SELECT VERSION"):
        stdout = "VERSION()\n10.5.22-MariaDB\n"
    elif sql_upper.startswith("SHOW DATABASES"):
        stdout = (
            "Database\ninformation_schema\nmysql\nperformance_schema\n"
        )
        if database:
            stdout += f"{database}\n"
    elif sql_upper.startswith("SHOW TABLES"):
        db_label = database or "selected_db"
        stdout = f"Tables_in_{db_label}\nusers\norders\nproducts\n"
    elif sql_upper.startswith("SELECT 1"):
        stdout = "1\n1\n"
    elif sql_upper.startswith("SHOW STATUS"):
        stdout = (
            "Variable_name\tValue\n"
            "Uptime\t86423\n"
            "Threads_connected\t3\n"
            "Questions\t18472\n"
        )
    else:
        stdout = ""

    db_label = f" on database '{database}'" if database else ""
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"SQL statement executed successfully{db_label}.",
    )


def _sim_dump(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    database = args.get("database", "mydb")
    host = args.get("host", "localhost")

    if _db_not_found(database) or _db_not_found(host):
        stderr = (
            f"mysqldump: Got error: 1049: Unknown database '{database}' "
            f"when selecting the database\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Dump of database '{database}' failed — database not found (exit 2).",
        )

    stdout = (
        f"-- MariaDB dump 10.19  Distrib 10.5.22-MariaDB, for Linux (x86_64)\n"
        f"--\n"
        f"-- Host: {host}    Database: {database}\n"
        f"-- ------------------------------------------------------\n"
        f"-- Server version\t10.5.22-MariaDB\n"
        f"\n"
        f"/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;\n"
        f"/*!40101 SET NAMES utf8 */;\n"
        f"\n"
        f"-- Table structure for table `users`\n"
        f"\n"
        f"DROP TABLE IF EXISTS `users`;\n"
        f"CREATE TABLE `users` (\n"
        f"  `id` int(11) NOT NULL AUTO_INCREMENT,\n"
        f"  `username` varchar(64) NOT NULL,\n"
        f"  `email` varchar(128) DEFAULT NULL,\n"
        f"  PRIMARY KEY (`id`)\n"
        f") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;\n"
        f"\n"
        f"-- Dump completed on 2026-07-04  8:00:00\n"
    )
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Database '{database}' dumped successfully.",
    )


def _sim_grant(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    user = args.get("user", "appuser")
    database = args.get("database", "appdb")
    privileges = args.get("privileges", "ALL PRIVILEGES")
    host = args.get("host", "localhost")
    user_host = args.get("user_host", "localhost")

    if _db_not_found(database):
        stderr = f"ERROR 1049 (42000): Unknown database '{database}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to grant privileges on '{database}' to '{user}'@'{user_host}' "
                f"— database not found (exit 1)."
            ),
        )

    if _db_not_found(user):
        stderr = f"ERROR 1396 (HY000): Operation GRANT failed for '{user}'@'{user_host}'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=(
                f"Failed to grant privileges on '{database}' to '{user}'@'{user_host}' "
                f"(exit 1)."
            ),
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Granted '{privileges}' on '{database}' to user '{user}'@'{user_host}'.",
    )


def _sim_drop_database(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    database = args.get("database", "olddb")
    host = args.get("host", "localhost")

    if _db_not_found(host):
        stderr = (
            f"mysqladmin: connect to server at '{host}' failed\n"
            f"error: 'Can't connect to MySQL server on '{host}' (111 Connection refused)'\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Failed to drop database '{database}' — could not connect to '{host}' (exit 2).",
        )

    # Check if database exists — simulate a "not found" failure on bad names
    # (distinct from host failure: use a separate hash seed)
    h = int(hashlib.md5((database + "_drop").encode()).hexdigest(), 16)
    if _db_not_found(database):
        stderr = f"mysqladmin: drop database failed; error: 'Can't drop database '{database}'; database doesn't exist'\n"
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to drop database '{database}' — database does not exist (exit 1).",
        )

    stdout = f"Dropping the database is potentially a very bad thing to do.\nAny data stored in the database will be destroyed.\n\nDo you really want to drop the '{database}' database [y/N] Dropping database...\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Database '{database}' dropped permanently.",
    )


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status":        _sim_status,
    "query":         _sim_query,
    "dump":          _sim_dump,
    "grant":         _sim_grant,
    "drop_database": _sim_drop_database,
}


def simulate_mariadb(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Simulate a 'mariadb' tool call and return a ToolResult-shaped dict.

    Parameters
    ----------
    op   : operation name; must be one of the 5 real ops declared in the
           mariadb ToolSpec (status, query, dump, grant, drop_database).
    args : argument dict (may be sparse; defaults are applied per-op).
    ctx  : system context — either the snapshot_text str from make_context(),
           or a profile dict.

    Returns
    -------
    dict with keys: exit_code (int), stdout (str), stderr (str), summary (str).
    All four keys are always present. summary is I2-clean.

    Raises
    ------
    KeyError  if op is not a recognised operation name.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_mariadb: unknown operation '{op}'. "
            f"Valid ops: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
