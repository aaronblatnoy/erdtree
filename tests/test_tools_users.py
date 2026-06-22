"""tests/test_tools_users.py — Unit tests for core/tools/users.py.

Stdlib unittest (pytest is not installed on this host). Every subprocess call
is mocked via unittest.mock.patch on ``core.tools.users.run_subprocess`` so no
real useradd/usermod/passwd/userdel/gpasswd process is launched.

Coverage
--------
  * ToolSpec self-registration in the module-level registry.
  * Permission classes: list/info READ; add/set_shell/add_to_group WRITE;
    lock/delete/remove_from_privgroup DESTRUCTIVE.
  * Each op produces a well-formed ToolResult (four fields, non-empty summary).
  * READ ops classify to ALLOW (no gate) via permissions.classify() on the
    faithful command line.
  * The faithful command line for each DESTRUCTIVE op classifies to
    DESTRUCTIVE -> CONFIRM_TYPED interactively, and REFUSE non-interactively.
  * The argv each op shells out is the expected command vector.
  * SELinux AVC hint surfaces when stderr looks like an AVC denial.
  * I2: every ToolSpec/OpSpec description AND every ToolResult.summary clears
    the canonical _FORBIDDEN_AI_TERMS filter imported from core/agent/prompt.py.

Run with::

    python3 -m unittest tests.test_tools_users
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

# Import the module to trigger self-registration in the module-level registry.
import core.tools.users  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import ExecContext, Gate, OpClass, classify
from core.agent.prompt import _AI_PATTERN, _FORBIDDEN_AI_TERMS
from core.tools import ToolResult, registry
from core.tools.users import USERS_SPEC, _execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok_result(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail_result(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    return patch("core.tools.users.run_subprocess", return_value=return_value)


# Faithful command lines the loop synthesizes for each op (the strings the
# hardened classifier actually sees). These are the load-bearing forms.
_READ_CMDS = {
    "list": "cat /etc/passwd",
    "info": "id deploy",
}
_WRITE_CMDS = {
    "add": "useradd deploy",
    "set_shell": "usermod -s /bin/bash deploy",
    "add_to_group": "usermod -aG docker deploy",
}
_DESTRUCTIVE_CMDS = {
    "lock": "usermod -L deploy",
    "delete": "userdel deploy",
    "remove_from_privgroup": "gpasswd -d deploy wheel",
}

_OP_ARGS = {
    "list": {},
    "info": {"user": "deploy"},
    "add": {"user": "deploy"},
    "set_shell": {"user": "deploy", "shell": "/bin/bash"},
    "add_to_group": {"user": "deploy", "group": "docker"},
    "lock": {"user": "deploy"},
    "delete": {"user": "deploy"},
    "remove_from_privgroup": {"user": "deploy"},
}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration(unittest.TestCase):
    def test_users_registered(self) -> None:
        self.assertIsNotNone(registry.get("users"))

    def test_spec_name(self) -> None:
        spec = registry.get("users")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.name, "users")

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("users")
        expected = {
            "list", "info", "add", "set_shell", "add_to_group",
            "lock", "delete", "remove_from_privgroup",
        }
        self.assertEqual(set(spec.ops.keys()), expected)


# ---------------------------------------------------------------------------
# Permission classes declared by the tool
# ---------------------------------------------------------------------------

class TestPermissionClasses(unittest.TestCase):
    def test_read_ops(self) -> None:
        for op in ("list", "info"):
            self.assertIs(registry.permission_class_for("users", op), OpClass.READ, op)

    def test_write_ops(self) -> None:
        for op in ("add", "set_shell", "add_to_group"):
            self.assertIs(registry.permission_class_for("users", op), OpClass.WRITE, op)

    def test_destructive_ops(self) -> None:
        for op in ("lock", "delete", "remove_from_privgroup"):
            self.assertIs(
                registry.permission_class_for("users", op), OpClass.DESTRUCTIVE, op
            )


# ---------------------------------------------------------------------------
# Permission gate integration (faithful command line -> classifier)
# ---------------------------------------------------------------------------

class TestPermissionGateIntegration(unittest.TestCase):
    """READ ops need no gate; DESTRUCTIVE ops require a typed word and are
    REFUSED non-interactively. This is the lockout keystone for this tool."""

    def test_read_ops_get_allow_gate(self) -> None:
        for op, cmd in _READ_CMDS.items():
            decision = classify(cmd)
            self.assertIs(decision.gate, Gate.ALLOW, f"{op}: {cmd}")
            self.assertTrue(decision.auto_ok, op)

    def test_write_ops_get_confirm_gate(self) -> None:
        for op, cmd in _WRITE_CMDS.items():
            decision = classify(cmd)
            self.assertIs(decision.gate, Gate.CONFIRM, f"{op}: {cmd}")
            self.assertFalse(decision.auto_ok, op)

    def test_destructive_ops_get_typed_gate_interactive(self) -> None:
        for op, cmd in _DESTRUCTIVE_CMDS.items():
            decision = classify(cmd, ExecContext(interactive=True))
            self.assertIs(decision.op_class, OpClass.DESTRUCTIVE, f"{op}: {cmd}")
            self.assertIs(decision.gate, Gate.CONFIRM_TYPED, f"{op}: {cmd}")
            self.assertFalse(decision.auto_ok, op)

    def test_destructive_ops_refused_non_interactive(self) -> None:
        for op, cmd in _DESTRUCTIVE_CMDS.items():
            decision = classify(cmd, ExecContext(interactive=False))
            self.assertIs(decision.gate, Gate.REFUSE, f"{op}: {cmd}")
            self.assertFalse(decision.auto_ok, op)


# ---------------------------------------------------------------------------
# Argv vectors: each op shells out the expected command vector
# ---------------------------------------------------------------------------

class TestCommandVectors(unittest.TestCase):
    def _argv_for(self, op: str, args: dict) -> list:
        mock_fn = MagicMock(return_value=_ok_result())
        with patch("core.tools.users.run_subprocess", mock_fn):
            _execute(op, args)
        return mock_fn.call_args[0][0]

    def test_list_argv(self) -> None:
        self.assertEqual(self._argv_for("list", {}), ["cat", "/etc/passwd"])

    def test_info_argv(self) -> None:
        self.assertEqual(
            self._argv_for("info", {"user": "deploy"}), ["id", "deploy"]
        )

    def test_add_argv(self) -> None:
        self.assertEqual(self._argv_for("add", {"user": "deploy"}), ["useradd", "deploy"])

    def test_set_shell_argv(self) -> None:
        self.assertEqual(
            self._argv_for("set_shell", {"user": "deploy", "shell": "/bin/bash"}),
            ["usermod", "-s", "/bin/bash", "deploy"],
        )

    def test_add_to_group_argv(self) -> None:
        self.assertEqual(
            self._argv_for("add_to_group", {"user": "deploy", "group": "docker"}),
            ["usermod", "-aG", "docker", "deploy"],
        )

    def test_lock_argv(self) -> None:
        self.assertEqual(
            self._argv_for("lock", {"user": "deploy"}), ["usermod", "-L", "deploy"]
        )

    def test_delete_argv(self) -> None:
        self.assertEqual(
            self._argv_for("delete", {"user": "deploy"}), ["userdel", "deploy"]
        )

    def test_remove_from_privgroup_argv(self) -> None:
        self.assertEqual(
            self._argv_for("remove_from_privgroup", {"user": "deploy"}),
            ["gpasswd", "-d", "deploy", "wheel"],
        )


# ---------------------------------------------------------------------------
# ToolResult structure + outcomes
# ---------------------------------------------------------------------------

class TestToolResultStructure(unittest.TestCase):
    def test_result_has_required_fields(self) -> None:
        for op, args in _OP_ARGS.items():
            with _patch_run(_ok_result(stdout=f"{op} output\n")):
                result = _execute(op, args)
            self.assertIsInstance(result, ToolResult, op)
            self.assertIsNotNone(result.exit_code, op)
            self.assertIsInstance(result.stdout, str, op)
            self.assertIsInstance(result.stderr, str, op)
            self.assertIsInstance(result.summary, str, op)
            self.assertGreater(len(result.summary), 0, op)

    def test_as_dict_has_four_keys(self) -> None:
        for op, args in _OP_ARGS.items():
            with _patch_run(_ok_result()):
                result = _execute(op, args)
            self.assertEqual(
                set(result.as_dict().keys()),
                {"exit_code", "stdout", "stderr", "summary"},
                op,
            )

    def test_success_summaries(self) -> None:
        cases = [
            ("list", _ok_result(stdout="root:x:0:0\ndeploy:x:1000:1000\n"), "Listed"),
            ("info", _ok_result(stdout="deploy:x:1000:1000:::/bin/bash\n"), "Found"),
            ("add", _ok_result(), "created"),
            ("set_shell", _ok_result(), "shell"),
            ("add_to_group", _ok_result(), "added"),
            ("lock", _ok_result(), "locked"),
            ("delete", _ok_result(), "deleted"),
            ("remove_from_privgroup", _ok_result(), "removed"),
        ]
        for op, ret, token in cases:
            with _patch_run(ret):
                result = _execute(op, _OP_ARGS[op])
            self.assertTrue(result.ok, op)
            self.assertIn(token.lower(), result.summary.lower(), op)

    def test_failure_summaries(self) -> None:
        for op, args in _OP_ARGS.items():
            with _patch_run(_fail_result(exit_code=1, stderr="boom")):
                result = _execute(op, args)
            self.assertFalse(result.ok, op)
            self.assertGreater(len(result.summary), 0, op)

    def test_unknown_op_returns_result(self) -> None:
        result = _execute("nonexistent", {})
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.exit_code, 1)


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint(unittest.TestCase):
    def test_avc_in_stderr_surfaces_hint(self) -> None:
        avc = 'AVC avc: denied { setattr } for pid=1234 comm="usermod"'
        for op, args in _OP_ARGS.items():
            with _patch_run(_fail_result(exit_code=1, stderr=avc)):
                result = _execute(op, args)
            self.assertTrue(
                "SELinux" in result.summary or "ausearch" in result.summary, op
            )

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail_result(exit_code=1, stderr="user does not exist")):
            result = _execute("delete", {"user": "ghost"})
        self.assertNotIn("ausearch", result.summary)


# ---------------------------------------------------------------------------
# I2: no AI/LLM/model/agent language anywhere user-facing
# ---------------------------------------------------------------------------

class TestNoAILanguage(unittest.TestCase):
    """Enforce I2 with the CANONICAL forbidden-term filter from prompt.py."""

    def _assert_clean(self, text: str, label: str) -> None:
        match = _AI_PATTERN.search(text)
        self.assertIsNone(
            match,
            f"I2 violation in {label}: forbidden term "
            f"{match.group(0)!r} in {text!r}" if match else "",
        )

    def test_forbidden_terms_imported(self) -> None:
        # Sanity: we imported the canonical list, not a local copy.
        self.assertIn("model", _FORBIDDEN_AI_TERMS)
        self.assertIn("agent", _FORBIDDEN_AI_TERMS)

    def test_tool_and_op_descriptions_clean(self) -> None:
        self._assert_clean(USERS_SPEC.description, "ToolSpec.description")
        for op_name, op in USERS_SPEC.ops.items():
            self._assert_clean(op.description, f"OpSpec[{op_name}].description")
            for arg in op.args:
                self._assert_clean(arg.description, f"ArgSpec[{op_name}.{arg.name}]")

    def test_success_summaries_clean(self) -> None:
        for op, args in _OP_ARGS.items():
            with _patch_run(_ok_result(stdout="x\n")):
                result = _execute(op, args)
            self._assert_clean(result.summary, f"success summary[{op}]")

    def test_failure_summaries_clean(self) -> None:
        for op, args in _OP_ARGS.items():
            with _patch_run(_fail_result(exit_code=1, stderr="error")):
                result = _execute(op, args)
            self._assert_clean(result.summary, f"failure summary[{op}]")

    def test_selinux_hint_summaries_clean(self) -> None:
        avc = 'AVC avc: denied { setattr } for pid=1 comm="usermod"'
        for op, args in _OP_ARGS.items():
            with _patch_run(_fail_result(exit_code=1, stderr=avc)):
                result = _execute(op, args)
            self._assert_clean(result.summary, f"selinux summary[{op}]")


# ---------------------------------------------------------------------------
# Registry dispatch integration (the loop's path)
# ---------------------------------------------------------------------------

class TestRegistryDispatch(unittest.TestCase):
    def test_dispatch_list(self) -> None:
        with _patch_run(_ok_result(stdout="root:x:0:0\n")):
            result = registry.dispatch("users", "list", {})
        self.assertTrue(result.ok)

    def test_dispatch_lock(self) -> None:
        with _patch_run(_ok_result()):
            result = registry.dispatch("users", "lock", {"user": "deploy"})
        self.assertTrue(result.ok)

    def test_dispatch_missing_user_arg_raises(self) -> None:
        with self.assertRaises(TypeError):
            registry.dispatch("users", "info", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with self.assertRaises(ValueError):
            registry.dispatch("users", "nope", {"user": "x"})


if __name__ == "__main__":
    unittest.main()
