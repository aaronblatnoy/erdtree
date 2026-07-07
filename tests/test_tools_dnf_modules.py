"""tests/test_tools_dnf_modules.py — Unit tests for core/tools/dnf_modules.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without dnf present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: list/info are READ; enable/disable/install/reset are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code=1) -> ok=False, failure summary containing the
    module name and exit code.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() never raises (I9) — unknown op and missing binary both return
    a well-formed ToolResult.
  * I2: no AI/LLM/model/agent/agentic/neural/language-model language in
    any success or failure summary.
  * ToolResult.as_dict() returns exactly the four canonical keys.
  * DEFERRED-TO-MOSSAD: live execution against real dnf on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.dnf_modules.run_subprocess`` (the function in the
  dnf_modules module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.dnf_modules  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.dnf_modules import DNF_MODULES_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Return a context-manager patch on core.tools.dnf_modules.run_subprocess."""
    return patch("core.tools.dnf_modules.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# 1. Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_dnf_modules_registered(self) -> None:
        assert registry.get("dnf_modules") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("dnf_modules")
        assert spec is not None
        assert spec.name == "dnf_modules"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("dnf_modules")
        assert spec is not None
        expected = {"list", "info", "enable", "disable", "install", "reset"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# 2. Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["list", "info"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("dnf_modules", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["enable", "disable", "install", "reset"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("dnf_modules", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# 3. Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_list_no_filter(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.dnf_modules.run_subprocess", mock_fn):
            _execute("list", {"module": ""})
        argv = mock_fn.call_args[0][0]
        assert argv == ["dnf", "module", "list"]

    def test_list_with_filter(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.dnf_modules.run_subprocess", mock_fn):
            _execute("list", {"module": "nodejs"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["dnf", "module", "list", "nodejs"]

    def test_info_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.dnf_modules.run_subprocess", mock_fn):
            _execute("info", {"module": "nodejs:18"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["dnf", "module", "info", "nodejs:18"]

    def test_enable_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.dnf_modules.run_subprocess", mock_fn):
            _execute("enable", {"module": "nodejs:18"})
        argv = mock_fn.call_args[0][0]
        assert argv[:3] == ["dnf", "module", "enable"]
        assert "nodejs:18" in argv
        assert "-y" in argv

    def test_disable_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.dnf_modules.run_subprocess", mock_fn):
            _execute("disable", {"module": "nodejs:18"})
        argv = mock_fn.call_args[0][0]
        assert argv[:3] == ["dnf", "module", "disable"]
        assert "nodejs:18" in argv
        assert "-y" in argv

    def test_install_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.dnf_modules.run_subprocess", mock_fn):
            _execute("install", {"module": "nodejs:18"})
        argv = mock_fn.call_args[0][0]
        assert argv[:3] == ["dnf", "module", "install"]
        assert "nodejs:18" in argv
        assert "-y" in argv

    def test_reset_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.dnf_modules.run_subprocess", mock_fn):
            _execute("reset", {"module": "nodejs"})
        argv = mock_fn.call_args[0][0]
        assert argv[:3] == ["dnf", "module", "reset"]
        assert "nodejs" in argv
        assert "-y" in argv


# ---------------------------------------------------------------------------
# 4. Exit-code mapping — success and failure branches
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("list",    {"module": "nodejs"}),
        ("info",    {"module": "nodejs:18"}),
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
    ])
    def test_success_exit_zero(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="Complete!\n")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args", [
        ("list",    {"module": "nodejs"}),
        ("info",    {"module": "nodejs:18"}),
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
    ])
    def test_failure_nonzero_exit(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="Error: No matching Modules")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == 1

    @pytest.mark.parametrize("op,args,expected_fragment", [
        ("list",    {"module": "nodejs"},   "nodejs"),
        ("info",    {"module": "php:8.2"},  "php:8.2"),
        ("enable",  {"module": "ruby:3.1"}, "ruby:3.1"),
        ("disable", {"module": "nginx"},    "nginx"),
        ("install", {"module": "mariadb:10.11"}, "mariadb:10.11"),
        ("reset",   {"module": "nodejs"},   "nodejs"),
    ])
    def test_failure_summary_contains_module(
        self, op: str, args: dict, expected_fragment: str
    ) -> None:
        with _patch(_fail(exit_code=1, stderr="Error")):
            result = _execute(op, args)
        assert expected_fragment in result.summary

    @pytest.mark.parametrize("op,args", [
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
    ])
    def test_failure_summary_contains_exit_code(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1)):
            result = _execute(op, args)
        assert "1" in result.summary


# ---------------------------------------------------------------------------
# 5. I2-clean summaries (no AI/LLM language)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "agent", "agentic", "neural", "language model"}
    # Note: "model" is intentionally excluded here because it legitimately
    # appears in dnf module output (module = software module, not AI model).
    # The I2 check targets the AI-domain sense; to avoid false positives on
    # the Linux concept of a "module", we use the per-word forbidden set above.

    @pytest.mark.parametrize("op,args", [
        ("list",    {"module": "nodejs"}),
        ("info",    {"module": "nodejs:18"}),
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
    ])
    def test_no_ai_language_success(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="Complete!\n")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
    ])
    def test_no_ai_language_failure(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# 6. SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "Failed to run transaction: "
        "AVC avc: denied { write } for pid=12345 "
        "comm=\"dnf\" name=\"dnf\" scontext=unconfined_u:unconfined_r:unconfined_t"
    )

    @pytest.mark.parametrize("op,args", [
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
        ("info",    {"module": "nodejs:18"}),
    ])
    def test_avc_denial_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert ("SELinux" in result.summary or "ausearch" in result.summary), (
            f"Expected SELinux hint in summary for op='{op}': {result.summary!r}"
        )

    def test_list_avc_surfaces_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute("list", {"module": "nodejs"})
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Error: No matching Modules")):
            result = _execute("info", {"module": "phantom:99"})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# 7. execute() never raises (I9)
