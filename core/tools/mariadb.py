"""core/tools/mariadb.py — MariaDB database management via mysqladmin and mysql CLI.

Supported operations
--------------------
  status        (READ)        — show MariaDB server status via mysqladmin.
  query         (READ/WRITE)  — run a SQL statement via mysql -e.
  dump          (WRITE)       — dump a database to stdout via mysqldump.
  grant         (WRITE)       — grant privileges to a database user.
  drop_database (DESTRUCTIVE) — drop a database permanently via mysqladmin drop.

SQL-GATING NOTE (advisory vs authoritative):
  The 'query' op is a user-supplied SQL wrapper. The OpSpec.permission_class is
  READ (for SELECT/SHOW/EXPLAIN class queries) as advisory documentation only.
  The AUTHORITATIVE gate is permissions.classify() over the rendered
  'mysql -e "<sql>"' argv — which is SQL-aware (Phase 1 escalates
  DROP/TRUNCATE/DELETE/ALTER to DESTRUCTIVE; biases to WRITE on any doubt).
  This tool does NOT inspect or parse the SQL body (I3: tools never classify).

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library (no mysql.connector,
      no PyMySQL, no requests).
  I2  No AI/LLM/model/agent language in any user-facing string.
  I3  The caller resolves the permission gate BEFORE execute(); this module
      never calls permissions.classify().
  I4  The caller writes the audit record; this module writes none.
  I6  Zero tier/product/model names anywhere in this file.
  I9  execute() NEVER raises: every failure degrades to a well-formed ToolResult.
"""

from __future__ import annotations

import re
from typing import Any

from core.agent.permissions import OpClass
from core.tools import (
    ArgSpec,
    OpSpec,
    ToolResult,
    ToolSpec,
    registry,
    run_subprocess,
)

# ---------------------------------------------------------------------------
# SELinux hint detection (copy VERBATIM from services.py)
# ---------------------------------------------------------------------------

_SELINUX_HINT_RE = re.compile(
    r"AVC\s+avc:|Permission\s+denied|dontaudit|type=AVC|selinux",
    re.IGNORECASE,
)

_SELINUX_HINT = (
    "SELinux may be blocking this operation — check 'ausearch -m avc -ts recent' "
    "or 'journalctl -t setroubleshoot' for denial details."
)


def _maybe_selinux_hint(stderr: str) -> str:
    """Return a SELinux hint suffix if stderr looks like an AVC denial."""
    if _SELINUX_HINT_RE.search(stderr):
        return f"  {_SELINUX_HINT}"
    return ""


# ---------------------------------------------------------------------------
# Individual operation implementations
# ---------------------------------------------------------------------------

