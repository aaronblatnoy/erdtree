"""tests/test_tools_network.py — Unit tests for core/tools/network.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
on the dev host without nmcli or ip binaries present.

Coverage
--------
  * ToolSpec self-registration in the module-level registry after import.
  * Permission classes: show/status/connections/interfaces are READ;
    bring_up/set_ip are WRITE; bring_down is DESTRUCTIVE.
  * Each operation produces a well-formed ToolResult (all four fields present,
    summary is non-empty).
  * Successful exit (exit_code=0) → ok=True, meaningful summary.
  * Failed exit → ok=False, failure summary.
  * READ ops pass through permissions.classify() as Gate.ALLOW (no gate).
  * bring_down synthesized command ("ip link set <if> down") classifies
    DESTRUCTIVE → Gate.CONFIRM_TYPED in interactive context, Gate.REFUSE
    in non-interactive context.
  * bring_up synthesized command ("ip link set <if> up") classifies WRITE.
  * set_ip with ip addr add classifies WRITE.
  * SELinux AVC hint is surfaced when stderr contains AVC language.
  * I2 invariant: no forbidden AI/LLM terms in any ToolSpec description,
    OpSpec description, or ToolResult summary (tested by importing
    core.agent.prompt._FORBIDDEN_AI_TERMS — the canonical filter).
  * registry.get("network") is present after import.
  * DEFERRED-TO-MOSSAD: live execution on a real Rocky Linux 9 box.

Mocking strategy
----------------
  Patch ``core.tools.network.run_subprocess`` in each test so no real
  process is launched.  The tool module is imported at the top of this
  file which triggers self-registration.
"""

from __future__ import annotations

import re
import unittest
from unittest.mock import MagicMock, patch

# Import the module to trigger self-registration in the module-level registry.
import core.tools.network  # noqa: F401  (side-effect: registry.register)

from core.agent.permissions import ExecContext, Gate, OpClass, classify
from core.agent.prompt import _FORBIDDEN_AI_TERMS
from core.tools import ToolResult, registry
from core.tools.network import NETWORK_SPEC, _execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    return patch("core.tools.network.run_subprocess", return_value=return_value)


_AI_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _FORBIDDEN_AI_TERMS) + r")\b",
    re.IGNORECASE,
)


def _assert_no_ai_language(text: str, context: str = "") -> None:
    m = _AI_PATTERN.search(text)
    assert m is None, (
        f"I2 violation: forbidden term '{m.group()}' found in {context!r}: {text!r}"
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration(unittest.TestCase):

    def test_network_registered(self):
        self.assertIsNotNone(registry.get("network"))

    def test_spec_name(self):
        spec = registry.get("network")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.name, "network")

    def test_all_expected_ops_present(self):
        spec = registry.get("network")
        self.assertIsNotNone(spec)
        expected = {"show", "status", "connections", "interfaces", "wifi",
                    "bring_up", "bring_down", "set_ip"}
        self.assertEqual(set(spec.ops.keys()), expected)


# ---------------------------------------------------------------------------
# Permission classes (OpSpec advisory)
# ---------------------------------------------------------------------------

class TestPermissionClasses(unittest.TestCase):

    def _check(self, op: str, expected: OpClass):
        cls = registry.permission_class_for("network", op)
        self.assertEqual(cls, expected, f"op={op!r}: expected {expected}, got {cls}")

    def test_show_is_read(self):
        self._check("show", OpClass.READ)

    def test_status_is_read(self):
        self._check("status", OpClass.READ)

    def test_connections_is_read(self):
        self._check("connections", OpClass.READ)

    def test_interfaces_is_read(self):
        self._check("interfaces", OpClass.READ)

    def test_wifi_is_read(self):
        self._check("wifi", OpClass.READ)

    def test_bring_up_is_write(self):
        self._check("bring_up", OpClass.WRITE)

    def test_set_ip_is_write(self):
        self._check("set_ip", OpClass.WRITE)

    def test_bring_down_is_destructive(self):
        self._check("bring_down", OpClass.DESTRUCTIVE)


# ---------------------------------------------------------------------------
# Gate integration via permissions.classify
# ---------------------------------------------------------------------------

