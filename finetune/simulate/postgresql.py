"""finetune/simulate/postgresql.py — Rocky Linux 9 output simulator for the 'postgresql' tool.

Public API
----------
simulate_postgresql(op, args, ctx) -> dict
    Returns a dict with exactly four keys mirroring core.tools.ToolResult:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (MUST be I2-clean — no forbidden terms)

    op   : one of the 6 real operations declared in core/tools/postgresql.py
    args : dict of op arguments (may be {} for ops with all-optional args)
    ctx  : system context string produced by make_context(), OR a profile dict.
           Both forms are supported via isinstance checks.

Realism model
-------------
* Simulates output from psql, createdb, createuser, pg_dump, dropdb, and
  systemctl status postgresql as seen on Rocky Linux 9.
* Exit codes mirror real PostgreSQL CLI behaviour:
    0  — success
    1  — general error (binary not found, connection refused, permission denied)
    2  — psql fatal error (invalid SQL, database does not exist)
* Failure triggers are deterministic: a database/role name containing
  "notfound", "noexist", "broken", "fail", or "missing" triggers an error.
  A hash-based ~15% scatter adds variety among otherwise valid names.

I2 compliance
-------------
All `summary` strings are I2-clean. No AI/LLM/model/agent language.

INV-read-only-core: this module imports NOTHING from core/ directly.
It does not import finetune.coreimports either (avoids circular deps).
The ToolResult shape is mirrored as a plain dict — no class dependency needed.
"""

from __future__ import annotations

import hashlib
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hostname(ctx: Any) -> str:
    """Extract hostname from ctx for use in realistic output."""
    if isinstance(ctx, dict):
        return ctx.get("hostname", "rocky-host.example.com").split(".")[0]
    if isinstance(ctx, str):
        for line in ctx.splitlines():
            if line.lower().startswith("hostname:"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    return parts[1].strip().split(".")[0]
    return "rocky-host"


def _pg_is_running(ctx: Any) -> bool:
    """Return True if postgresql appears to be running in the context."""
    if isinstance(ctx, dict):
        active: list[str] = ctx.get("active_services", [])
        return any("postgresql" in s for s in active)
    if isinstance(ctx, str):
        return "postgresql" in ctx.lower()
    return False


def _name_is_bad(name: str) -> bool:
    """Deterministically decide if a name triggers an error response."""
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
    host = _hostname(ctx)
    running = _pg_is_running(ctx)

    if running:
        stdout = (
            f"● postgresql.service - PostgreSQL Database Server\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/postgresql.service; enabled; preset: disabled)\n"
            f"     Active: active (running) since Mon 2026-07-06 00:01:04 UTC; 6h 22min ago\n"
            f"   Main PID: 1423 (postmaster)\n"
            f"      Tasks: 8 (limit: 23168)\n"
            f"     Memory: 92.4M\n"
            f"        CPU: 2.341s\n"
            f"     CGroup: /system.slice/postgresql.service\n"
            f"             └─1423 /usr/bin/postmaster -D /var/lib/pgsql/data\n"
            f"\n"
            f"Jul 06 00:01:04 {host} systemd[1]: Started PostgreSQL Database Server.\n"
        )
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary="PostgreSQL service is active and running.",
        )
    else:
        stdout = (
            f"○ postgresql.service - PostgreSQL Database Server\n"
            f"     Loaded: loaded (/usr/lib/systemd/system/postgresql.service; disabled; preset: disabled)\n"
            f"     Active: inactive (dead)\n"
        )
        return _make_result(
            exit_code=3,
            stdout=stdout,
            stderr="",
            summary="PostgreSQL service is loaded but currently inactive.",
        )


