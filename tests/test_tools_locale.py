"""tests/test_tools_locale.py — Unit tests for core/tools/locale.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without localectl or timedatectl present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: localectl-status / timedatectl-status are READ;
    set-locale / set-keymap / set-timezone / set-ntp are WRITE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (nonzero) -> ok=False, failure summary.
  * Command vectors: the exact argv passed to run_subprocess is asserted.
  * SELinux AVC hint is surfaced when stderr contains AVC language.
  * execute() never raises for any op including unknown ops and exit 127.
  * I2: no AI/LLM/model/agent language in any summary.
  * DEFERRED-TO-MOSSAD: live execution against real localectl/timedatectl.

Mocking strategy
----------------
  Patch ``core.tools.locale.run_subprocess`` (in the locale module's
  namespace, where the ``from core.tools import run_subprocess`` binding
  lives) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration in the module-level registry.
import core.tools.locale  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.locale import LOCALE_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.locale.run_subprocess in the locale module namespace."""
    return patch("core.tools.locale.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_locale_registered(self) -> None:
        assert registry.get("locale") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("locale")
        assert spec is not None
        assert spec.name == "locale"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("locale")
        assert spec is not None
        expected = {
            "localectl-status",
            "set-locale",
            "set-keymap",
            "timedatectl-status",
            "set-timezone",
            "set-ntp",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["localectl-status", "timedatectl-status"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("locale", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["set-locale", "set-keymap", "set-timezone", "set-ntp"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("locale", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_localectl_status_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("localectl-status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["localectl", "status"]

    def test_set_locale_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("set-locale", {"locale": "en_US.UTF-8"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["localectl", "set-locale", "en_US.UTF-8"]

    def test_set_keymap_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("set-keymap", {"keymap": "us"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["localectl", "set-keymap", "us"]

    def test_timedatectl_status_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("timedatectl-status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["timedatectl", "status"]

    def test_set_timezone_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("set-timezone", {"timezone": "America/New_York"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["timedatectl", "set-timezone", "America/New_York"]

    def test_set_ntp_true_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("set-ntp", {"enabled": "true"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["timedatectl", "set-ntp", "true"]

    def test_set_ntp_false_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("set-ntp", {"enabled": "false"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["timedatectl", "set-ntp", "false"]

    @pytest.mark.parametrize("raw,expected_val", [
        ("1", "true"),
        ("yes", "true"),
        ("on", "true"),
        ("0", "false"),
        ("no", "false"),
        ("off", "false"),
    ])
    def test_set_ntp_normalises_bool_values(self, raw: str, expected_val: str) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.locale.run_subprocess", mock_fn):
            _execute("set-ntp", {"enabled": raw})
        argv = mock_fn.call_args[0][0]
        assert argv[2] == expected_val


# ---------------------------------------------------------------------------
# Exit-code mapping — success
# ---------------------------------------------------------------------------

class TestExitCodeSuccess:
    def test_localectl_status_ok(self) -> None:
        with _patch(_ok(stdout="System Locale: LANG=en_US.UTF-8")):
            result = _execute("localectl-status", {})
        assert result.ok
        assert len(result.summary) > 0

    def test_set_locale_ok(self) -> None:
        with _patch(_ok()):
            result = _execute("set-locale", {"locale": "en_US.UTF-8"})
        assert result.ok
        assert "en_US.UTF-8" in result.summary

    def test_set_keymap_ok(self) -> None:
        with _patch(_ok()):
            result = _execute("set-keymap", {"keymap": "de"})
        assert result.ok
        assert "de" in result.summary

    def test_timedatectl_status_ok(self) -> None:
        with _patch(_ok(stdout="Time zone: UTC")):
            result = _execute("timedatectl-status", {})
        assert result.ok

    def test_set_timezone_ok(self) -> None:
        with _patch(_ok()):
            result = _execute("set-timezone", {"timezone": "UTC"})
        assert result.ok
        assert "UTC" in result.summary

    def test_set_ntp_ok(self) -> None:
        with _patch(_ok()):
            result = _execute("set-ntp", {"enabled": "true"})
        assert result.ok
        assert "enabled" in result.summary.lower()


# ---------------------------------------------------------------------------
# Exit-code mapping — failure
# ---------------------------------------------------------------------------

class TestExitCodeFailure:
    def test_localectl_status_fail(self) -> None:
        with _patch(_fail(exit_code=1, stderr="command not found")):
            result = _execute("localectl-status", {})
        assert not result.ok
        assert result.exit_code == 1

    def test_set_locale_fail(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Locale not found")):
            result = _execute("set-locale", {"locale": "xx_XX.UTF-8"})
        assert not result.ok
        assert "xx_XX.UTF-8" in result.summary
        assert "1" in result.summary

    def test_set_keymap_fail(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Keymap not found")):
            result = _execute("set-keymap", {"keymap": "bogus"})
        assert not result.ok
        assert "bogus" in result.summary

    def test_timedatectl_status_fail(self) -> None:
        with _patch(_fail(exit_code=127)):
            result = _execute("timedatectl-status", {})
        assert not result.ok
        assert result.exit_code == 127

    def test_set_timezone_fail(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Timezone not found")):
            result = _execute("set-timezone", {"timezone": "Invalid/Zone"})
        assert not result.ok
        assert "Invalid/Zone" in result.summary

    def test_set_ntp_fail(self) -> None:
        with _patch(_fail(exit_code=1, stderr="NTP unavailable")):
            result = _execute("set-ntp", {"enabled": "true"})
        assert not result.ok


# ---------------------------------------------------------------------------
# I2-clean summaries — no AI language
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("localectl-status",   {}),
        ("set-locale",         {"locale": "en_US.UTF-8"}),
        ("set-keymap",         {"keymap": "us"}),
        ("timedatectl-status", {}),
        ("set-timezone",       {"timezone": "UTC"}),
        ("set-ntp",            {"enabled": "true"}),
    ])
    def test_no_ai_language_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("localectl-status",   {}),
        ("set-locale",         {"locale": "en_US.UTF-8"}),
        ("set-timezone",       {"timezone": "UTC"}),
        ("set-ntp",            {"enabled": "true"}),
    ])
    def test_no_ai_language_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "AVC avc: denied { write } for pid=5432 "
        "comm=\"localectl\" name=\"locale.conf\" scontext=system_u:system_r:init_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("localectl-status",   {}),
        ("set-locale",         {"locale": "en_US.UTF-8"}),
        ("set-keymap",         {"keymap": "us"}),
        ("timedatectl-status", {}),
        ("set-timezone",       {"timezone": "UTC"}),
        ("set-ntp",            {"enabled": "true"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert "SELinux" in result.summary or "ausearch" in result.summary, (
            f"SELinux hint missing for op='{op}': {result.summary!r}"
        )

    @pytest.mark.parametrize("op,args", [
        ("localectl-status",   {}),
        ("set-locale",         {"locale": "en_US.UTF-8"}),
        ("timedatectl-status", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="command not found")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("localectl-status",   {}),
        ("set-locale",         {"locale": "en_US.UTF-8"}),
        ("set-keymap",         {"keymap": "us"}),
        ("timedatectl-status", {}),
        ("set-timezone",       {"timezone": "UTC"}),
        ("set-ntp",            {"enabled": "true"}),
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
        ("localectl-status",   {}),
        ("set-locale",         {"locale": "en_US.UTF-8"}),
        ("set-keymap",         {"keymap": "us"}),
        ("timedatectl-status", {}),
        ("set-timezone",       {"timezone": "UTC"}),
        ("set-ntp",            {"enabled": "true"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# execute() NEVER raises (I9)
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("completely-bogus-op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert "completely-bogus-op" in result.summary

    def test_missing_binary_exit_127(self) -> None:
        """Simulate run_subprocess returning exit 127 (binary not found)."""
        with _patch(_fail(exit_code=127, stderr="localectl: command not found")):
            result = _execute("localectl-status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_set_locale(self) -> None:
        with _patch(_fail(exit_code=127, stderr="localectl: command not found")):
            result = _execute("set-locale", {"locale": "en_US.UTF-8"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    def test_missing_binary_timedatectl(self) -> None:
        with _patch(_fail(exit_code=127, stderr="timedatectl: command not found")):
            result = _execute("timedatectl-status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127

    @pytest.mark.parametrize("op,args", [
        ("localectl-status",   {}),
        ("set-locale",         {"locale": "en_US.UTF-8"}),
        ("set-keymap",         {"keymap": "us"}),
        ("timedatectl-status", {}),
        ("set-timezone",       {"timezone": "UTC"}),
        ("set-ntp",            {"enabled": "true"}),
    ])
    def test_no_exception_on_any_op(self, op: str, args: dict) -> None:
        """execute() must not raise for any valid op, even with a failing subprocess."""
        with _patch(_fail(exit_code=1, stderr="error")):
            try:
                result = _execute(op, args)
            except Exception as exc:  # noqa: BLE001
                pytest.fail(f"_execute raised {type(exc).__name__} for op='{op}': {exc}")
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_localectl_status(self) -> None:
        with _patch(_ok(stdout="System Locale: LANG=en_US.UTF-8")):
            result = registry.dispatch("locale", "localectl-status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_set_locale(self) -> None:
        with _patch(_ok()):
            result = registry.dispatch("locale", "set-locale", {"locale": "en_US.UTF-8"})
        assert result.ok

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'locale'"):
            registry.dispatch("locale", "set-locale", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("locale", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# LOCALE_SPEC direct attribute checks
# ---------------------------------------------------------------------------

class TestSpecAttributes:
    def test_spec_description_is_i2_clean(self) -> None:
        forbidden = {"AI", "LLM", "model", "agent", "agentic", "neural"}
        for word in forbidden:
            assert word not in LOCALE_SPEC.description, (
                f"I2 violation in LOCALE_SPEC.description: '{word}'"
            )

    def test_op_descriptions_are_i2_clean(self) -> None:
        forbidden = {"AI", "LLM", "model", "agent", "agentic", "neural"}
        for op_name, op_spec in LOCALE_SPEC.ops.items():
            for word in forbidden:
                assert word not in op_spec.description, (
                    f"I2 violation in op '{op_name}' description: '{word}'"
                )


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real localectl on Rocky Linux 9")
def test_live_localectl_status() -> None:
    """Live: localectl status returns a populated ToolResult."""
    result = _execute("localectl-status", {})
    assert result.exit_code == 0
    assert "LANG" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real timedatectl on Rocky Linux 9")
def test_live_timedatectl_status() -> None:
    """Live: timedatectl status returns time/date info."""
    result = _execute("timedatectl-status", {})
    assert result.exit_code == 0
    assert "Time zone" in result.stdout


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real localectl + root on Rocky Linux 9")
def test_live_set_locale_requires_root() -> None:
    """Live: localectl set-locale requires elevated privileges.
    Run as root to succeed; otherwise expect exit non-0.
    """
    result = _execute("set-locale", {"locale": "en_US.UTF-8"})
    assert result.exit_code is not None


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real timedatectl + root on Rocky Linux 9")
def test_live_set_timezone_requires_root() -> None:
    """Live: timedatectl set-timezone requires elevated privileges."""
    result = _execute("set-timezone", {"timezone": "UTC"})
    assert result.exit_code is not None