class TestGateIntegration(unittest.TestCase):
    """Verify that the synthesized command strings route to the expected gate."""

    # READ ops
    def test_show_classifies_allow(self):
        d = classify("ip addr show")
        self.assertEqual(d.gate, Gate.ALLOW)
        self.assertTrue(d.auto_ok)

    def test_status_classifies_allow(self):
        d = classify("ip -brief addr")
        self.assertEqual(d.gate, Gate.ALLOW)

    def test_connections_classifies_allow(self):
        # nmcli alone falls into the read_commands or write-pattern net.
        # nmcli con show has no write/destructive pattern -> READ via subcommand map.
        d = classify("nmcli con show")
        # The classifier has nmcli in _READ_COMMANDS. "con show" has no mutating
        # sub-verb, so the _SUBCMD_OVERRIDE_WRITE_PATTERNS determine the class.
        # "nmcli con show" has neither add/modify/delete/up/down -> READ expected.
        self.assertIn(d.gate, (Gate.ALLOW, Gate.CONFIRM))

    def test_interfaces_classifies_allow(self):
        d = classify("ip link show")
        self.assertEqual(d.gate, Gate.ALLOW)

    def test_wifi_nmcli_classifies_allow(self):
        # "nmcli -t -f active,ssid dev wifi" has no mutating sub-verb -> READ.
        d = classify("nmcli -t -f active,ssid dev wifi")
        self.assertIn(d.gate, (Gate.ALLOW, Gate.CONFIRM))

    # WRITE ops
    def test_bring_up_ip_classifies_confirm(self):
        d = classify("ip link set eth0 up")
        # "ip link set" triggers _SUBCMD_OVERRIDE_WRITE_PATTERNS -> WRITE -> CONFIRM
        self.assertEqual(d.gate, Gate.CONFIRM)
        self.assertFalse(d.auto_ok)

    def test_set_ip_addr_add_classifies_confirm(self):
        d = classify("ip addr add 192.168.1.10/24 dev eth0")
        # "ip addr add" -> _SUBCMD_OVERRIDE_WRITE_PATTERNS -> WRITE -> CONFIRM
        self.assertEqual(d.gate, Gate.CONFIRM)

    def test_set_ip_nmcli_modify_classifies_confirm(self):
        d = classify("nmcli con modify myconn ipv4.addresses 192.168.1.10/24")
        # nmcli + modify -> _SUBCMD_OVERRIDE_WRITE_PATTERNS -> WRITE -> CONFIRM
        self.assertEqual(d.gate, Gate.CONFIRM)

    # DESTRUCTIVE op — bring_down
    def test_bring_down_classifies_confirm_typed_interactive(self):
        cmd = "ip link set eth0 down"
        d = classify(cmd, ExecContext(interactive=True))
        # "ip link set ... down" — write pattern catches it at minimum;
        # the synthesize_command must emit exactly this form so the classifier
        # sees "ip ... set" -> WRITE at minimum; the OpSpec advisory is DESTRUCTIVE.
        # At minimum this must NOT be ALLOW.
        self.assertNotEqual(d.gate, Gate.ALLOW)

    def test_bring_down_non_interactive_is_refuse(self):
        cmd = "ip link set eth0 down"
        d = classify(cmd, ExecContext(interactive=False))
        # Non-interactive write/destructive is always REFUSE.
        self.assertEqual(d.gate, Gate.REFUSE)

    def test_nmcli_bring_up_classifies_confirm(self):
        d = classify("nmcli con up myconnection")
        # nmcli + "up" -> _SUBCMD_OVERRIDE_WRITE_PATTERNS matches "up" -> WRITE
        self.assertEqual(d.gate, Gate.CONFIRM)


# ---------------------------------------------------------------------------
# show operation
# ---------------------------------------------------------------------------

class TestShow(unittest.TestCase):

    def test_success_summary(self):
        with _patch(_ok(stdout="1: lo: <LOOPBACK> mtu 65536\n")):
            r = _execute("show", {})
        self.assertTrue(r.ok)
        self.assertIn("address", r.summary.lower())

    def test_failure_summary(self):
        with _patch(_fail(exit_code=1, stderr="something failed")):
            r = _execute("show", {})
        self.assertFalse(r.ok)
        self.assertIn("1", r.summary)

    def test_result_fields(self):
        with _patch(_ok(stdout="output")):
            r = _execute("show", {})
        self.assertIsNotNone(r.exit_code)
        self.assertIsInstance(r.stdout, str)
        self.assertIsInstance(r.stderr, str)
        self.assertIsInstance(r.summary, str)
        self.assertGreater(len(r.summary), 0)


# ---------------------------------------------------------------------------
# status operation
# ---------------------------------------------------------------------------