def _sim_query(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    sql: str = args.get("sql", "SELECT 1")
    database: str = args.get("database", "postgres") or "postgres"
    username: str = args.get("username", "postgres") or "postgres"

    # Connection failure if PostgreSQL is not running
    if not _pg_is_running(ctx):
        stderr = (
            f"psql: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" "
            f"failed: No such file or directory\n"
            f"\tIs the server running locally and accepting connections on that socket?\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Connection to database '{database}' failed — the PostgreSQL service may not be running (exit 2).",
        )

    if _name_is_bad(database):
        stderr = (
            f"psql: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" "
            f"failed: FATAL:  database \"{database}\" does not exist\n"
        )
        return _make_result(
            exit_code=2,
            stdout="",
            stderr=stderr,
            summary=f"Query failed — database '{database}' does not exist (exit 2).",
        )

    # Simulate a basic SELECT output
    sql_lower = sql.strip().lower()
    if sql_lower.startswith("select"):
        if "version()" in sql_lower:
            stdout = (
                f"                                                 version\n"
                f"---------------------------------------------------------------------------------------------------------\n"
                f" PostgreSQL 15.3 on x86_64-redhat-linux-gnu, compiled by gcc (GCC) 11.4.1 20230605 (Red Hat 11.4.1-2), 64-bit\n"
                f"(1 row)\n\n"
            )
        elif "count" in sql_lower:
            stdout = " count\n-------\n    42\n(1 row)\n\n"
        else:
            stdout = " ?column?\n----------\n        1\n(1 row)\n\n"
        return _make_result(
            exit_code=0,
            stdout=stdout,
            stderr="",
            summary=f"Query executed successfully against database '{database}'.",
        )

    # Non-SELECT: still simulate success for show/explain
    stdout = " (0 rows)\n\n" if "select" not in sql_lower else " ?column?\n----------\n 1\n(1 row)\n\n"
    return _make_result(
        exit_code=0,
        stdout=stdout,
        stderr="",
        summary=f"Query executed successfully against database '{database}'.",
    )


def _sim_createdb(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    dbname: str = args.get("dbname", "newdb")
    username: str = args.get("username", "postgres") or "postgres"

    if not _pg_is_running(ctx):
        stderr = (
            f"createdb: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" "
            f"failed: No such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create database '{dbname}' — PostgreSQL service may not be running (exit 1).",
        )

    if _name_is_bad(dbname):
        stderr = (
            f"createdb: error: database creation failed: ERROR:  database \"{dbname}\" already exists\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create database '{dbname}' (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Database '{dbname}' created successfully.",
    )


def _sim_createuser(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    rolename: str = args.get("rolename", "newrole")
    username: str = args.get("username", "postgres") or "postgres"

    if not _pg_is_running(ctx):
        stderr = (
            f"createuser: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" "
            f"failed: No such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create role '{rolename}' — PostgreSQL service may not be running (exit 1).",
        )

    if _name_is_bad(rolename):
        stderr = (
            f"createuser: error: creation of new role failed: ERROR:  role \"{rolename}\" already exists\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to create role '{rolename}' (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Role '{rolename}' created successfully.",
    )


def _sim_pg_dump(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    dbname: str = args.get("dbname", "mydb")
    output_file: str = args.get("output_file", "/tmp/dump.sql")
    username: str = args.get("username", "postgres") or "postgres"

    if not _pg_is_running(ctx):
        stderr = (
            f"pg_dump: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" "
            f"failed: No such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Dump of database '{dbname}' failed — PostgreSQL service may not be running (exit 1).",
        )

    if _name_is_bad(dbname):
        stderr = (
            f"pg_dump: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" "
            f"failed: FATAL:  database \"{dbname}\" does not exist\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Dump of database '{dbname}' failed — database does not exist (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Database '{dbname}' dumped to '{output_file}'.",
    )


def _sim_dropdb(args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    dbname: str = args.get("dbname", "olddb")
    username: str = args.get("username", "postgres") or "postgres"

    if not _pg_is_running(ctx):
        stderr = (
            f"dropdb: error: connection to server on socket \"/var/run/postgresql/.s.PGSQL.5432\" "
            f"failed: No such file or directory\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to drop database '{dbname}' — PostgreSQL service may not be running (exit 1).",
        )

    if _name_is_bad(dbname):
        stderr = (
            f"dropdb: error: database removal failed: ERROR:  database \"{dbname}\" does not exist\n"
        )
        return _make_result(
            exit_code=1,
            stdout="",
            stderr=stderr,
            summary=f"Failed to drop database '{dbname}' — database does not exist (exit 1).",
        )

    return _make_result(
        exit_code=0,
        stdout="",
        stderr="",
        summary=f"Database '{dbname}' has been permanently dropped.",
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH = {
    "status":     _sim_status,
    "query":      _sim_query,
    "createdb":   _sim_createdb,
    "createuser": _sim_createuser,
    "pg_dump":    _sim_pg_dump,
    "dropdb":     _sim_dropdb,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def simulate_postgresql(op: str, args: dict[str, Any], ctx: Any) -> dict[str, Any]:
    """Return a simulated ToolResult dict for a postgresql operation.

    Parameters
    ----------
    op   : one of the real ops declared in core/tools/postgresql.py
    args : op arg dict (may be {} for ops with all-optional args; defaults applied per-op)
    ctx  : system-context str from make_context(), OR a profile dict — support
           BOTH via isinstance (see _pg_is_running/_hostname).

    Returns a dict with exactly these four keys:
        exit_code : int
        stdout    : str
        stderr    : str
        summary   : str   (I2-clean)

    Raises KeyError on an unknown op (Phase-13 completeness assert relies on this).
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        raise KeyError(
            f"simulate_postgresql: unknown operation '{op}'. "
            f"Valid: {sorted(_DISPATCH)}"
        )
    return handler(args, ctx)
