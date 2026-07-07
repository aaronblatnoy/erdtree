"""tests/test_tools_nmcli.py — Unit tests for core/tools/nmcli.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without nmcli present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: device_status/connection_show/wifi_list are READ;
    connection_add/modify/up/down/wifi_connect/dns_configure are WRITE;
    connection_delete is DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit (exit_code != 0) → ok=False, failure summary with op context.
  * Command vectors: argv lists are correct for each op.
  * SELinux AVC hint is surfaced in summary when stderr contains AVC language.
  * execute() NEVER raises for unknown ops or missing binary (exit 127).
  * DEFERRED-TO-MOSSAD: live execution against real nmcli on Rocky Linux 9.

Mocking strategy
----------------
  We patch ``core.tools.nmcli.run_subprocess`` (the function in the
  nmcli module's namespace) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Import the module to trigger self-registration.
import core.tools.nmcli  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.nmcli import NMCLI_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 4, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.nmcli.run_subprocess."""
    return patch("core.tools.nmcli.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_nmcli_registered(self) -> None:
        assert registry.get("nmcli") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("nmcli")
        assert spec is not None
        assert spec.name == "nmcli"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("nmcli")
        assert spec is not None
        expected = {
            "device_status",
            "connection_show",
            "connection_add",
            "connection_modify",
            "connection_up",
            "connection_down",
            "connection_delete",
            "wifi_list",
            "wifi_connect",
            "dns_configure",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["device_status", "connection_show", "wifi_list"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nmcli", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", [
        "connection_add", "connection_modify", "connection_up",
        "connection_down", "wifi_connect", "dns_configure",
    ])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("nmcli", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_connection_delete_is_destructive(self) -> None:
        cls = registry.permission_class_for("nmcli", "connection_delete")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors
# ---------------------------------------------------------------------------

class TestCommandVectors:
    """Assert the exact argv list passed to run_subprocess for each op."""

    def test_device_status_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("device_status", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "device", "status"]

    def test_connection_show_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("connection_show", {"name": "eth0-static"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "connection", "show", "eth0-static"]

    def test_connection_add_argv_minimal(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("connection_add", {
                "type": "ethernet",
                "con_name": "my-conn",
                "ifname": "eth1",
            })
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "nmcli", "connection", "add",
            "type", "ethernet",
            "con-name", "my-conn",
            "ifname", "eth1",
        ]

    def test_connection_add_argv_with_ip4_gw4(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("connection_add", {
                "type": "ethernet",
                "con_name": "static-eth",
                "ifname": "eth0",
                "ip4": "10.0.0.5/24",
                "gw4": "10.0.0.1",
            })
        argv = mock_fn.call_args[0][0]
        assert "ip4" in argv
        assert "10.0.0.5/24" in argv
        assert "gw4" in argv
        assert "10.0.0.1" in argv

    def test_connection_modify_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("connection_modify", {
                "name": "eth0-static",
                "property": "ipv4.addresses",
                "value": "192.168.1.50/24",
            })
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "nmcli", "connection", "modify",
            "eth0-static", "ipv4.addresses", "192.168.1.50/24",
        ]

    def test_connection_up_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("connection_up", {"name": "eth0-static"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "connection", "up", "eth0-static"]

    def test_connection_down_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("connection_down", {"name": "guest-wifi"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "connection", "down", "guest-wifi"]

    def test_connection_delete_argv(self) -> None:
        """Verify the destructive verb 'delete' is literally in argv[2]."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("connection_delete", {"name": "old-vpn"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "connection", "delete", "old-vpn"]
        # The destructive verb must be the literal string so the classifier can gate it.
        assert argv[2] == "delete"

    def test_wifi_list_argv_no_ifname(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("wifi_list", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "device", "wifi", "list"]

    def test_wifi_list_argv_with_ifname(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("wifi_list", {"ifname": "wlan0"})
        argv = mock_fn.call_args[0][0]
        assert "ifname" in argv
        assert "wlan0" in argv

    def test_wifi_connect_argv_no_password(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("wifi_connect", {"ssid": "OpenNet"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["nmcli", "device", "wifi", "connect", "OpenNet"]
        assert "password" not in argv

    def test_wifi_connect_argv_with_password(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("wifi_connect", {"ssid": "CorpWifi", "password": "secret123"})
        argv = mock_fn.call_args[0][0]
        assert "password" in argv
        assert "secret123" in argv

    def test_dns_configure_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.nmcli.run_subprocess", mock_fn):
            _execute("dns_configure", {"name": "eth0-static", "dns": "8.8.8.8 8.8.4.4"})
        argv = mock_fn.call_args[0][0]
        assert argv == [
            "nmcli", "connection", "modify",
            "eth0-static", "ipv4.dns", "8.8.8.8 8.8.4.4",
        ]


# ---------------------------------------------------------------------------
# Exit-code mapping and summary content
# ---------------------------------------------------------------------------

class TestDeviceStatus:
    def test_success_summary(self) -> None:
        with _patch(_ok(stdout="DEVICE  TYPE      STATE\neth0    ethernet  connected\n")):
            result = _execute("device_status", {})
        assert result.ok
        assert "device status" in result.summary.lower() or "retrieved" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=10, stderr="Error: NetworkManager is not running.")):
            result = _execute("device_status", {})
        assert not result.ok
        assert "10" in result.summary


class TestConnectionShow:
    def test_success(self) -> None:
        with _patch(_ok(stdout="connection.id: eth0-static\n")):
            result = _execute("connection_show", {"name": "eth0-static"})
        assert result.ok
        assert "eth0-static" in result.summary

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: notfound - no such connection profile.")):
            result = _execute("connection_show", {"name": "notfound"})
        assert not result.ok
        assert "notfound" in result.summary


class TestConnectionAdd:
    def test_success(self) -> None:
        with _patch(_ok(stdout="Connection 'my-conn' successfully added.\n")):
            result = _execute("connection_add", {
                "type": "ethernet", "con_name": "my-conn", "ifname": "eth1",
            })
        assert result.ok
        assert "my-conn" in result.summary
        assert "created" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: invalid type")):
            result = _execute("connection_add", {
                "type": "bad-type", "con_name": "x-conn", "ifname": "eth9",
            })
        assert not result.ok
        assert "x-conn" in result.summary


class TestConnectionModify:
    def test_success(self) -> None:
        with _patch(_ok()):
            result = _execute("connection_modify", {
                "name": "eth0-static", "property": "ipv4.dns", "value": "1.1.1.1",
            })
        assert result.ok
        assert "eth0-static" in result.summary
        assert "ipv4.dns" in result.summary

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4)):
            result = _execute("connection_modify", {
                "name": "ghost-conn", "property": "ipv4.dns", "value": "1.1.1.1",
            })
        assert not result.ok
        assert "ghost-conn" in result.summary


class TestConnectionUp:
    def test_success(self) -> None:
        with _patch(_ok(stdout="Connection successfully activated.\n")):
            result = _execute("connection_up", {"name": "eth0-static"})
        assert result.ok
        assert "eth0-static" in result.summary
        assert "activated" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: No carrier")):
            result = _execute("connection_up", {"name": "eth1-broken"})
        assert not result.ok
        assert "eth1-broken" in result.summary


class TestConnectionDown:
    def test_success(self) -> None:
        with _patch(_ok(stdout="Connection 'guest-wifi' successfully deactivated.\n")):
            result = _execute("connection_down", {"name": "guest-wifi"})
        assert result.ok
        assert "guest-wifi" in result.summary
        assert "deactivated" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4)):
            result = _execute("connection_down", {"name": "no-such-conn"})
        assert not result.ok
        assert "no-such-conn" in result.summary


class TestConnectionDelete:
    def test_success(self) -> None:
        with _patch(_ok(stdout="Connection 'old-vpn' successfully deleted.\n")):
            result = _execute("connection_delete", {"name": "old-vpn"})
        assert result.ok
        assert "old-vpn" in result.summary
        assert "deleted" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: ghost - no such connection profile.")):
            result = _execute("connection_delete", {"name": "ghost"})
        assert not result.ok
        assert "ghost" in result.summary

    def test_is_destructive(self) -> None:
        cls = NMCLI_SPEC.permission_class_for("connection_delete")
        assert cls is OpClass.DESTRUCTIVE


class TestWifiList:
    def test_success(self) -> None:
        stdout = "IN-USE  BSSID              SSID\n*       AA:BB  OfficeWifi\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("wifi_list", {})
        assert result.ok
        assert "wi-fi" in result.summary.lower() or "network" in result.summary.lower()

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: No Wi-Fi device found.")):
            result = _execute("wifi_list", {})
        assert not result.ok
        assert "4" in result.summary


class TestWifiConnect:
    def test_success(self) -> None:
        with _patch(_ok(stdout="Device 'wlan0' successfully activated.\n")):
            result = _execute("wifi_connect", {"ssid": "OfficeWifi"})
        assert result.ok
        assert "OfficeWifi" in result.summary
        assert "connected" in result.summary.lower()

    def test_failure_wrong_password(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: Secrets were required, but not provided.")):
            result = _execute("wifi_connect", {"ssid": "CorpNet", "password": "wrong"})
        assert not result.ok
        assert "CorpNet" in result.summary


class TestDnsConfigure:
    def test_success(self) -> None:
        with _patch(_ok()):
            result = _execute("dns_configure", {"name": "eth0-static", "dns": "8.8.8.8"})
        assert result.ok
        assert "eth0-static" in result.summary
        assert "8.8.8.8" in result.summary

    def test_failure(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: profile not found")):
            result = _execute("dns_configure", {"name": "ghost-conn", "dns": "8.8.8.8"})
        assert not result.ok
        assert "ghost-conn" in result.summary


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    @pytest.mark.parametrize("op,args", [
        ("device_status",    {}),
        ("connection_show",  {"name": "eth0-static"}),
        ("connection_up",    {"name": "eth0-static"}),
        ("connection_delete", {"name": "eth0-static"}),
        ("dns_configure",    {"name": "eth0-static", "dns": "8.8.8.8"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        avc_stderr = (
            "AVC avc: denied { read } for pid=1234 comm=\"nmcli\" "
            "name=\"nmcli\" scontext=staff_u:staff_r:staff_t"
        )
        with _patch(_fail(exit_code=1, stderr=avc_stderr)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        )

    def test_clean_stderr_no_hint(self) -> None:
        with _patch(_fail(exit_code=4, stderr="Error: profile not found.")):
            result = _execute("connection_show", {"name": "missing"})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("device_status",    {}),
        ("connection_show",  {"name": "eth0-static"}),
        ("connection_add",   {"type": "ethernet", "con_name": "test", "ifname": "eth0"}),
        ("connection_modify", {"name": "eth0-static", "property": "ipv4.dns", "value": "1.1.1.1"}),
        ("connection_up",    {"name": "eth0-static"}),
        ("connection_down",  {"name": "eth0-static"}),
        ("connection_delete", {"name": "old-vpn"}),
        ("wifi_list",        {}),
        ("wifi_connect",     {"ssid": "TestSSID"}),
        ("dns_configure",    {"name": "eth0-static", "dns": "8.8.8.8"}),
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
        ("device_status",    {}),
        ("connection_show",  {"name": "x"}),
        ("connection_delete", {"name": "x"}),
        ("wifi_list",        {}),
        ("dns_configure",    {"name": "x", "dns": "1.1.1.1"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() never raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        result = _execute("totally_unknown_op", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "Unknown operation" in result.summary
        assert len(result.summary) > 0

    def test_missing_binary_exit_127_is_handled(self) -> None:
        missing_binary = ToolResult(
            exit_code=127,
            stdout="",
            stderr="nmcli: command not found",
            summary="",
        )
        with patch("core.tools.nmcli.run_subprocess", return_value=missing_binary):
            result = _execute("device_status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0

    def test_exit_127_on_connection_delete(self) -> None:
        missing_binary = ToolResult(
            exit_code=127, stdout="", stderr="nmcli: command not found", summary=""
        )
        with patch("core.tools.nmcli.run_subprocess", return_value=missing_binary):
            result = _execute("connection_delete", {"name": "some-conn"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# No AI / LLM / model language in any summary  (I2)
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("device_status",    {}),
        ("connection_show",  {"name": "eth0-static"}),
        ("connection_add",   {"type": "ethernet", "con_name": "test-conn", "ifname": "eth0"}),
        ("connection_modify", {"name": "eth0-static", "property": "ipv4.dns", "value": "1.1.1.1"}),
        ("connection_up",    {"name": "eth0-static"}),
        ("connection_down",  {"name": "eth0-static"}),
        ("connection_delete", {"name": "old-vpn"}),
        ("wifi_list",        {}),
        ("wifi_connect",     {"ssid": "OfficeWifi"}),
        ("dns_configure",    {"name": "eth0-static", "dns": "8.8.8.8"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("connection_show",   {"name": "eth0-static"}),
        ("connection_delete", {"name": "old-vpn"}),
        ("dns_configure",     {"name": "eth0-static", "dns": "8.8.8.8"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=4, stderr="some error")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_device_status(self) -> None:
        with _patch(_ok(stdout="DEVICE  TYPE      STATE\neth0    ethernet  connected\n")):
            result = registry.dispatch("nmcli", "device_status", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_connection_delete(self) -> None:
        with _patch(_ok(stdout="Connection 'x' deleted.\n")):
            result = registry.dispatch("nmcli", "connection_delete", {"name": "x"})
        assert result.ok

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with pytest.raises(TypeError):
            registry.dispatch("nmcli", "connection_show", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("nmcli", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nmcli on Rocky Linux 9")
def test_live_device_status() -> None:
    """Live: nmcli device status returns a populated ToolResult."""
    result = _execute("device_status", {})
    assert result.exit_code in (0, 4, 10)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nmcli on Rocky Linux 9")
def test_live_wifi_list() -> None:
    """Live: nmcli device wifi list returns a populated ToolResult."""
    result = _execute("wifi_list", {})
    assert result.exit_code in (0, 4)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real nmcli on Rocky Linux 9")
def test_live_connection_show_requires_profile() -> None:
    """Live: nmcli connection show <name> returns a populated ToolResult."""
    result = _execute("connection_show", {"name": "Wired connection 1"})
    assert result.exit_code in (0, 4)
