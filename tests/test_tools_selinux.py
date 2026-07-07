"""tests/test_tools_selinux.py — Unit tests for core/tools/selinux.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without sestatus / semanage / restorecon etc.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: READ, WRITE, DESTRUCTIVE ops match the plan table.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code != 0) -> not ok, failure summary naming the key field.
  * Command vectors: argv passed to run_subprocess is exactly the expected list.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * Clean stderr does NOT surface the hint.
  * execute() NEVER raises: bogus op + exit 127 (missing binary) both degrade
    gracefully to a well-formed ToolResult with no exception.
  * I2: no AI/LLM/model/agent/agentic/neural language in any summary.
  * as_dict() returns exactly {exit_code, stdout, stderr, summary}.
  * DEFERRED-TO-MOSSAD: live execution skipped on the macOS dev host.

Mocking strategy
----------------
  Patch ``core.tools.selinux.run_subprocess`` in the selinux module's namespace
  (where the ``from core.tools import run_subprocess`` binding lives) so every
  _op_* function is intercepted without touching the real binary.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.selinux  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.selinux import SELINUX_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.selinux.run_subprocess."""
    return patch("core.tools.selinux.run_subprocess", return_value=return_value)


def _patch_fn(return_value: ToolResult) -> MagicMock:
    """Return a MagicMock pre-configured to return return_value."""
    m = MagicMock(return_value=return_value)
    return m


_AVC_STDERR = (
    "AVC avc:  denied  { read } for  pid=1234 comm=\"httpd\" "
    "name=\"index.html\" scontext=system_u:system_r:httpd_t:s0 "
    "tcontext=system_u:object_r:default_t:s0 tclass=file permissive=0"
)

_CLEAN_STDERR = "Operation not permitted.\n"


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_selinux_registered(self) -> None:
        assert registry.get("selinux") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("selinux")
        assert spec is not None
        assert spec.name == "selinux"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("selinux")
        assert spec is not None
        expected = {
            "sestatus",
            "getsebool",
            "getenforce",
            "setenforce",
            "setsebool",
            "semanage_fcontext_list",
            "semanage_fcontext_add",
            "semanage_fcontext_delete",
            "semanage_port_list",
            "semanage_port_add",
            "semanage_port_delete",
            "semanage_user_list",
            "semanage_user_add",
            "semanage_user_delete",
            "restorecon",
            "chcon",
            "audit2allow",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------


class TestPermissionClasses:
    @pytest.mark.parametrize("op", [
        "sestatus",
        "getsebool",
        "getenforce",
        "semanage_fcontext_list",
        "semanage_port_list",
        "semanage_user_list",
        "audit2allow",
    ])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("selinux", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", [
        "setenforce",
        "setsebool",
        "semanage_fcontext_add",
        "semanage_port_add",
        "semanage_user_add",
        "restorecon",
        "chcon",
    ])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("selinux", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", [
        "semanage_fcontext_delete",
        "semanage_port_delete",
        "semanage_user_delete",
    ])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("selinux", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — argv passed to run_subprocess
# ---------------------------------------------------------------------------


class TestCommandVectors:
    def test_sestatus_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("sestatus", {})
        assert m.call_args[0][0] == ["sestatus"]

    def test_getsebool_argv(self) -> None:
        m = _patch_fn(_ok(stdout="httpd_can_network_connect --> on\n"))
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("getsebool", {"boolean": "httpd_can_network_connect"})
        assert m.call_args[0][0] == ["getsebool", "httpd_can_network_connect"]

    def test_getenforce_argv(self) -> None:
        m = _patch_fn(_ok(stdout="Enforcing\n"))
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("getenforce", {})
        assert m.call_args[0][0] == ["getenforce"]

    def test_setenforce_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("setenforce", {"mode": "1"})
        assert m.call_args[0][0] == ["setenforce", "1"]

    def test_setenforce_zero_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("setenforce", {"mode": "0"})
        assert m.call_args[0][0] == ["setenforce", "0"]

    def test_setsebool_no_persist_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("setsebool", {"boolean": "httpd_can_network_connect", "value": "on"})
        assert m.call_args[0][0] == ["setsebool", "httpd_can_network_connect", "on"]

    def test_setsebool_persist_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("setsebool", {"boolean": "httpd_can_network_connect", "value": "on", "persist": True})
        assert m.call_args[0][0] == ["setsebool", "-P", "httpd_can_network_connect", "on"]

    def test_semanage_fcontext_list_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_fcontext_list", {})
        assert m.call_args[0][0] == ["semanage", "fcontext", "-l"]

    def test_semanage_fcontext_add_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_fcontext_add", {
                "fcontext_type": "httpd_sys_content_t",
                "fcontext_spec": "/srv/www(/.*)?",
            })
        assert m.call_args[0][0] == [
            "semanage", "fcontext", "-a", "-t", "httpd_sys_content_t", "/srv/www(/.*)?"
        ]

    def test_semanage_fcontext_delete_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_fcontext_delete", {"fcontext_spec": "/srv/old(/.*)?"})
        assert m.call_args[0][0] == ["semanage", "fcontext", "-d", "/srv/old(/.*)?"]

    def test_semanage_port_list_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_port_list", {})
        assert m.call_args[0][0] == ["semanage", "port", "-l"]

    def test_semanage_port_add_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_port_add", {
                "port_type": "http_port_t", "protocol": "tcp", "port": "8080"
            })
        assert m.call_args[0][0] == [
            "semanage", "port", "-a", "-t", "http_port_t", "-p", "tcp", "8080"
        ]

    def test_semanage_port_delete_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_port_delete", {"protocol": "tcp", "port": "8080"})
        assert m.call_args[0][0] == ["semanage", "port", "-d", "-p", "tcp", "8080"]

    def test_semanage_user_list_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_user_list", {})
        assert m.call_args[0][0] == ["semanage", "user", "-l"]

    def test_semanage_user_add_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_user_add", {"seuser": "dbadmin_u", "roles": "staff_r"})
        assert m.call_args[0][0] == ["semanage", "user", "-a", "-R", "staff_r", "dbadmin_u"]

    def test_semanage_user_delete_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("semanage_user_delete", {"seuser": "dbadmin_u"})
        assert m.call_args[0][0] == ["semanage", "user", "-d", "dbadmin_u"]

    def test_restorecon_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("restorecon", {"path": "/var/www/html"})
        assert m.call_args[0][0] == ["restorecon", "-Rv", "/var/www/html"]

    def test_chcon_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("chcon", {"context_type": "httpd_sys_content_t", "path": "/srv/app"})
        assert m.call_args[0][0] == ["chcon", "-t", "httpd_sys_content_t", "/srv/app"]

    def test_audit2allow_argv(self) -> None:
        m = _patch_fn(_ok())
        with patch("core.tools.selinux.run_subprocess", m):
            _execute("audit2allow", {})
        assert m.call_args[0][0] == ["audit2allow", "-a"]


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure paths
# ---------------------------------------------------------------------------


