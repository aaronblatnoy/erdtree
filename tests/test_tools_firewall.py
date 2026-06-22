"""tests/test_tools_firewall.py — Unit tests for core/tools/firewall.py.

stdlib unittest (pytest is absent on this host). Run with:

    python3 -m unittest tests.test_tools_firewall

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on this host without firewall-cmd present.

Coverage
--------
  * ToolSpec self-registration in the module-level registry (registry.get).
  * Permission classes: list/get_zones/query are READ; add/remove/reload/
    set_default_zone are WRITE; panic_on is DESTRUCTIVE.
  * Each operation produces a well-formed ToolResult (four fields, non-empty
    summary).
  * Successful exit (0) -> ok=True; non-zero exit -> ok=False with a failure
    summary.
  * READ ops need no gate: classify() of the faithful firewall-cmd READ command
    returns ALLOW / auto_ok.
  * The lockout op (panic_on) classifies DESTRUCTIVE -> CONFIRM_TYPED, and
    REFUSE under a non-interactive ExecContext.
  * SELinux AVC hint is surfaced in the summary when stderr looks like an AVC
    denial.
  * I2: every OpSpec/ToolSpec description AND every ToolResult.summary clears
    the canonical _FORBIDDEN_AI_TERMS filter imported from core/agent/prompt.py.

Mocking strategy
----------------
  We patch ``core.tools.firewall.run_subprocess`` (the function in the
  firewall module's namespace) to return controlled ToolResult fixtures, so no
  real process is launched.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

# Import the module to trigger self-registration in the module-level registry.
import core.tools.firewall  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import ExecContext, Gate, OpClass, classify
from core.agent.prompt import _AI_PATTERN
from core.tools import ToolResult, registry
from core.tools.firewall import FIREWALL_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.firewall.run_subprocess."""
    return patch("core.tools.firewall.run_subprocess", return_value=return_value)


# Representative args per op so each can be exercised generically.
_ALL_OPS_ARGS: dict[str, dict] = {
    "list": {"zone": "public"},
    "get_zones": {},
    "query": {"service": "ssh", "zone": "public"},
    "add_service": {"service": "http", "zone": "public"},
    "add_port": {"port": "8080/tcp", "zone": "public"},
    "remove_service": {"service": "http", "zone": "public"},
    "remove_port": {"port": "8080/tcp", "zone": "public"},
    "reload": {},
    "set_default_zone": {"zone": "public"},
    "panic_on": {},
}

_READ_OPS = ("list", "get_zones", "query")
_WRITE_OPS = (
    "add_service",
    "add_port",
    "remove_service",
    "remove_port",
    "reload",
    "set_default_zone",
)
_DESTRUCTIVE_OPS = ("panic_on",)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration(unittest.TestCase):
    def test_firewall_registered(self) -> None:
        self.assertIsNotNone(registry.get("firewall"))

    def test_spec_name(self) -> None:
        spec = registry.get("firewall")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.name, "firewall")

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("firewall")
        self.assertIsNotNone(spec)
        expected = set(_ALL_OPS_ARGS.keys())
        self.assertEqual(set(spec.ops.keys()), expected)


# ---------------------------------------------------------------------------
# Permission classes (the OpSpec-declared, advisory class)
# ---------------------------------------------------------------------------

class TestPermissionClasses(unittest.TestCase):
    def test_read_ops(self) -> None:
        for op in _READ_OPS:
            with self.subTest(op=op):
                self.assertIs(registry.permission_class_for("firewall", op), OpClass.READ)

    def test_write_ops(self) -> None:
        for op in _WRITE_OPS:
            with self.subTest(op=op):
                self.assertIs(registry.permission_class_for("firewall", op), OpClass.WRITE)

    def test_destructive_ops(self) -> None:
        for op in _DESTRUCTIVE_OPS:
            with self.subTest(op=op):
                self.assertIs(
                    registry.permission_class_for("firewall", op), OpClass.DESTRUCTIVE
                )


# ---------------------------------------------------------------------------
# Classifier integration — the gate that actually fires (synthesized strings)
# ---------------------------------------------------------------------------

class TestClassifierIntegration(unittest.TestCase):
    """The OpSpec class is advisory; the EXISTING hardened classifier resolves
    the real gate on the faithful firewall-cmd command line. READ ops need no
    gate; panic_on is DESTRUCTIVE and REFUSE non-interactively."""

    def test_read_ops_get_allow_gate(self) -> None:
        cmds = {
            "list": "firewall-cmd --zone public --list-all",
            "get_zones": "firewall-cmd --get-zones",
            "query": "firewall-cmd --zone public --query-service ssh",
        }
        for op, cmd in cmds.items():
            with self.subTest(op=op):
                decision = classify(cmd)
                self.assertIs(decision.gate, Gate.ALLOW)
                self.assertTrue(decision.auto_ok)

    def test_panic_on_is_destructive_confirm_typed(self) -> None:
        decision = classify("firewall-cmd --panic-on")
        self.assertIs(decision.op_class, OpClass.DESTRUCTIVE)
        self.assertIs(decision.gate, Gate.CONFIRM_TYPED)
        self.assertFalse(decision.auto_ok)

    def test_panic_on_refused_non_interactive(self) -> None:
        decision = classify(
            "firewall-cmd --panic-on", ExecContext(interactive=False)
        )
        self.assertIs(decision.gate, Gate.REFUSE)
        self.assertFalse(decision.auto_ok)


