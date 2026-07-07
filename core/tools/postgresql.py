"""core/tools/postgresql.py — PostgreSQL database management via psql/createdb/dropdb CLI.

Supported operations
--------------------
  status     (READ)        — show PostgreSQL service status via systemctl.
  query      (READ, advisory) — run a user-supplied SQL statement via psql -c.
  createdb   (WRITE)       — create a new database via the createdb binary.
  createuser (WRITE)       — create a new database role via the createuser binary.
  pg_dump    (WRITE)       — dump a database to a file via pg_dump.
  dropdb     (DESTRUCTIVE) — permanently drop a database via the dropdb binary.

SQL-GATING NOTE (load-bearing):
  The `query` op carries user-supplied SQL that this module does NOT inspect.
  The OpSpec.permission_class is READ (advisory) because the expected use is
  SELECT-style reads. However, the AUTHORITATIVE gate is permissions.classify()
  over the rendered `psql -c "<SQL>"` argv, which Phase 1 makes SQL-aware:
  DROP/TRUNCATE/DELETE/ALTER escalate to DESTRUCTIVE; any doubt escalates to WRITE.
  This module NEVER parses or guards SQL (I3 — classifying is the caller's job).
  Do not add SQL-parsing logic here.

Design rules (load-bearing invariants):
  I1  No network. Every effect goes through run_subprocess against a LOCAL
      binary; this module imports NO socket-opening library.
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
    """systemctl status postgresql — show the PostgreSQL service state."""
    result = run_subprocess(["systemctl", "status", "--no-pager", "postgresql"])
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = "PostgreSQL service is active and running."
    else:
        summary = f"PostgreSQL service reported status exit {result.exit_code}."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_query(args: dict[str, Any]) -> ToolResult:
    """psql -c <sql> — run a SQL statement.

    Advisory permission class is READ (expected use: SELECT queries).
    The authoritative gate is permissions.classify() over the argv — Phase 1
    escalates DROP/TRUNCATE/DELETE/ALTER to DESTRUCTIVE and biases to WRITE on
    any doubt. This tool never inspects the SQL body (I3).
    """
    sql: str = args["sql"]
    database: str = args.get("database", "postgres") or "postgres"
    username: str = args.get("username", "postgres") or "postgres"
    cmd = ["psql", "-U", username, "-d", database, "-c", sql]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Query executed successfully against database '{database}'."
    else:
        summary = f"Query failed against database '{database}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_createdb(args: dict[str, Any]) -> ToolResult:
    """createdb <dbname> — create a new PostgreSQL database."""
    dbname: str = args["dbname"]
    username: str = args.get("username", "postgres") or "postgres"
    cmd = ["createdb", "-U", username, dbname]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Database '{dbname}' created successfully."
    else:
        summary = f"Failed to create database '{dbname}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_createuser(args: dict[str, Any]) -> ToolResult:
    """createuser <rolename> — create a new PostgreSQL role."""
    rolename: str = args["rolename"]
    username: str = args.get("username", "postgres") or "postgres"
    cmd = ["createuser", "-U", username, rolename]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Role '{rolename}' created successfully."
    else:
        summary = f"Failed to create role '{rolename}' (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_pg_dump(args: dict[str, Any]) -> ToolResult:
    """pg_dump -f <output_file> <dbname> — dump a PostgreSQL database to a file."""
    dbname: str = args["dbname"]
    output_file: str = args["output_file"]
    username: str = args.get("username", "postgres") or "postgres"
    cmd = ["pg_dump", "-U", username, "-f", output_file, dbname]
    result = run_subprocess(cmd, timeout=300)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Database '{dbname}' dumped to '{output_file}'."
    else:
        summary = f"Dump of database '{dbname}' failed (exit {result.exit_code})."
    return ToolResult(
        exit_code=result.exit_code,
        stdout=result.stdout,
        stderr=result.stderr,
        summary=summary + selinux,
    )


def _op_dropdb(args: dict[str, Any]) -> ToolResult:
    """dropdb <dbname> — permanently drop a PostgreSQL database.

    DESTRUCTIVE: this operation is irreversible. The database and all its data
    are permanently deleted. The authoritative safety gate is permissions.classify()
    over the rendered `dropdb <dbname>` argv; Phase 1 must ensure this escalates
    to DESTRUCTIVE (currently [UNKNOWN]).
    """
    dbname: str = args["dbname"]
    username: str = args.get("username", "postgres") or "postgres"
    cmd = ["dropdb", "-U", username, dbname]
    result = run_subprocess(cmd)
    selinux = _maybe_selinux_hint(result.stderr)
    if result.ok:
        summary = f"Database '{dbname}' has been permanently dropped."
    else:
        summary = f"Failed to drop database '{dbname}' (exit {result.exit_code})."
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
    "status":     _op_status,
    "query":      _op_query,
    "createdb":   _op_createdb,
    "createuser": _op_createuser,
    "pg_dump":    _op_pg_dump,
    "dropdb":     _op_dropdb,
}


# ---------------------------------------------------------------------------
# Tool execute()
# ---------------------------------------------------------------------------

def _execute(op: str, args: dict[str, Any]) -> ToolResult:
    """Execute a postgresql operation and return a structured ToolResult.

    The caller is responsible for:
      1. Resolving the permission gate via permissions.classify().
      2. Writing the audit record via audit.AuditLog.write().

    This function runs the subprocess, constructs a ToolResult, and returns.
    It never raises (I9): unknown ops, missing binaries (exit 127), and timeouts
    all degrade to a well-formed ToolResult.
    """
    handler = _DISPATCH.get(op)
    if handler is None:
        return ToolResult(
            exit_code=1,
            stdout="",
            stderr="",
            summary=f"Unknown operation '{op}' for postgresql tool.",
        )
    return handler(args)


# ---------------------------------------------------------------------------
# ToolSpec declaration
# ---------------------------------------------------------------------------

_DBNAME_ARG = ArgSpec(
    name="dbname",
    type=str,
    required=True,
    description="The name of the PostgreSQL database.",
)

_USERNAME_ARG = ArgSpec(
    name="username",
    type=str,
    required=False,
    description="The PostgreSQL superuser to connect as (default: 'postgres').",
    default="postgres",
)

POSTGRESQL_SPEC = ToolSpec(
    name="postgresql",
    description="Manage PostgreSQL databases via the psql, createdb, createuser, pg_dump, and dropdb CLI tools.",
    ops={
        "status": OpSpec(
            op_name="status",
            permission_class=OpClass.READ,
            args=[],
            description="Show the current status of the PostgreSQL service.",
        ),
        "query": OpSpec(
            op_name="query",
            permission_class=OpClass.READ,
            args=[
                ArgSpec(
                    name="sql",
                    type=str,
                    required=True,
                    description=(
                        "The SQL statement to execute via psql -c. "
                        "Advisory class is READ (intended for SELECT queries). "
                        "The authoritative gate inspects the SQL argv for "
                        "DROP/TRUNCATE/DELETE/ALTER and escalates accordingly."
                    ),
                ),
                ArgSpec(
                    name="database",
                    type=str,
                    required=False,
                    description="Target database name (default: 'postgres').",
                    default="postgres",
                ),
                _USERNAME_ARG,
            ],
            description=(
                "Run a SQL statement via psql -c. "
                "Expected use is read-only queries (SELECT/SHOW/EXPLAIN). "
                "The advisory class is READ; the permission classifier is the "
                "authoritative gate for destructive SQL."
            ),
        ),
        "createdb": OpSpec(
            op_name="createdb",
            permission_class=OpClass.WRITE,
            args=[_DBNAME_ARG, _USERNAME_ARG],
            description="Create a new PostgreSQL database.",
        ),
        "createuser": OpSpec(
            op_name="createuser",
            permission_class=OpClass.WRITE,
            args=[
                ArgSpec(
                    name="rolename",
                    type=str,
                    required=True,
                    description="The name of the new PostgreSQL role to create.",
                ),
                _USERNAME_ARG,
            ],
            description="Create a new PostgreSQL role.",
        ),
        "pg_dump": OpSpec(
            op_name="pg_dump",
            permission_class=OpClass.WRITE,
            args=[
                _DBNAME_ARG,
                ArgSpec(
                    name="output_file",
                    type=str,
                    required=True,
                    description="Destination file path for the database dump.",
                ),
                _USERNAME_ARG,
            ],
            description="Dump a PostgreSQL database to a file via pg_dump.",
        ),
        "dropdb": OpSpec(
            op_name="dropdb",
            permission_class=OpClass.DESTRUCTIVE,
            args=[_DBNAME_ARG, _USERNAME_ARG],
            description=(
                "Permanently drop a PostgreSQL database. "
                "DESTRUCTIVE: all data in the database is irreversibly deleted."
            ),
        ),
    },
    execute=_execute,
)

# ---------------------------------------------------------------------------
# Self-registration into the module-level registry singleton
# ---------------------------------------------------------------------------

registry.register(POSTGRESQL_SPEC)