class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args", [
        ("sestatus", {}),
        ("getsebool", {"boolean": "httpd_can_network_connect"}),
        ("getenforce", {}),
        ("setenforce", {"mode": "1"}),
        ("setsebool", {"boolean": "httpd_can_network_connect", "value": "on"}),
        ("semanage_fcontext_list", {}),
        ("semanage_fcontext_add", {"fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/srv/www(/.*)?"}),
        ("semanage_fcontext_delete", {"fcontext_spec": "/srv/old(/.*)?"}),
        ("semanage_port_list", {}),
        ("semanage_port_add", {"port_type": "http_port_t", "protocol": "tcp", "port": "8080"}),
        ("semanage_port_delete", {"protocol": "tcp", "port": "8080"}),
        ("semanage_user_list", {}),
        ("semanage_user_add", {"seuser": "dbadmin_u", "roles": "staff_r"}),
        ("semanage_user_delete", {"seuser": "dbadmin_u"}),
        ("restorecon", {"path": "/var/www/html"}),
        ("chcon", {"context_type": "httpd_sys_content_t", "path": "/srv/app"}),
        ("audit2allow", {}),
    ])
    def test_success_ok_true(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="success output")):
            result = _execute(op, args)
        assert result.ok
        assert result.exit_code == 0

    @pytest.mark.parametrize("op,args,exit_code", [
        ("sestatus", {}, 127),
        ("getsebool", {"boolean": "bogus_bool"}, 1),
        ("getenforce", {}, 1),
        ("setenforce", {"mode": "0"}, 1),
        ("setsebool", {"boolean": "httpd_can_network_connect", "value": "off"}, 1),
        ("semanage_fcontext_list", {}, 1),
        ("semanage_fcontext_add", {"fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/x"}, 1),
        ("semanage_fcontext_delete", {"fcontext_spec": "/x"}, 1),
        ("semanage_port_list", {}, 1),
        ("semanage_port_add", {"port_type": "http_port_t", "protocol": "tcp", "port": "8080"}, 1),
        ("semanage_port_delete", {"protocol": "tcp", "port": "8080"}, 1),
        ("semanage_user_list", {}, 1),
        ("semanage_user_add", {"seuser": "x_u", "roles": "user_r"}, 1),
        ("semanage_user_delete", {"seuser": "x_u"}, 1),
        ("restorecon", {"path": "/nonexistent"}, 1),
        ("chcon", {"context_type": "httpd_sys_content_t", "path": "/nonexistent"}, 1),
        ("audit2allow", {}, 1),
    ])
    def test_failure_not_ok(self, op: str, args: dict, exit_code: int) -> None:
        with _patch(_fail(exit_code=exit_code, stderr="error output")):
            result = _execute(op, args)
        assert not result.ok
        assert result.exit_code == exit_code

    def test_setenforce_mode_label_enforcing_in_success(self) -> None:
        with _patch(_ok()):
            result = _execute("setenforce", {"mode": "1"})
        assert "enforcing" in result.summary.lower()

    def test_setenforce_mode_label_permissive_in_success(self) -> None:
        with _patch(_ok()):
            result = _execute("setenforce", {"mode": "0"})
        assert "permissive" in result.summary.lower()

    def test_setsebool_persist_note_in_summary(self) -> None:
        with _patch(_ok()):
            result = _execute("setsebool", {"boolean": "httpd_can_network_connect", "value": "on", "persist": True})
        assert "persistent" in result.summary.lower()

    def test_setsebool_no_persist_note_in_summary(self) -> None:
        with _patch(_ok()):
            result = _execute("setsebool", {"boolean": "httpd_can_network_connect", "value": "on"})
        assert "runtime" in result.summary.lower()


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------


