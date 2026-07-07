"""tests/test_tools_postgresql.py — Unit tests for core/tools/postgresql.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without psql, createdb, createuser, pg_dump, or
dropdb present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: status/query are READ; createdb/createuser/pg_dump are
    WRITE; dropdb is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Command vectors: exact argv list passed to run_subprocess per op.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code=1) -> ok=False, failure summary.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * I2: no AI/LLM/model/agent language in any summary.
  * I9: execute() NEVER raises — unknown op and missing-binary (exit 127) both
    return well-formed ToolResult, no exception.
  * Structure: every op returns a ToolResult with as_dict() == 4 required keys.
  * DEFERRED-TO-MOSSAD: live execution tests skipped on dev host.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Side-effect import: triggers registry.register(POSTGRESQL_SPEC)
import core.tools.postgresql  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.postgresql import POSTGRESQL_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Context-manager patch on core.tools.postgresql.run_subprocess."""
    return patch("core.tools.postgresql.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_postgresql_registered(self) -> None:
        assert registry.get("postgresql") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("postgresql")
        assert spec is not None
        assert spec.name == "postgresql"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("postgresql")
        assert spec is not None
        expected = {"status", "query", "createdb", "createuser", "pg_dump", "dropdb"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["status", "query"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("postgresql", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["createdb", "createuser", "pg_dump"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("postgresql", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_dropdb_is_destructive(self) -> None:
        cls = registry.permission_class_for("postgresql", "dropdb")
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for 'dropdb', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — assert argv list passed to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_status_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.postgresql.run_subprocess", mock_fn):
            _execute("status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["systemctl", "status", "--no-pager", "postgresql"]

    def test_query_command_default_db(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.postgresql.run_subprocess", mock_fn):
            _execute("query", {"sql": "SELECT 1"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "psql"
        assert "-U" in argv
        assert "-d" in argv
        assert "-c" in argv
        assert "SELECT 1" in argv

    def test_query_command_custom_db(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.postgresql.run_subprocess", mock_fn):
            _execute("query", {"sql": "SELECT count(*) FROM orders", "database": "shop", "username": "admin"})
        argv = mock_fn.call_args[0][0]
        assert "shop" in argv
        assert "admin" in argv
        assert "SELECT count(*) FROM orders" in argv

    def test_createdb_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.postgresql.run_subprocess", mock_fn):
            _execute("createdb", {"dbname": "mydb"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "createdb"
        assert "mydb" in argv
        assert "-U" in argv

    def test_createuser_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.postgresql.run_subprocess", mock_fn):
            _execute("createuser", {"rolename": "appuser"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "createuser"
        assert "appuser" in argv
        assert "-U" in argv

    def test_pg_dump_command(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.postgresql.run_subprocess", mock_fn):
            _execute("pg_dump", {"dbname": "appdb", "output_file": "/backup/appdb.sql"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "pg_dump"
        assert "-f" in argv
        assert "/backup/appdb.sql" in argv
        assert "appdb" in argv

    def test_dropdb_command(self) -> None:
        """dropdb argv must contain the real 'dropdb' binary name (visible to classifier)."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.postgresql.run_subprocess", mock_fn):
            _execute("dropdb", {"dbname": "olddb"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "dropdb"
        assert "olddb" in argv


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure paths
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_success_exit_ok(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_failure_exit_not_ok(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1

    def test_failure_summary_contains_exit_code(self) -> None:
        with _patch_run(_fail(exit_code=2)):
            result = _execute("createdb", {"dbname": "appdb"})
        assert "2" in result.summary or "appdb" in result.summary

    def test_dropdb_success_summary_mentions_dbname(self) -> None:
        with _patch_run(_ok()):
            result = _execute("dropdb", {"dbname": "legacy_db"})
        assert "legacy_db" in result.summary

    def test_pg_dump_success_summary_mentions_output(self) -> None:
        with _patch_run(_ok()):
            result = _execute("pg_dump", {"dbname": "prod", "output_file": "/backup/prod.sql"})
        assert "prod" in result.summary
        assert "/backup/prod.sql" in result.summary


# ---------------------------------------------------------------------------
# status operation
# ---------------------------------------------------------------------------

class TestStatus:
    def test_success_summary(self) -> None:
        stdout = (
            "● postgresql.service - PostgreSQL Database Server\n"
            "     Active: active (running) since Mon 2026-07-06 00:01:04 UTC"
        )
        with _patch_run(_ok(stdout=stdout)):
            result = _execute("status", {})
        assert result.ok
        assert "PostgreSQL" in result.summary or "active" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch_run(_fail(exit_code=3)):
            result = _execute("status", {})
        assert not result.ok
        assert "3" in result.summary

    def test_stdout_preserved(self) -> None:
        with _patch_run(_ok(stdout="some status output")):
            result = _execute("status", {})
        assert result.stdout == "some status output"


# ---------------------------------------------------------------------------
# query operation
# ---------------------------------------------------------------------------

class TestQuery:
    def test_success(self) -> None:
        with _patch_run(_ok(stdout=" ?column?\n----------\n 1\n(1 row)\n")):
            result = _execute("query", {"sql": "SELECT 1"})
        assert result.ok
        assert "postgres" in result.summary or "success" in result.summary.lower()

    def test_failure_with_fatal(self) -> None:
        with _patch_run(_fail(exit_code=2, stderr="FATAL: database does not exist")):
            result = _execute("query", {"sql": "SELECT 1", "database": "ghost"})
        assert not result.ok
        assert "ghost" in result.summary

    def test_custom_database_in_summary(self) -> None:
        with _patch_run(_ok()):
            result = _execute("query", {"sql": "SELECT 1", "database": "mydb"})
        assert "mydb" in result.summary


# ---------------------------------------------------------------------------
# createdb operation
# ---------------------------------------------------------------------------

class TestCreatedb:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("createdb", {"dbname": "newdb"})
        assert result.ok
        assert "newdb" in result.summary
        assert "created" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="database already exists")):
            result = _execute("createdb", {"dbname": "existing_db"})
        assert not result.ok
        assert "existing_db" in result.summary


# ---------------------------------------------------------------------------
# createuser operation
# ---------------------------------------------------------------------------

class TestCreateuser:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("createuser", {"rolename": "appuser"})
        assert result.ok
        assert "appuser" in result.summary
        assert "created" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="role already exists")):
            result = _execute("createuser", {"rolename": "existing_role"})
        assert not result.ok
        assert "existing_role" in result.summary


# ---------------------------------------------------------------------------
# pg_dump operation
# ---------------------------------------------------------------------------

class TestPgDump:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("pg_dump", {"dbname": "appdb", "output_file": "/tmp/appdb.sql"})
        assert result.ok
        assert "appdb" in result.summary
        assert "/tmp/appdb.sql" in result.summary

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="FATAL: database not found")):
            result = _execute("pg_dump", {"dbname": "ghost_db", "output_file": "/tmp/g.sql"})
        assert not result.ok
        assert "ghost_db" in result.summary


# ---------------------------------------------------------------------------
# dropdb operation
# ---------------------------------------------------------------------------

class TestDropdb:
    def test_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("dropdb", {"dbname": "testdb"})
        assert result.ok
        assert "testdb" in result.summary
        assert "drop" in result.summary.lower() or "permanent" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="database does not exist")):
            result = _execute("dropdb", {"dbname": "nonexistent_db"})
        assert not result.ok
        assert "nonexistent_db" in result.summary

    def test_dropdb_permission_class(self) -> None:
        assert POSTGRESQL_SPEC.permission_class_for("dropdb") is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "psql: error: AVC avc: denied { read } for pid=5432 "
        "comm=\"psql\" name=\"postgresql\" scontext=unconfined_u:unconfined_r:unconfined_t:s0-s0:c0.c1023"
    )

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_avc_denial_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("createdb",   {"dbname": "testdb"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="database not found")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# I2: No AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_no_ai_language_success(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_no_ai_language_failure(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# I9: execute() NEVER raises
# ---------------------------------------------------------------------------

class TestNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)

    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_missing_binary_exit_127_returns_toolresult(self, op: str, args: dict) -> None:
        """Patch run_subprocess to simulate a missing binary (exit 127)."""
        mock_result = ToolResult(exit_code=127, stdout="", stderr="command not found: psql", summary="")
        with _patch_run(mock_result):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
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
        ("status",     {}),
        ("query",      {"sql": "SELECT 1"}),
        ("createdb",   {"dbname": "testdb"}),
        ("createuser", {"rolename": "testrole"}),
        ("pg_dump",    {"dbname": "testdb", "output_file": "/tmp/t.sql"}),
        ("dropdb",     {"dbname": "testdb"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_status(self) -> None:
        with _patch_run(_ok(stdout="● postgresql.service")):
            result = registry.dispatch("postgresql", "status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_createdb(self) -> None:
        with _patch_run(_ok()):
            result = registry.dispatch("postgresql", "createdb", {"dbname": "newdb"})
        assert result.ok

    def test_dispatch_missing_dbname_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'dbname'"):
            registry.dispatch("postgresql", "createdb", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("postgresql", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real psql/postgresql on Rocky Linux 9")
def test_live_status_postgresql() -> None:
    """Live: systemctl status postgresql returns a populated ToolResult."""
    result = _execute("status", {})
    assert result.exit_code in (0, 3, 4)
    assert len(result.stdout) > 0 or len(result.stderr) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real psql on Rocky Linux 9")
def test_live_query_select_version() -> None:
    """Live: psql -c 'SELECT version()' returns version string."""
    result = _execute("query", {"sql": "SELECT version()"})
    assert result.exit_code == 0
    assert "PostgreSQL" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real createdb/dropdb on Rocky Linux 9")
def test_live_createdb_and_dropdb() -> None:
    """Live: createdb then dropdb for a transient test database."""
    create_result = _execute("createdb", {"dbname": "_test_erdtree_transient"})
    assert create_result.exit_code == 0
    drop_result = _execute("dropdb", {"dbname": "_test_erdtree_transient"})
    assert drop_result.exit_code == 0