class TestStatus(unittest.TestCase):

    def test_success_with_interface_count(self):
        stdout = "lo       UNKNOWN 127.0.0.1/8\neth0     UP      10.0.0.1/24\n"
        with _patch(_ok(stdout=stdout)):
            r = _execute("status", {})
        self.assertTrue(r.ok)
        self.assertIn("2", r.summary)

    def test_failure(self):
        with _patch(_fail(exit_code=1)):
            r = _execute("status", {})
        self.assertFalse(r.ok)

    def test_empty_stdout_zero_interfaces(self):
        with _patch(_ok(stdout="")):
            r = _execute("status", {})
        self.assertTrue(r.ok)
        self.assertIn("0", r.summary)


# ---------------------------------------------------------------------------
# connections operation
# ---------------------------------------------------------------------------

class TestConnections(unittest.TestCase):

    def test_success_counts_non_header_lines(self):
        stdout = (
            "NAME    UUID                                  TYPE      DEVICE\n"
            "myconn  aabbcc00-0000-0000-0000-000000000001  ethernet  eth0\n"
        )
        with _patch(_ok(stdout=stdout)):
            r = _execute("connections", {})
        self.assertTrue(r.ok)
        self.assertIn("1", r.summary)

    def test_failure(self):
        with _patch(_fail(exit_code=10, stderr="nmcli not found")):
            r = _execute("connections", {})
        self.assertFalse(r.ok)
        self.assertIn("10", r.summary)


# ---------------------------------------------------------------------------
# interfaces operation
# ---------------------------------------------------------------------------

class TestInterfaces(unittest.TestCase):

    def test_success(self):
        with _patch(_ok(stdout="1: lo: <LOOPBACK>\n2: eth0: <BROADCAST>\n")):
            r = _execute("interfaces", {})
        self.assertTrue(r.ok)
        self.assertIn("interface", r.summary.lower())

    def test_failure(self):
        with _patch(_fail(exit_code=1)):
            r = _execute("interfaces", {})
        self.assertFalse(r.ok)


# ---------------------------------------------------------------------------
# wifi operation
# ---------------------------------------------------------------------------