class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("sestatus", {}),
        ("getsebool", {"boolean": "httpd_can_network_connect"}),
        ("getenforce", {}),
        ("setenforce", {"mode": "1"}),
        ("setsebool", {"boolean": "httpd_can_network_connect", "value": "on"}),
        ("semanage_fcontext_list", {}),
        ("semanage_fcontext_add", {"fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/srv/www(/.*)?"}),
        ("semanage_fcontext_delete", {"fcontext_spec": "/srv/old(/.*)?"}),
        ("semanage_port_list", {}),
        ("semanage_port_add", {"port_type": "http_port_t", "protocol": "tcp", "port": "8080"}),
        ("semanage_port_delete", {"protocol": "tcp", "port": "8080"}),
        ("semanage_user_list", {}),
        ("semanage_user_add", {"seuser": "dbadmin_u", "roles": "staff_r"}),
        ("semanage_user_delete", {"seuser": "dbadmin_u"}),
        ("restorecon", {"path": "/var/www/html"}),
        ("chcon", {"context_type": "httpd_sys_content_t", "path": "/srv/app"}),
        ("audit2allow", {}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout=f"{op} ok")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("sestatus", {}),
        ("getenforce", {}),
        ("setenforce", {"mode": "1"}),
        ("restorecon", {"path": "/var/www/html"}),
        ("audit2allow", {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# SELinux AVC hint surfacing
# ---------------------------------------------------------------------------


class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("sestatus", {}),
        ("getsebool", {"boolean": "httpd_can_network_connect"}),
        ("getenforce", {}),
        ("setenforce", {"mode": "1"}),
        ("setsebool", {"boolean": "httpd_can_network_connect", "value": "on"}),
        ("semanage_fcontext_list", {}),
        ("semanage_fcontext_add", {"fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/srv/www(/.*)?"}),
        ("semanage_fcontext_delete", {"fcontext_spec": "/srv/old(/.*)?"}),
        ("semanage_port_list", {}),
        ("semanage_port_add", {"port_type": "http_port_t", "protocol": "tcp", "port": "8080"}),
        ("semanage_port_delete", {"protocol": "tcp", "port": "8080"}),
        ("semanage_user_list", {}),
        ("semanage_user_add", {"seuser": "dbadmin_u", "roles": "staff_r"}),
        ("semanage_user_delete", {"seuser": "dbadmin_u"}),
        ("restorecon", {"path": "/var/www/html"}),
        ("chcon", {"context_type": "httpd_sys_content_t", "path": "/srv/app"}),
        ("audit2allow", {}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=_AVC_STDERR)):
            result = _execute(op, args)
        assert "ausearch" in result.summary or "SELinux" in result.summary or "AVC" in result.summary, (
            f"AVC hint not surfaced for op '{op}': {result.summary!r}"
        )

    @pytest.mark.parametrize("op,args", [
        ("sestatus", {}),
        ("getenforce", {}),
        ("setenforce", {"mode": "1"}),
        ("restorecon", {"path": "/var/www/html"}),
        ("audit2allow", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=_CLEAN_STDERR)):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"Hint erroneously triggered for op '{op}' with clean stderr: {result.summary!r}"
        )


# ---------------------------------------------------------------------------
# I2 — no AI/LLM/model/agent language in any summary
# ---------------------------------------------------------------------------


class TestNoAILanguage:
    """Invariant I2: no forbidden terms in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("sestatus", {}),
        ("getsebool", {"boolean": "httpd_can_network_connect"}),
        ("getenforce", {}),
        ("setenforce", {"mode": "1"}),
        ("setsebool", {"boolean": "httpd_can_network_connect", "value": "on"}),
        ("semanage_fcontext_list", {}),
        ("semanage_fcontext_add", {"fcontext_type": "httpd_sys_content_t", "fcontext_spec": "/srv/www(/.*)?"}),
        ("semanage_fcontext_delete", {"fcontext_spec": "/srv/old(/.*)?"}),
        ("semanage_port_list", {}),
        ("semanage_port_add", {"port_type": "http_port_t", "protocol": "tcp", "port": "8080"}),
        ("semanage_port_delete", {"protocol": "tcp", "port": "8080"}),
        ("semanage_user_list", {}),
        ("semanage_user_add", {"seuser": "dbadmin_u", "roles": "staff_r"}),
        ("semanage_user_delete", {"seuser": "dbadmin_u"}),
        ("restorecon", {"path": "/var/www/html"}),
        ("chcon", {"context_type": "httpd_sys_content_t", "path": "/srv/app"}),
        ("audit2allow", {}),
    ])
    def test_no_ai_language_success(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="ok")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in success summary for '{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("sestatus", {}),
        ("setenforce", {"mode": "0"}),
        ("restorecon", {"path": "/bad/path"}),
        ("audit2allow", {}),
        ("semanage_fcontext_delete", {"fcontext_spec": "/x"}),
        ("semanage_port_delete", {"protocol": "tcp", "port": "9999"}),
        ("semanage_user_delete", {"seuser": "gone_u"}),
    ])
    def test_no_ai_language_failure(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' in failure summary for '{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# execute() NEVER raises — I9 compliance
# ---------------------------------------------------------------------------


class TestI9NeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("totally_unknown_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        assert "unknown" in result.summary.lower() or "Unknown" in result.summary

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        with _patch(_fail(exit_code=127, stderr="bash: sestatus: command not found\n")):
            result = _execute("sestatus", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_semanage_exit_127(self) -> None:
        with _patch(_fail(exit_code=127, stderr="bash: semanage: command not found\n")):
            result = _execute("semanage_fcontext_list", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_restorecon_exit_127(self) -> None:
        with _patch(_fail(exit_code=127, stderr="bash: restorecon: command not found\n")):
            result = _execute("restorecon", {"path": "/var/www"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_destructive_delete_exit_127_returns_toolresult(self) -> None:
        with _patch(_fail(exit_code=127, stderr="bash: semanage: command not found\n")):
            result = _execute("semanage_port_delete", {"protocol": "tcp", "port": "8080"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------


class TestRegistryDispatch:
    def test_dispatch_sestatus(self) -> None:
        with _patch(_ok(stdout="SELinux status: enabled")):
            result = registry.dispatch("selinux", "sestatus", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_getsebool(self) -> None:
        with _patch(_ok(stdout="httpd_can_network_connect --> on\n")):
            result = registry.dispatch("selinux", "getsebool", {"boolean": "httpd_can_network_connect"})
        assert result.ok

    def test_dispatch_getsebool_missing_required_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'boolean'"):
            registry.dispatch("selinux", "getsebool", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("selinux", "nonexistent_op", {})

    def test_dispatch_restorecon(self) -> None:
        with _patch(_ok(stdout="Relabeled /var/www")):
            result = registry.dispatch("selinux", "restorecon", {"path": "/var/www"})
        assert result.ok


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sestatus on Rocky Linux 9")
def test_live_sestatus() -> None:
    """Live: sestatus returns a populated ToolResult."""
    result = _execute("sestatus", {})
    assert result.exit_code in (0, 1, 127)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real getenforce on Rocky Linux 9")
def test_live_getenforce() -> None:
    """Live: getenforce returns Enforcing/Permissive/Disabled."""
    result = _execute("getenforce", {})
    assert result.exit_code == 0
    assert result.stdout.strip() in ("Enforcing", "Permissive", "Disabled")


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real semanage on Rocky Linux 9 with root")
def test_live_semanage_port_list() -> None:
    """Live: semanage port -l returns the port label table."""
    result = _execute("semanage_port_list", {})
    assert result.exit_code == 0
    assert "http_port_t" in result.stdout or len(result.stdout) > 0