# ---------------------------------------------------------------------------
# Per-op execution: success and failure
# ---------------------------------------------------------------------------

class TestExecutionSuccess(unittest.TestCase):
    def test_list_success(self) -> None:
        with _patch_run(_ok_result(stdout="public (active)\n  services: ssh dhcpv6-client")):
            result = _execute("list", {"zone": "public"})
        self.assertTrue(result.ok)
        self.assertIn("public", result.summary)

    def test_get_zones_counts(self) -> None:
        with _patch_run(_ok_result(stdout="public internal dmz")):
            result = _execute("get_zones", {})
        self.assertTrue(result.ok)
        self.assertIn("3", result.summary)

    def test_query_allowed(self) -> None:
        with _patch_run(_ok_result(stdout="yes")):
            result = _execute("query", {"service": "ssh", "zone": "public"})
        self.assertTrue(result.ok)
        self.assertIn("ssh", result.summary)
        self.assertIn("allowed", result.summary.lower())

    def test_query_not_allowed(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stdout="no")):
            result = _execute("query", {"service": "telnet", "zone": "public"})
        self.assertFalse(result.ok)
        self.assertIn("telnet", result.summary)

    def test_add_service_success(self) -> None:
        with _patch_run(_ok_result(stdout="success")):
            result = _execute("add_service", {"service": "http", "zone": "public"})
        self.assertTrue(result.ok)
        self.assertIn("http", result.summary)

    def test_add_port_success(self) -> None:
        with _patch_run(_ok_result(stdout="success")):
            result = _execute("add_port", {"port": "8080/tcp", "zone": "public"})
        self.assertTrue(result.ok)
        self.assertIn("8080/tcp", result.summary)

    def test_remove_service_success(self) -> None:
        with _patch_run(_ok_result(stdout="success")):
            result = _execute("remove_service", {"service": "http", "zone": "public"})
        self.assertTrue(result.ok)
        self.assertIn("http", result.summary)

    def test_remove_port_success(self) -> None:
        with _patch_run(_ok_result(stdout="success")):
            result = _execute("remove_port", {"port": "8080/tcp", "zone": "public"})
        self.assertTrue(result.ok)
        self.assertIn("8080/tcp", result.summary)

    def test_reload_success(self) -> None:
        with _patch_run(_ok_result(stdout="success")):
            result = _execute("reload", {})
        self.assertTrue(result.ok)
        self.assertIn("reload", result.summary.lower())

    def test_set_default_zone_success(self) -> None:
        with _patch_run(_ok_result(stdout="success")):
            result = _execute("set_default_zone", {"zone": "internal"})
        self.assertTrue(result.ok)
        self.assertIn("internal", result.summary)

    def test_panic_on_success(self) -> None:
        with _patch_run(_ok_result(stdout="success")):
            result = _execute("panic_on", {})
        self.assertTrue(result.ok)
        self.assertIn("panic", result.summary.lower())


class TestExecutionFailure(unittest.TestCase):
    def test_failure_propagates_exit_code(self) -> None:
        for op, args in _ALL_OPS_ARGS.items():
            with self.subTest(op=op):
                with _patch_run(_fail_result(exit_code=2, stderr="firewalld is not running")):
                    result = _execute(op, args)
                # query maps exit!=0 to "not allowed" (ok=False) too; all non-zero.
                self.assertFalse(result.ok)
                self.assertEqual(result.exit_code, 2)


# ---------------------------------------------------------------------------
# Command vector faithfulness — the tool shells out via run_subprocess only
# ---------------------------------------------------------------------------