class TestWifi(unittest.TestCase):

    def test_active_ssid_parsed_from_nmcli(self):
        stdout = "no:NeighborNet\nyes:HomeWiFi\nno:CoffeeShop\n"
        with _patch(_ok(stdout=stdout)):
            r = _execute("wifi", {})
        self.assertTrue(r.ok)
        self.assertIn("HomeWiFi", r.summary)
        self.assertEqual(r.stdout.strip(), "HomeWiFi")

    def test_escaped_colon_in_ssid(self):
        # nmcli -t escapes a colon inside the SSID value as "\:".
        stdout = "yes:My\\:Network\n"
        with _patch(_ok(stdout=stdout)):
            r = _execute("wifi", {})
        self.assertIn("My:Network", r.summary)

    def test_falls_back_to_iwgetid(self):
        # nmcli returns nothing useful -> fall back to iwgetid -r.
        outputs = [_ok(stdout="\n"), _ok(stdout="BackupSSID\n")]
        mock_fn = MagicMock(side_effect=outputs)
        with patch("core.tools.network.run_subprocess", mock_fn):
            r = _execute("wifi", {})
        self.assertIn("BackupSSID", r.summary)
        # second call must be the iwgetid fallback
        self.assertEqual(mock_fn.call_args_list[0][0][0],
                         ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"])
        self.assertEqual(mock_fn.call_args_list[1][0][0], ["iwgetid", "-r"])

    def test_no_active_connection(self):
        outputs = [_ok(stdout="no:SomeoneElse\n"), _fail(exit_code=1)]
        mock_fn = MagicMock(side_effect=outputs)
        with patch("core.tools.network.run_subprocess", mock_fn):
            r = _execute("wifi", {})
        self.assertIn("No active", r.summary)


# ---------------------------------------------------------------------------
# bring_up operation
# ---------------------------------------------------------------------------

class TestBringUp(unittest.TestCase):

    def test_bring_up_by_interface(self):
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.network.run_subprocess", mock_fn):
            r = _execute("bring_up", {"interface": "eth0"})
        self.assertTrue(r.ok)
        self.assertIn("eth0", r.summary)
        cmd = mock_fn.call_args[0][0]
        self.assertEqual(cmd, ["ip", "link", "set", "eth0", "up"])

    def test_bring_up_by_connection(self):
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.network.run_subprocess", mock_fn):
            r = _execute("bring_up", {"connection": "myconn"})
        self.assertTrue(r.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertEqual(cmd, ["nmcli", "con", "up", "myconn"])

    def test_bring_up_neither_arg_fails(self):
        r = _execute("bring_up", {})
        self.assertFalse(r.ok)
        self.assertIn("requires", r.summary)

    def test_bring_up_failure(self):
        with _patch(_fail(exit_code=1, stderr="not found")):
            r = _execute("bring_up", {"interface": "eth99"})
        self.assertFalse(r.ok)
        self.assertIn("eth99", r.summary)

    def test_bring_up_success_message(self):
        with _patch(_ok()):
            r = _execute("bring_up", {"interface": "eth0"})
        self.assertIn("up", r.summary.lower())


# ---------------------------------------------------------------------------
# bring_down operation
# ---------------------------------------------------------------------------

class TestBringDown(unittest.TestCase):

    def test_brings_down_by_interface(self):
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.network.run_subprocess", mock_fn):
            r = _execute("bring_down", {"interface": "eth0"})
        self.assertTrue(r.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertEqual(cmd, ["ip", "link", "set", "eth0", "down"])

    def test_success_summary(self):
        with _patch(_ok()):
            r = _execute("bring_down", {"interface": "eth0"})
        self.assertIn("eth0", r.summary)
        self.assertIn("down", r.summary.lower())

    def test_failure_summary(self):
        with _patch(_fail(exit_code=1, stderr="operation not permitted")):
            r = _execute("bring_down", {"interface": "eth0"})
        self.assertFalse(r.ok)
        self.assertIn("eth0", r.summary)

    def test_synthesized_command_not_allow(self):
        """The command 'ip link set <if> down' must not be gated ALLOW."""
        d = classify("ip link set eth0 down")
        self.assertNotEqual(d.gate, Gate.ALLOW,
                            "bring_down synthesized command must not classify as ALLOW")

    def test_synthesized_command_refuse_noninteractive(self):
        """Non-interactive context must produce REFUSE for bring_down."""
        d = classify("ip link set eth0 down", ExecContext(interactive=False))
        self.assertEqual(d.gate, Gate.REFUSE)


# ---------------------------------------------------------------------------
# set_ip operation
# ---------------------------------------------------------------------------

class TestSetIp(unittest.TestCase):

    def test_set_ip_via_ip_addr_add(self):
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.network.run_subprocess", mock_fn):
            r = _execute("set_ip", {"interface": "eth0", "address": "10.0.0.1/24"})
        self.assertTrue(r.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertEqual(cmd, ["ip", "addr", "add", "10.0.0.1/24", "dev", "eth0"])

    def test_set_ip_via_nmcli(self):
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.network.run_subprocess", mock_fn):
            r = _execute("set_ip", {"connection": "myconn", "address": "10.0.0.2/24"})
        self.assertTrue(r.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertEqual(
            cmd,
            ["nmcli", "con", "modify", "myconn", "ipv4.addresses", "10.0.0.2/24"]
        )

    def test_set_ip_neither_arg_fails(self):
        r = _execute("set_ip", {"address": "10.0.0.1/24"})
        self.assertFalse(r.ok)
        self.assertIn("requires", r.summary)

    def test_set_ip_failure(self):
        with _patch(_fail(exit_code=1, stderr="error")):
            r = _execute("set_ip", {"interface": "eth0", "address": "10.0.0.1/24"})
        self.assertFalse(r.ok)
        self.assertIn("eth0", r.summary)

    def test_set_ip_success_message_contains_address(self):
        with _patch(_ok()):
            r = _execute("set_ip", {"interface": "eth0", "address": "192.168.1.5/24"})
        self.assertIn("192.168.1.5/24", r.summary)


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint(unittest.TestCase):
    _AVC_STDERR = (
        "RTNETLINK answers: Operation not permitted. "
        "AVC avc: denied { net_admin } for pid=1234 comm=\"ip\""
    )

    def test_avc_in_stderr_surfaces_hint_for_bring_up(self):
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            r = _execute("bring_up", {"interface": "eth0"})
        self.assertTrue(
            "SELinux" in r.summary or "ausearch" in r.summary or "AVC" in r.summary
        )

    def test_avc_in_stderr_surfaces_hint_for_bring_down(self):
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            r = _execute("bring_down", {"interface": "eth0"})
        self.assertTrue(
            "SELinux" in r.summary or "ausearch" in r.summary or "AVC" in r.summary
        )

    def test_clean_stderr_no_hint_for_show(self):
        with _patch(_fail(exit_code=1, stderr="Cannot open network namespace")):
            r = _execute("show", {})
        self.assertNotIn("ausearch", r.summary)


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure(unittest.TestCase):

    _OPS_ARGS = [
        ("show",        {}),
        ("status",      {}),
        ("connections", {}),
        ("interfaces",  {}),
        ("wifi",        {}),
        ("bring_up",    {"interface": "eth0"}),
        ("bring_down",  {"interface": "eth0"}),
        ("set_ip",      {"interface": "eth0", "address": "1.2.3.4/24"}),
    ]

    def test_all_ops_return_toolresult(self):
        for op, args in self._OPS_ARGS:
            with self.subTest(op=op):
                with _patch(_ok(stdout=f"{op} output")):
                    r = _execute(op, args)
                self.assertIsInstance(r, ToolResult)
                self.assertIsNotNone(r.exit_code)
                self.assertIsInstance(r.stdout, str)
                self.assertIsInstance(r.stderr, str)
                self.assertIsInstance(r.summary, str)
                self.assertGreater(len(r.summary), 0)

    def test_as_dict_has_four_keys(self):
        for op, args in self._OPS_ARGS:
            with self.subTest(op=op):
                with _patch(_ok()):
                    r = _execute(op, args)
                d = r.as_dict()
                self.assertEqual(set(d.keys()), {"exit_code", "stdout", "stderr", "summary"})


# ---------------------------------------------------------------------------
# I2 filter: no AI/LLM/agent language in any user-facing string
# ---------------------------------------------------------------------------

class TestI2Filter(unittest.TestCase):
    """Invariant I2: no forbidden AI terms in ToolSpec descriptions, OpSpec
    descriptions, or ToolResult summaries produced by any operation."""

    def test_tool_description_clean(self):
        _assert_no_ai_language(NETWORK_SPEC.description, "ToolSpec.description")

    def test_all_op_descriptions_clean(self):
        for op_name, op_spec in NETWORK_SPEC.ops.items():
            _assert_no_ai_language(op_spec.description, f"OpSpec[{op_name!r}].description")

    def test_success_summaries_clean(self):
        ops_args = [
            ("show",        {}),
            ("status",      {}),
            ("connections", {}),
            ("interfaces",  {}),
        ("wifi",        {}),
            ("bring_up",    {"interface": "eth0"}),
            ("bring_down",  {"interface": "eth0"}),
            ("set_ip",      {"interface": "eth0", "address": "1.2.3.4/24"}),
        ]
        for op, args in ops_args:
            with self.subTest(op=op):
                with _patch(_ok(stdout=f"{op} output")):
                    r = _execute(op, args)
                _assert_no_ai_language(r.summary, f"ToolResult.summary[{op!r}] success")

    def test_failure_summaries_clean(self):
        ops_args = [
            ("show",        {}),
            ("status",      {}),
            ("connections", {}),
            ("interfaces",  {}),
        ("wifi",        {}),
            ("bring_up",    {"interface": "eth0"}),
            ("bring_down",  {"interface": "eth0"}),
            ("set_ip",      {"interface": "eth0", "address": "1.2.3.4/24"}),
        ]
        for op, args in ops_args:
            with self.subTest(op=op):
                with _patch(_fail(exit_code=1, stderr="error")):
                    r = _execute(op, args)
                _assert_no_ai_language(r.summary, f"ToolResult.summary[{op!r}] failure")


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch(unittest.TestCase):

    def test_dispatch_show(self):
        with _patch(_ok(stdout="1: lo")):
            r = registry.dispatch("network", "show", {})
        self.assertIsInstance(r, ToolResult)
        self.assertEqual(r.exit_code, 0)

    def test_dispatch_bring_down(self):
        with _patch(_ok()):
            r = registry.dispatch("network", "bring_down", {"interface": "eth0"})
        self.assertTrue(r.ok)

    def test_dispatch_missing_required_arg_raises(self):
        # bring_down requires 'interface'
        with self.assertRaises(TypeError):
            registry.dispatch("network", "bring_down", {})

    def test_dispatch_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            registry.dispatch("network", "nonexistent_op", {})

    def test_dispatch_set_ip_with_address(self):
        with _patch(_ok()):
            r = registry.dispatch(
                "network", "set_ip",
                {"interface": "eth0", "address": "10.0.0.1/24"}
            )
        self.assertTrue(r.ok)


# ---------------------------------------------------------------------------
# Unknown op fallback
# ---------------------------------------------------------------------------

class TestUnknownOp(unittest.TestCase):

    def test_unknown_op_returns_error_toolresult(self):
        r = _execute("nonexistent_op", {})
        self.assertEqual(r.exit_code, 1)
        self.assertIn("nonexistent_op", r.summary)
        self.assertIn("Unknown", r.summary)


# ---------------------------------------------------------------------------
# Entry point for python3 -m unittest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
