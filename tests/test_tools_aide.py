"""tests/test_tools_aide.py — Unit tests for core/tools/aide.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without the aide binary present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: check/db_status are READ; init/update are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful I2-clean summary.
  * Failed exit (non-zero) → ok=False, failure summary naming the issue.
  * Command vectors: assert the exact argv list passed to run_subprocess.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises (I9): unknown op and missing-binary (exit 127)
    both return well-formed ToolResult, no exception.
  * ToolResult structure: exit_code non-None, stdout/stderr/summary str,
    summary non-empty, as_dict() has exactly 4 keys.
  * No AI/LLM/model/agent language in any summary (I2).
  * DEFERRED-TO-MOSSAD: live execution against real aide on Rocky Linux 9.

Mocking strategy
----------------
  Patch ``core.tools.aide.run_subprocess`` (in the aide module's namespace,
  where the ``from core.tools import run_subprocess`` binding lives) to
  return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.aide  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.aide import AIDE_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Return a context-manager patch on core.tools.aide.run_subprocess."""
    return patch("core.tools.aide.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_aide_registered(self) -> None:
        assert registry.get("aide") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("aide")
        assert spec is not None
        assert spec.name == "aide"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("aide")
        assert spec is not None
        assert set(spec.ops.keys()) == {"check", "init", "update", "db_status"}


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["check", "db_status"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("aide", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["init", "update"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("aide", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_check_default_config(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("check", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["aide", "--check", "--config", "/etc/aide.conf"]

    def test_check_custom_config(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("check", {"config": "/etc/aide/prod.conf"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["aide", "--check", "--config", "/etc/aide/prod.conf"]

    def test_init_default_config(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("init", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["aide", "--init", "--config", "/etc/aide.conf"]

    def test_init_custom_config(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("init", {"config": "/etc/aide/custom.conf"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["aide", "--init", "--config", "/etc/aide/custom.conf"]

    def test_update_default_config(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("update", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["aide", "--update", "--config", "/etc/aide.conf"]

    def test_update_custom_config(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("update", {"config": "/etc/aide/custom.conf"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["aide", "--update", "--config", "/etc/aide/custom.conf"]

    def test_db_status_default_path(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("db_status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stat", "/var/lib/aide/aide.db.gz"]

    def test_db_status_custom_path(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.aide.run_subprocess", mock_fn):
            _execute("db_status", {"db_path": "/data/aide/aide.db.gz"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["stat", "/data/aide/aide.db.gz"]


# ---------------------------------------------------------------------------
# check operation
# ---------------------------------------------------------------------------

class TestCheck:
    def test_success_no_changes(self) -> None:
        stdout = "aide 0.16.2\nNo differences found.\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("check", {})
        assert result.ok
        assert "passed" in result.summary.lower() or "no" in result.summary.lower()

    def test_failure_changes_detected(self) -> None:
        stdout = "aide 0.16.2 found differences between database and filesystem!!\n"
        with _patch(_fail(exit_code=1, stdout=stdout)):
            result = _execute("check", {})
        assert not result.ok
        assert result.exit_code == 1
        assert len(result.summary) > 0

    def test_failure_db_missing(self) -> None:
        stderr = "aide: cannot open database file '/var/lib/aide/aide.db.gz'\n"
        with _patch(_fail(exit_code=2, stderr=stderr)):
            result = _execute("check", {})
        assert not result.ok
        assert result.exit_code == 2


# ---------------------------------------------------------------------------
# init operation
# ---------------------------------------------------------------------------

class TestInit:
    def test_success(self) -> None:
        stdout = "aide initialized database at /var/lib/aide/aide.db.new.gz\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("init", {})
        assert result.ok
        assert "initialised" in result.summary.lower() or "initialized" in result.summary.lower()

    def test_failure(self) -> None:
        stderr = "aide: cannot open configuration file '/etc/aide.conf'\n"
        with _patch(_fail(exit_code=2, stderr=stderr)):
            result = _execute("init", {})
        assert not result.ok
        assert result.exit_code == 2
        assert len(result.summary) > 0

    def test_success_mentions_move(self) -> None:
        with _patch(_ok()):
            result = _execute("init", {})
        # Summary should advise moving the new DB into place
        assert "aide.db" in result.summary.lower() or "baseline" in result.summary.lower()


# ---------------------------------------------------------------------------
# update operation
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_success(self) -> None:
        stdout = "aide updated database at /var/lib/aide/aide.db.new.gz\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("update", {})
        assert result.ok
        assert "updated" in result.summary.lower()

    def test_failure(self) -> None:
        stderr = "aide: cannot open database file '/var/lib/aide/aide.db.gz'\n"
        with _patch(_fail(exit_code=2, stderr=stderr)):
            result = _execute("update", {})
        assert not result.ok
        assert "update" in result.summary.lower() or "failed" in result.summary.lower()

    def test_failure_includes_exit_code(self) -> None:
        with _patch(_fail(exit_code=5, stderr="some error")):
            result = _execute("update", {})
        assert not result.ok
        assert "5" in result.summary


# ---------------------------------------------------------------------------
# db_status operation
# ---------------------------------------------------------------------------

class TestDbStatus:
    def test_success(self) -> None:
        stdout = (
            "  File: /var/lib/aide/aide.db.gz\n"
            "  Size: 2457600\n"
            "Modify: 2026-07-05 22:00:11 +0000\n"
        )
        with _patch(_ok(stdout=stdout)):
            result = _execute("db_status", {})
        assert result.ok
        assert "aide.db" in result.summary or "found" in result.summary.lower()

    def test_failure_db_absent(self) -> None:
        stderr = "stat: cannot statx '/var/lib/aide/aide.db.gz': No such file or directory\n"
        with _patch(_fail(exit_code=1, stderr=stderr)):
            result = _execute("db_status", {})
        assert not result.ok
        assert "aide.db" in result.summary.lower() or "not found" in result.summary.lower()

    def test_custom_path_in_summary(self) -> None:
        with _patch(_ok(stdout="  File: /data/aide/aide.db.gz\n")):
            result = _execute("db_status", {"db_path": "/data/aide/aide.db.gz"})
        assert result.ok
        assert "/data/aide/aide.db.gz" in result.summary


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("check",     {}),
        ("init",      {}),
        ("update",    {}),
        ("db_status", {}),
    ])
    def test_avc_denial_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc:  denied  { read } for  pid=1234 "
            "comm=\"aide\" name=\"aide.db.gz\" scontext=system_u:system_r:unconfined_t:s0"
        )
        with _patch(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint not surfaced for op={op!r}; summary={result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("check",     {}),
        ("init",      {}),
        ("update",    {}),
        ("db_status", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="permission denied in a generic way")):
            # Note: "Permission denied" IS in the SELinux hint regex, so use a
            # clearly non-AVC error message.
            pass
        with _patch(_fail(exit_code=1, stderr="file not found")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"SELinux hint wrongly surfaced for clean stderr on op={op!r}"
        )


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        with _patch(_fail(exit_code=127, stderr="aide: command not found")):
            result = _execute("check", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    def test_timeout_exit_124_returns_toolresult(self) -> None:
        with _patch(_fail(exit_code=124, stderr="")):
            result = _execute("init", {})
        assert isinstance(result, ToolResult)
        assert not result.ok

    def test_no_exception_on_all_ops_with_missing_binary(self) -> None:
        for op in ["check", "init", "update", "db_status"]:
            with _patch(_fail(exit_code=127)):
                try:
                    result = _execute(op, {})
                    assert result.exit_code == 127
                except Exception as exc:  # noqa: BLE001
                    pytest.fail(f"_execute raised for op={op!r}: {exc}")


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("check",     {}),
        ("init",      {}),
        ("update",    {}),
        ("db_status", {}),
    ])
    def test_success_result_fields(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("check",     {}),
        ("init",      {}),
        ("update",    {}),
        ("db_status", {}),
    ])
    def test_as_dict_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}

    @pytest.mark.parametrize("op,args", [
        ("check",     {}),
        ("init",      {}),
        ("update",    {}),
        ("db_status", {}),
    ])
    def test_failure_result_non_ok(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# I2 — No AI / model / LLM language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("check",     {}),
        ("init",      {}),
        ("update",    {}),
        ("db_status", {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op={op!r}: "
                f"{result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("check",     {}),
        ("init",      {}),
        ("update",    {}),
        ("db_status", {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="some error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op={op!r}: "
                f"{result.summary!r}"
            )

    def test_spec_descriptions_i2_clean(self) -> None:
        """ToolSpec and OpSpec descriptions must also be I2-clean."""
        forbidden = {"AI", "LLM", "model", "agent", "agentic", "neural"}
        spec = registry.get("aide")
        assert spec is not None
        for word in forbidden:
            assert word not in spec.description, (
                f"I2 violation in ToolSpec.description: '{word}'"
            )
            for op_name, op_spec in spec.ops.items():
                assert word not in op_spec.description, (
                    f"I2 violation in OpSpec({op_name}).description: '{word}'"
                )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_check(self) -> None:
        with _patch(_ok(stdout="No differences found.")):
            result = registry.dispatch("aide", "check", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_db_status(self) -> None:
        with _patch(_ok(stdout="  File: /var/lib/aide/aide.db.gz")):
            result = registry.dispatch("aide", "db_status", {})
        assert result.ok

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("aide", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real aide binary on Rocky Linux 9")
def test_live_check() -> None:
    """Live: aide --check exits 0 (no changes) or 1 (changes found)."""
    result = _execute("check", {})
    assert result.exit_code in (0, 1, 2, 14)
    assert isinstance(result.summary, str)
    assert len(result.summary) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real aide binary on Rocky Linux 9")
def test_live_db_status() -> None:
    """Live: stat on the AIDE DB file returns file metadata."""
    result = _execute("db_status", {})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real aide + root on Rocky Linux 9")
def test_live_init_requires_root() -> None:
    """Live: aide --init requires root. Without root, exit non-zero."""
    result = _execute("init", {})
    assert result.exit_code is not None