def _op_status(args: dict[str, Any]) -> ToolResult:
    """mysqladmin status — show server uptime, threads, queries, etc."""
    host: str = args.get("host", "localhost")
    cmd = ["mysqladmin", "--host", host, "status"]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"MariaDB server at '{host}' is reachable and returned status."
    else:
        summary = f"MariaDB status check for '{host}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_query(args: dict[str, Any]) -> ToolResult:
    """mysql -e '<sql>' [database] — execute a SQL statement.

    Advisory permission_class is READ, but the authoritative gate is
    permissions.classify() over the rendered argv. DROP/TRUNCATE/DELETE/ALTER
    inside the -e argument will be escalated to DESTRUCTIVE by the Phase-1
    classifier. This tool does not parse SQL (I3).
    """
    sql: str = args["sql"]
    database: str = args.get("database", "")
    host: str = args.get("host", "localhost")
    cmd = ["mysql", "--host", host, "-e", sql]
    if database:
        cmd.append(database)
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    db_label = f" on database '{database}'" if database else ""
    if result.ok:
        summary = f"SQL statement executed successfully{db_label}."
    else:
        summary = f"SQL statement failed{db_label} (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_dump(args: dict[str, Any]) -> ToolResult:
    """mysqldump <database> — dump database schema and data to stdout."""
    database: str = args["database"]
    host: str = args.get("host", "localhost")
    cmd = ["mysqldump", "--host", host, database]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Database '{database}' dumped successfully."
    else:
        summary = f"Dump of database '{database}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_grant(args: dict[str, Any]) -> ToolResult:
    """mysql -e 'GRANT <privs> ON <db>.* TO <user>@<host>' — grant privileges."""
    user: str = args["user"]
    database: str = args["database"]
    privileges: str = args.get("privileges", "ALL PRIVILEGES")
    host: str = args.get("host", "localhost")
    user_host: str = args.get("user_host", "localhost")
    sql = f"GRANT {privileges} ON {database}.* TO '{user}'@'{user_host}'; FLUSH PRIVILEGES;"
    cmd = ["mysql", "--host", host, "-e", sql]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Granted '{privileges}' on '{database}' to user '{user}'@'{user_host}'."
    else:
        summary = (
            f"Failed to grant privileges on '{database}' to '{user}'@'{user_host}' "
            f"(exit {result.exit_code})."
        )
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_drop_database(args: dict[str, Any]) -> ToolResult:
    """mysqladmin drop <database> — permanently drop a database (DESTRUCTIVE).

    This operation is irreversible. The database and all its tables are deleted.
    The argv shape 'mysqladmin drop <db>' is the literal destructive form that
    permissions.classify() must escalate to DESTRUCTIVE (Phase 1, [UNKNOWN]).
    """
    database: str = args["database"]
    host: str = args.get("host", "localhost")
    # Pass --force so mysqladmin does not prompt interactively (caller already confirmed).
    cmd = ["mysqladmin", "--host", host, "--force", "drop", database]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Database '{database}' dropped permanently."
    else:
        summary = f"Failed to drop database '{database}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict[str, Any] = {
    "status":        _op_status,
    "query":         _op_query,
    "dump":          _op_dump,
    "grant":         _op_grant,
    "drop_database": _op_drop_database,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Dispatch a mariadb operation and return a structured ToolResult.

    I9: Never raises — unknown ops and all subprocess failures degrade to a
    well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for mariadb tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_HOST_ARG = ArgSpec(
    name="host",
    type=str,
    required=False,
    description="MariaDB server hostname or IP (default: localhost).",
    default="localhost",
)

_DATABASE_ARG = ArgSpec(
    name="database",
    type=str,
    required=True,
    description="Name of the MariaDB database.",
)

MARIADB_SPEC = ToolSpec(
    name="mariadb",
    description="Manage MariaDB databases via mysqladmin, mysql, and mysqldump.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[_HOST_ARG],
            description="Show MariaDB server status (uptime, threads, queries).",
        ),
        "query": OpSpec(
            op_name="query",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="sql",
                    type=str,
                    required=True,
                    description="SQL statement to execute (e.g. 'SELECT VERSION()').",
                ),
                ArgSpec(
                    name="database",
                    type=str,
                    required=False,
                    description="Database context to run the query against.",
                    default="",
                ),
                _HOST_ARG,
            ],
            description=(
                "Execute a SQL statement via mysql -e. Advisory class READ; "
                "the authoritative gate inspects the SQL payload — "
                "DROP/TRUNCATE/DELETE/ALTER escalate to DESTRUCTIVE."
            ),
        ),
        "dump": OpSpec(
            op_name="dump",
            permission_class=OpClass.WRITE,
            args=[_DATABASE_ARG, _HOST_ARG],
            description="Dump a database to stdout via mysqldump.",
        ),
        "grant": OpSpec(
            op_name="grant",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="user",
                    type=str,
                    required=True,
                    description="MariaDB username to grant privileges to.",
                ),
                _DATABASE_ARG,
                ArgSpec(
                    name="privileges",
                    type=str,
                    required=False,
                    description="Privileges to grant (default: ALL PRIVILEGES).",
                    default="ALL PRIVILEGES",
                ),
                _HOST_ARG,
                ArgSpec(
                    name="user_host",
                    type=str,
                    required=False,
                    description="Host part of the user account (default: localhost).",
                    default="localhost",
                ),
            ],
            description="Grant database privileges to a MariaDB user.",
        ),
        "drop_database": OpSpec(
            op_name="drop_database",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_DATABASE_ARG, _HOST_ARG],
            description=(
                "Permanently drop a database and all its tables (DESTRUCTIVE — "
                "irreversible data loss)."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(MARIADB_SPEC)
