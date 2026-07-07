"""tests/test_tools_mariadb.py — Unit tests for core/tools/mariadb.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without mysqladmin, mysql, or mysqldump present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/query are READ; dump/grant are WRITE;
    drop_database is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary with exit code.
  * Command vectors: the exact argv list passed to run_subprocess is verified
    for each operation (including the '--force drop' shape for drop_database).
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2 compliance: no AI/LLM/model/agent/agentic/neural/language model in any
    summary string.
  * I9: execute() never raises — unknown ops and exit-127 (missing binary)
    both return a well-formed ToolResult.
  * ToolResult structure: all four fields present; as_dict() returns exactly
    {exit_code, stdout, stderr, summary}.
  * DEFERRED-TO-MOSSAD: live execution against real MariaDB on Rocky Linux 9.

Mocking strategy
----------------
  Patch ``core.tools.mariadb.run_subprocess`` (the name in the mariadb
  module's namespace, where the ``from core.tools import run_subprocess``
  binding lives) — NOT the root ``core.tools.run_subprocess``.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.mariadb  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.mariadb import MARIADB_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Patch core.tools.mariadb.run_subprocess with a fixed return value."""
    return patch("core.tools.mariadb.run_subprocess", return_value=return_value)


def _patch_run_mock():
    """Patch core.tools.mariadb.run_subprocess with a MagicMock."""
    return patch("core.tools.mariadb.run_subprocess")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_mariadb_registered(self) -> None:
        assert registry.get("mariadb") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("mariadb")
        assert spec is not None
        assert spec.name == "mariadb"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("mariadb")
        assert spec is not None
        expected = {"status", "query", "dump", "grant", "drop_database"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "query"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("mariadb", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["dump", "grant"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("mariadb", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_drop_database_is_destructive(self) -> None:
        cls = registry.permission_class_for("mariadb", "drop_database")
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for 'drop_database', got {cls}"

    def test_spec_drop_database_is_destructive(self) -> None:
        cls = MARIADB_SPEC.permission_class_for("drop_database")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv passed to run_subprocess for each operation."""

    def test_status_default_host(self) -> None:
        mock = MagicMock(return_value=_ok())
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("status", {})
        argv = mock.call_args[0][0]
        assert argv == ["mysqladmin", "--host", "localhost", "status"]

    def test_status_custom_host(self) -> None:
        mock = MagicMock(return_value=_ok())
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("status", {"host": "db.internal"})
        argv = mock.call_args[0][0]
        assert argv == ["mysqladmin", "--host", "db.internal", "status"]

    def test_query_no_database(self) -> None:
        mock = MagicMock(return_value=_ok(stdout="10.5.22-MariaDB\n"))
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("query", {"sql": "SELECT VERSION()"})
        argv = mock.call_args[0][0]
        assert argv == ["mysql", "--host", "localhost", "-e", "SELECT VERSION()"]

    def test_query_with_database(self) -> None:
        mock = MagicMock(return_value=_ok(stdout="col\nval\n"))
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("query", {"sql": "SELECT 1", "database": "mydb"})
        argv = mock.call_args[0][0]
        assert argv == ["mysql", "--host", "localhost", "-e", "SELECT 1", "mydb"]

    def test_dump_argv(self) -> None:
        mock = MagicMock(return_value=_ok(stdout="-- MariaDB dump\n"))
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("dump", {"database": "myapp"})
        argv = mock.call_args[0][0]
        assert argv == ["mysqldump", "--host", "localhost", "myapp"]

    def test_dump_custom_host(self) -> None:
        mock = MagicMock(return_value=_ok(stdout="-- MariaDB dump\n"))
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("dump", {"database": "myapp", "host": "db2.internal"})
        argv = mock.call_args[0][0]
        assert argv == ["mysqldump", "--host", "db2.internal", "myapp"]

    def test_grant_argv(self) -> None:
        mock = MagicMock(return_value=_ok())
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("grant", {"user": "appuser", "database": "appdb"})
        argv = mock.call_args[0][0]
        assert argv[0] == "mysql"
        assert "--host" in argv
        assert "-e" in argv
        # The SQL argument should contain GRANT, the database, and FLUSH PRIVILEGES
        e_idx = argv.index("-e")
        sql_arg = argv[e_idx + 1]
        assert "GRANT" in sql_arg
        assert "appdb" in sql_arg
        assert "appuser" in sql_arg
        assert "FLUSH PRIVILEGES" in sql_arg

    def test_drop_database_argv(self) -> None:
        """drop_database must use mysqladmin --force drop <db> shape."""
        mock = MagicMock(return_value=_ok(stdout="Dropping database...\n"))
        with patch("core.tools.mariadb.run_subprocess", mock):
            _execute("drop_database", {"database": "olddb"})
        argv = mock.call_args[0][0]
        assert argv[0] == "mysqladmin"
        assert "--force" in argv
        assert "drop" in argv
        assert "olddb" in argv
        # Verify the 'drop <db>' shape is in the correct positional relationship
        drop_idx = argv.index("drop")
        assert argv[drop_idx + 1] == "olddb"


# ---------------------------------------------------------------------------
# Exit-code mapping
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_status_success(self) -> None:
        with _patch_run(_ok(stdout="Uptime: 86423  Threads: 3\n")):
            result = _execute("status", {})
        assert result.ok
        assert "reachable" in result.summary.lower() or "status" in result.summary.lower()

    def test_status_failure(self) -> None:
        with _patch_run(_fail(exit_code=2, stderr="Connection refused")):
            result = _execute("status", {"host": "badhost"})
        assert not result.ok
        assert result.exit_code == 2
        assert "badhost" in result.summary

    def test_query_success(self) -> None:
        with _patch_run(_ok(stdout="VERSION()\n10.5.22-MariaDB\n")):
            result = _execute("query", {"sql": "SELECT VERSION()"})
        assert result.ok
        assert "executed" in result.summary.lower()

    def test_query_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="ERROR 1049: Unknown database")):
            result = _execute("query", {"sql": "SELECT 1", "database": "ghost_db"})
        assert not result.ok
        assert "ghost_db" in result.summary
        assert "1" in result.summary  # exit code

    def test_dump_success(self) -> None:
        with _patch_run(_ok(stdout="-- MariaDB dump\n")):
            result = _execute("dump", {"database": "myapp"})
        assert result.ok
        assert "myapp" in result.summary
        assert "dumped" in result.summary.lower()

    def test_dump_failure(self) -> None:
        with _patch_run(_fail(exit_code=2, stderr="Unknown database 'ghostdb'")):
            result = _execute("dump", {"database": "ghostdb"})
        assert not result.ok
        assert "ghostdb" in result.summary

    def test_grant_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("grant", {"user": "bob", "database": "myapp"})
        assert result.ok
        assert "bob" in result.summary
        assert "myapp" in result.summary

    def test_grant_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="ERROR 1396: Operation GRANT failed")):
            result = _execute("grant", {"user": "nouser", "database": "myapp"})
        assert not result.ok
        assert "nouser" in result.summary or "myapp" in result.summary

    def test_drop_database_success(self) -> None:
        with _patch_run(_ok(stdout="Dropping database...\n")):
            result = _execute("drop_database", {"database": "olddb"})
        assert result.ok
        assert "olddb" in result.summary
        assert "dropped" in result.summary.lower()

    def test_drop_database_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="Can't drop database 'ghostdb'; doesn't exist")):
            result = _execute("drop_database", {"database": "ghostdb"})
        assert not result.ok
        assert "ghostdb" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("query",         {"sql": "SELECT 1"}),
        ("dump",          {"database": "mydb"}),
        ("grant",         {"user": "u", "database": "d"}),
        ("drop_database", {"database": "olddb"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("query",         {"sql": "SELECT 1"}),
        ("dump",          {"database": "mydb"}),
        ("grant",         {"user": "u", "database": "d"}),
        ("drop_database", {"database": "olddb"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I2 — no AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("query",         {"sql": "SELECT 1"}),
        ("dump",          {"database": "mydb"}),
        ("grant",         {"user": "u", "database": "d"}),
        ("drop_database", {"database": "olddb"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("status",        {"host": "badhost"}),
        ("query",         {"sql": "SELECT 1", "database": "mydb"}),
        ("dump",          {"database": "mydb"}),
        ("grant",         {"user": "u", "database": "d"}),
        ("drop_database", {"database": "olddb"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}'"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "Failed: AVC avc: denied { read } for pid=1234 "
        "comm=\"mysql\" name=\"mysqld.sock\""
    )

    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("query",         {"sql": "SELECT 1"}),
        ("dump",          {"database": "mydb"}),
        ("grant",         {"user": "u", "database": "d"}),
        ("drop_database", {"database": "olddb"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint for op='{op}', got: {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("status",        {}),
        ("query",         {"sql": "SELECT 1"}),
        ("dump",          {"database": "mydb"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="Connection refused.")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"SELinux hint fired on clean stderr for op='{op}': {result.summary!r}"
        )


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert "nonexistent_op" in result.summary

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """Simulate the binary not being installed (exit 127)."""
        with _patch_run(_fail(exit_code=127, stderr="mysqladmin: command not found")):
            result = _execute("status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_missing_binary_query_exit_127(self) -> None:
        with _patch_run(_fail(exit_code=127, stderr="mysql: command not found")):
            result = _execute("query", {"sql": "SELECT 1"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_dump_exit_127(self) -> None:
        with _patch_run(_fail(exit_code=127, stderr="mysqldump: command not found")):
            result = _execute("dump", {"database": "mydb"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_missing_binary_drop_exit_127(self) -> None:
        with _patch_run(_fail(exit_code=127, stderr="mysqladmin: command not found")):
            result = _execute("drop_database", {"database": "olddb"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_status(self) -> None:
        with _patch_run(_ok(stdout="Uptime: 100  Threads: 1\n")):
            result = registry.dispatch("mariadb", "status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_query(self) -> None:
        with _patch_run(_ok(stdout="VERSION()\n10.5.22\n")):
            result = registry.dispatch("mariadb", "query", {"sql": "SELECT VERSION()"})
        assert result.ok

    def test_dispatch_drop_database(self) -> None:
        with _patch_run(_ok(stdout="Dropping database...\n")):
            result = registry.dispatch("mariadb", "drop_database", {"database": "olddb"})
        assert result.ok

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("mariadb", "nonexistent_op", {})

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'sql'"):
            registry.dispatch("mariadb", "query", {})

    def test_dispatch_dump_missing_database_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'database'"):
            registry.dispatch("mariadb", "dump", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real MariaDB on Rocky Linux 9")
def test_live_status() -> None:
    """Live: mysqladmin status returns a populated ToolResult."""
    result = _execute("status", {})
    assert result.exit_code in (0, 1, 2)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real MariaDB on Rocky Linux 9")
def test_live_query_version() -> None:
    """Live: mysql -e 'SELECT VERSION()' returns MariaDB version string."""
    result = _execute("query", {"sql": "SELECT VERSION()"})
    assert result.exit_code == 0
    assert "MariaDB" in result.stdout or "maria" in result.stdout.lower()


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real MariaDB + root on Rocky Linux 9")
def test_live_dump_requires_privileges() -> None:
    """Live: mysqldump on a database requires SELECT privilege."""
    result = _execute("dump", {"database": "mysql"})
    assert result.exit_code is not None