# ---------------------------------------------------------------------------

class TestI9NeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("nonexistent_op", {"module": "nodejs"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_op" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit127_returns_toolresult(self) -> None:
        """run_subprocess returns exit_code=127 for a missing binary (FileNotFoundError)."""
        missing_binary_result = ToolResult(
            exit_code=127,
            stdout="",
            stderr="bash: dnf: command not found",
            summary="",
        )
        with _patch(missing_binary_result):
            result = _execute("list", {"module": ""})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_execute_does_not_raise_for_any_op(self) -> None:
        for op in ("list", "info", "enable", "disable", "install", "reset", "bogus_op"):
            args: dict = {"module": "nodejs"} if op != "list" else {"module": ""}
            try:
                _execute(op, args)
            except Exception as exc:
                pytest.fail(f"_execute raised {type(exc).__name__} for op='{op}': {exc}")


# ---------------------------------------------------------------------------
# 8. ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("list",    {"module": ""}),
        ("list",    {"module": "nodejs"}),
        ("info",    {"module": "nodejs:18"}),
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("list",    {"module": ""}),
        ("info",    {"module": "nodejs:18"}),
        ("enable",  {"module": "nodejs:18"}),
        ("disable", {"module": "nodejs:18"}),
        ("install", {"module": "nodejs:18"}),
        ("reset",   {"module": "nodejs"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real dnf on Rocky Linux 9")
def test_live_list_all_modules() -> None:
    """Live: dnf module list returns a populated ToolResult."""
    result = _execute("list", {"module": ""})
    assert result.exit_code == 0
    assert len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real dnf on Rocky Linux 9")
def test_live_info_nodejs() -> None:
    """Live: dnf module info nodejs returns metadata."""
    result = _execute("info", {"module": "nodejs"})
    assert result.exit_code in (0, 1)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real dnf + root on Rocky Linux 9")
def test_live_enable_requires_root() -> None:
    """Live: dnf module enable requires elevated privileges on Rocky Linux 9.

    Run as root or with sudo. Without privileges, exit_code != 0 and stderr
    contains a permission message.
    """
    result = _execute("enable", {"module": "nodejs:18"})
    assert result.exit_code is not None