class TestCommandVectors(unittest.TestCase):
    def _captured_cmd(self, op: str, args: dict) -> list[str]:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.firewall.run_subprocess", mock_fn):
            _execute(op, args)
        return mock_fn.call_args[0][0]

    def test_panic_on_emits_panic_flag(self) -> None:
        cmd = self._captured_cmd("panic_on", {})
        self.assertEqual(cmd, ["firewall-cmd", "--panic-on"])

    def test_set_default_zone_emits_set_flag(self) -> None:
        cmd = self._captured_cmd("set_default_zone", {"zone": "internal"})
        self.assertEqual(cmd, ["firewall-cmd", "--set-default-zone", "internal"])

    def test_add_port_emits_add_port_flag(self) -> None:
        cmd = self._captured_cmd("add_port", {"port": "8080/tcp", "zone": "public"})
        self.assertIn("--add-port", cmd)
        self.assertIn("8080/tcp", cmd)

    def test_list_without_zone_omits_zone_flag(self) -> None:
        cmd = self._captured_cmd("list", {})
        self.assertNotIn("--zone", cmd)
        self.assertIn("--list-all", cmd)

    def test_every_command_starts_with_firewall_cmd(self) -> None:
        for op, args in _ALL_OPS_ARGS.items():
            with self.subTest(op=op):
                cmd = self._captured_cmd(op, args)
                self.assertEqual(cmd[0], "firewall-cmd")


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint(unittest.TestCase):
    _AVC_STDERR = (
        "Error: COMMAND_FAILED: "
        "AVC avc: denied { write } for pid=999 comm=\"firewall-cmd\""
    )

    def test_avc_denial_surfaces_hint(self) -> None:
        for op, args in _ALL_OPS_ARGS.items():
            with self.subTest(op=op):
                with _patch_run(_fail_result(exit_code=1, stderr=self._AVC_STDERR)):
                    result = _execute(op, args)
                self.assertTrue(
                    "SELinux" in result.summary or "ausearch" in result.summary,
                    f"missing SELinux hint for op={op}: {result.summary!r}",
                )

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="Error: INVALID_ZONE")):
            result = _execute("list", {"zone": "ghost"})
        self.assertNotIn("ausearch", result.summary)


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure(unittest.TestCase):
    def test_result_has_required_fields(self) -> None:
        for op, args in _ALL_OPS_ARGS.items():
            with self.subTest(op=op):
                with _patch_run(_ok_result(stdout=f"{op} output")):
                    result = _execute(op, args)
                self.assertIsInstance(result, ToolResult)
                self.assertIsNotNone(result.exit_code)
                self.assertIsInstance(result.stdout, str)
                self.assertIsInstance(result.stderr, str)
                self.assertIsInstance(result.summary, str)
                self.assertGreater(len(result.summary), 0)

    def test_as_dict_has_four_keys(self) -> None:
        for op, args in _ALL_OPS_ARGS.items():
            with self.subTest(op=op):
                with _patch_run(_ok_result()):
                    result = _execute(op, args)
                self.assertEqual(
                    set(result.as_dict().keys()),
                    {"exit_code", "stdout", "stderr", "summary"},
                )


# ---------------------------------------------------------------------------
# Registry dispatch integration (the router path)
# ---------------------------------------------------------------------------

class TestRegistryDispatch(unittest.TestCase):
    def test_dispatch_list(self) -> None:
        with _patch_run(_ok_result(stdout="public")):
            result = registry.dispatch("firewall", "list", {"zone": "public"})
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.exit_code, 0)

    def test_dispatch_panic_on(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("firewall", "panic_on", {})
        self.assertTrue(result.ok)

    def test_dispatch_missing_required_arg_raises(self) -> None:
        with self.assertRaises(TypeError):
            registry.dispatch("firewall", "add_service", {"zone": "public"})

    def test_dispatch_unknown_op_raises(self) -> None:
        with self.assertRaises(ValueError):
            registry.dispatch("firewall", "nonexistent_op", {})


# ---------------------------------------------------------------------------
# I2: no AI/LLM/model/agent language anywhere user-facing
# ---------------------------------------------------------------------------

class TestNoAILanguage(unittest.TestCase):
    """Invariant I2 — enforced with the CANONICAL filter imported from
    core/agent/prompt.py rather than a re-listed local term set."""

    def _assert_clean(self, text: str, label: str) -> None:
        match = _AI_PATTERN.search(text)
        self.assertIsNone(
            match,
            f"I2 violation in {label}: forbidden term "
            f"{match.group()!r} in {text!r}" if match else "",
        )

    def test_spec_description_clean(self) -> None:
        self._assert_clean(FIREWALL_SPEC.description, "firewall ToolSpec.description")

    def test_op_descriptions_clean(self) -> None:
        for name, op in FIREWALL_SPEC.ops.items():
            with self.subTest(op=name):
                self._assert_clean(op.description, f"op[{name}].description")

    def test_arg_descriptions_clean(self) -> None:
        for name, op in FIREWALL_SPEC.ops.items():
            for arg in op.args:
                with self.subTest(op=name, arg=arg.name):
                    self._assert_clean(arg.description, f"op[{name}].arg[{arg.name}]")

    def test_success_summaries_clean(self) -> None:
        for op, args in _ALL_OPS_ARGS.items():
            with self.subTest(op=op):
                with _patch_run(_ok_result(stdout="public internal dmz")):
                    result = _execute(op, args)
                self._assert_clean(result.summary, f"success summary[{op}]")

    def test_failure_summaries_clean(self) -> None:
        for op, args in _ALL_OPS_ARGS.items():
            with self.subTest(op=op):
                with _patch_run(_fail_result(exit_code=1, stderr="boom")):
                    result = _execute(op, args)
                self._assert_clean(result.summary, f"failure summary[{op}]")

    def test_selinux_hint_summary_clean(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="AVC avc: denied { write }")):
            result = _execute("add_service", {"service": "http", "zone": "public"})
        self._assert_clean(result.summary, "selinux-hint summary")


if __name__ == "__main__":
    unittest.main()
