"""tests/test_tools_files.py — Unit tests for core/tools/files.py.

All subprocess calls are mocked via unittest.mock.patch so no real process
runs on the build host (ls/stat/cat/find/cp/mv/rm/mkdir/chmod/chown/tee are
never executed).

Coverage
--------
  * ToolSpec self-registers into the module-level registry at import time.
  * registry.get("files") is not None after import.
  * READ ops (list, read, stat, find) declare permission_class=READ.
  * WRITE ops (copy, move, mkdir, chmod, chown, write, remove) declare WRITE.
  * Each op returns a well-formed ToolResult (exit_code, stdout, stderr, summary).
  * Successful ops (exit_code=0) -> ok=True, descriptive summary.
  * Failed ops (exit_code=1) -> ok=False, failure summary.
  * read: lines argument clamped to [1, 1000]; default 200.
  * read: output truncated at the line cap; summary notes truncation.
  * SELinux AVC hint surfaced in summary when stderr contains AVC language.
  * I2 filter: no forbidden AI/LLM/model/agent terms in any description
    or summary string (imports _FORBIDDEN_AI_TERMS from core.agent.prompt).
  * Unknown op returns exit_code=1 with descriptive summary.
  * READ ops produce Gate.ALLOW via permissions.classify on their command shapes.
  * remove with recursive=True -> command contains -r flag.
  * remove with force=True -> command contains -f flag.
  * find with name/type/maxdepth args -> correct flags in command.
  * copy with recursive=True -> command contains -r flag.

DEFERRED-TO-MOSSAD: live execution against real binaries on Rocky Linux 9.
"""

from __future__ import annotations

import re
import sys
import os
import unittest
from typing import Any
from unittest.mock import MagicMock, patch

# Ensure the repo root is on the path so imports resolve.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Importing files.py triggers self-registration in the module-level registry.
import core.tools.files  # noqa: F401  (side-effect: registry.register)
from core.tools.files import FILES_SPEC, _execute
from core.agent.permissions import Gate, OpClass, ExecContext, classify
from core.agent.prompt import _FORBIDDEN_AI_TERMS
from core.tools import ToolResult, registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(rv: ToolResult):
    """Patch core.tools.files.run_subprocess with a fixed return value."""
    return patch("core.tools.files.run_subprocess", return_value=rv)


def _patch_fn(fn: MagicMock):
    """Patch core.tools.files.run_subprocess with a MagicMock."""
    return patch("core.tools.files.run_subprocess", fn)


_AI_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in _FORBIDDEN_AI_TERMS) + r")\b",
    re.IGNORECASE,
)


def _check_i2(text: str, label: str = "string") -> None:
    """Assert no I2-forbidden terms appear in text."""
    m = _AI_PATTERN.search(text)
    if m:
        raise AssertionError(
            f"I2 violation in {label!r}: found forbidden term "
            f"{m.group()!r}: {text!r}"
        )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration(unittest.TestCase):
    def test_files_registered_in_registry(self):
        self.assertIsNotNone(registry.get("files"))

    def test_spec_name(self):
        spec = registry.get("files")
        self.assertEqual(spec.name, "files")

    def test_all_expected_ops_present(self):
        spec = registry.get("files")
        expected = {
            "list", "read", "stat", "find",
            "copy", "move", "mkdir", "chmod", "chown", "write", "remove",
        }
        self.assertEqual(set(spec.ops.keys()), expected)


# ---------------------------------------------------------------------------
# Permission classes declared in ToolSpec
# ---------------------------------------------------------------------------

class TestPermissionClasses(unittest.TestCase):
    def test_read_ops_declared_read(self):
        for op in ("list", "read", "stat", "find"):
            with self.subTest(op=op):
                cls = registry.permission_class_for("files", op)
                self.assertIs(cls, OpClass.READ, f"Expected READ for '{op}'")

    def test_write_ops_declared_write(self):
        for op in ("copy", "move", "mkdir", "chmod", "chown", "write", "remove"):
            with self.subTest(op=op):
                cls = registry.permission_class_for("files", op)
                self.assertIs(cls, OpClass.WRITE, f"Expected WRITE for '{op}'")


# ---------------------------------------------------------------------------
# READ ops gate to ALLOW via permissions.classify
# ---------------------------------------------------------------------------

class TestReadOpsGate(unittest.TestCase):
    """READ ops must classify as Gate.ALLOW through the real classifier."""

    def test_list_allows(self):
        d = classify("ls -lah /tmp")
        self.assertIs(d.gate, Gate.ALLOW)
        self.assertTrue(d.auto_ok)

    def test_read_allows(self):
        d = classify("cat /etc/hostname")
        self.assertIs(d.gate, Gate.ALLOW)

    def test_stat_allows(self):
        d = classify("stat /tmp/foo.txt")
        self.assertIs(d.gate, Gate.ALLOW)

    def test_find_allows(self):
        d = classify("find /tmp -name '*.log'")
        self.assertIs(d.gate, Gate.ALLOW)


# ---------------------------------------------------------------------------
# DESTRUCTIVE gate: rm -rf classifies DESTRUCTIVE -> CONFIRM_TYPED
# (and REFUSE non-interactively)
# ---------------------------------------------------------------------------

class TestRemoveDestructiveGate(unittest.TestCase):
    def test_rm_rf_is_destructive_interactive(self):
        d = classify("rm -rf /tmp/scratch", ExecContext(interactive=True))
        self.assertIs(d.op_class, OpClass.DESTRUCTIVE)
        self.assertIs(d.gate, Gate.CONFIRM_TYPED)

    def test_rm_rf_system_path_is_destructive(self):
        d = classify("rm -rf /etc/mydir", ExecContext(interactive=True))
        self.assertIs(d.op_class, OpClass.DESTRUCTIVE)

    def test_rm_rf_is_refused_non_interactive(self):
        d = classify("rm -rf /tmp/scratch", ExecContext(interactive=False))
        self.assertIs(d.gate, Gate.REFUSE)

    def test_plain_rm_is_write(self):
        d = classify("rm /tmp/foo.txt", ExecContext(interactive=True))
        self.assertIs(d.op_class, OpClass.WRITE)
        self.assertIs(d.gate, Gate.CONFIRM)


# ---------------------------------------------------------------------------
# ToolResult structure — all ops return well-formed results
# ---------------------------------------------------------------------------

class TestToolResultStructure(unittest.TestCase):
    _cases = [
        ("list",   {"path": "/tmp"}),
        ("read",   {"path": "/tmp/foo.txt"}),
        ("stat",   {"path": "/tmp/foo.txt"}),
        ("find",   {"path": "/tmp"}),
        ("copy",   {"src": "/tmp/a", "dst": "/tmp/b"}),
        ("move",   {"src": "/tmp/a", "dst": "/tmp/b"}),
        ("mkdir",  {"path": "/tmp/newdir"}),
        ("chmod",  {"mode": "755", "path": "/tmp/foo"}),
        ("chown",  {"owner": "root", "path": "/tmp/foo"}),
        ("write",  {"path": "/tmp/out.txt", "content": "hello"}),
        ("remove", {"path": "/tmp/foo.txt"}),
    ]

    def test_result_has_required_fields(self):
        for op, args in self._cases:
            with self.subTest(op=op):
                with _patch(_ok(stdout=f"{op} output")):
                    result = _execute(op, args)
                self.assertIsInstance(result, ToolResult)
                self.assertIsNotNone(result.exit_code)
                self.assertIsInstance(result.stdout, str)
                self.assertIsInstance(result.stderr, str)
                self.assertIsInstance(result.summary, str)
                self.assertGreater(len(result.summary), 0)

    def test_as_dict_has_four_keys(self):
        with _patch(_ok()):
            result = _execute("list", {"path": "/tmp"})
        d = result.as_dict()
        self.assertEqual(set(d.keys()), {"exit_code", "stdout", "stderr", "summary"})

    def test_success_ok_true(self):
        with _patch(_ok()):
            result = _execute("stat", {"path": "/tmp/x"})
        self.assertTrue(result.ok)

    def test_failure_ok_false(self):
        with _patch(_fail(exit_code=1)):
            result = _execute("stat", {"path": "/nonexistent"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# list operation
# ---------------------------------------------------------------------------

class TestList(unittest.TestCase):
    def test_success_summary_mentions_path(self):
        with _patch(_ok(stdout="total 4\ndrwxr-xr-x 2 root root 40 Jan 1 00:00 .\n")):
            result = _execute("list", {"path": "/tmp"})
        self.assertTrue(result.ok)
        self.assertIn("/tmp", result.summary)

    def test_default_path_is_dot(self):
        mock_fn = MagicMock(return_value=_ok(stdout=".\n"))
        with _patch_fn(mock_fn):
            _execute("list", {})
        cmd = mock_fn.call_args[0][0]
        self.assertIn(".", cmd)

    def test_failure_summary(self):
        with _patch(_fail(exit_code=2, stderr="No such file")):
            result = _execute("list", {"path": "/no/such/dir"})
        self.assertFalse(result.ok)
        self.assertIn("/no/such/dir", result.summary)

    def test_list_uses_tree_depth_2(self):
        # "file structure" should be a tree, not a flat ls -lah.
        mock_fn = MagicMock(return_value=_ok(stdout=".\n└── README.txt\n"))
        with _patch_fn(mock_fn):
            _execute("list", {"path": "/root"})
        cmd = mock_fn.call_args[0][0]
        self.assertEqual(cmd[0], "tree")
        self.assertIn("-L", cmd)
        self.assertIn("2", cmd)
        self.assertIn("/root", cmd)

    def test_list_falls_back_to_ls_when_tree_absent(self):
        # If `tree` is not installed (exit 127), fall back to ls -lah so a
        # listing always works on a bare host.
        calls = []

        def fake(cmd, *a, **k):
            calls.append(cmd)
            if cmd[0] == "tree":
                return ToolResult(exit_code=127, stdout="", stderr="not found", summary="")
            return _ok(stdout="total 0\n-rw-r--r-- 1 root root 0 README.txt\n")

        with _patch_fn(MagicMock(side_effect=fake)):
            result = _execute("list", {"path": "."})
        self.assertEqual(calls[0][0], "tree")
        self.assertEqual(calls[1][0], "ls")   # fell back
        self.assertTrue(result.ok)


# ---------------------------------------------------------------------------
# read operation
# ---------------------------------------------------------------------------

class TestRead(unittest.TestCase):
    def test_success_summary(self):
        content = "line1\nline2\nline3\n"
        with _patch(_ok(stdout=content)):
            result = _execute("read", {"path": "/tmp/foo.txt"})
        self.assertTrue(result.ok)
        self.assertIn("/tmp/foo.txt", result.summary)

    def test_default_line_cap_applied(self):
        # Generate content exceeding the default cap.
        content = "\n".join(f"line{i}" for i in range(2000)) + "\n"
        with _patch(_ok(stdout=content)):
            result = _execute("read", {"path": "/tmp/big.txt"})
        # Default cap is 200; output must be truncated.
        actual_lines = result.stdout.count("\n")
        self.assertLessEqual(actual_lines, 200)
        self.assertIn("truncated", result.summary)

    def test_custom_line_cap(self):
        content = "\n".join(f"line{i}" for i in range(500)) + "\n"
        with _patch(_ok(stdout=content)):
            result = _execute("read", {"path": "/tmp/big.txt", "lines": 10})
        actual_lines = len(result.stdout.splitlines())
        self.assertLessEqual(actual_lines, 10)

    def test_lines_clamped_to_max(self):
        content = "\n".join(f"x{i}" for i in range(2000)) + "\n"
        with _patch(_ok(stdout=content)):
            result = _execute("read", {"path": "/tmp/x.txt", "lines": 99999})
        actual_lines = len(result.stdout.splitlines())
        self.assertLessEqual(actual_lines, 1000)

    def test_lines_clamped_to_min(self):
        content = "a\nb\nc\n"
        with _patch(_ok(stdout=content)):
            result = _execute("read", {"path": "/tmp/x.txt", "lines": 0})
        actual_lines = len(result.stdout.splitlines())
        self.assertGreaterEqual(actual_lines, 1)

    def test_failure_summary(self):
        with _patch(_fail(exit_code=1, stderr="Permission denied")):
            result = _execute("read", {"path": "/etc/shadow"})
        self.assertFalse(result.ok)
        self.assertIn("/etc/shadow", result.summary)


# ---------------------------------------------------------------------------
# stat operation
# ---------------------------------------------------------------------------

class TestStat(unittest.TestCase):
    def test_success(self):
        stat_out = "  File: /tmp/foo\n  Size: 100\n"
        with _patch(_ok(stdout=stat_out)):
            result = _execute("stat", {"path": "/tmp/foo"})
        self.assertTrue(result.ok)
        self.assertIn("/tmp/foo", result.summary)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="No such file or directory")):
            result = _execute("stat", {"path": "/no/such"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# find operation
# ---------------------------------------------------------------------------

class TestFind(unittest.TestCase):
    def test_success_summary_mentions_count(self):
        output = "/tmp/a.log\n/tmp/b.log\n"
        with _patch(_ok(stdout=output)):
            result = _execute("find", {"path": "/tmp", "name": "*.log"})
        self.assertTrue(result.ok)
        self.assertIn("2", result.summary)

    def test_name_flag_in_command(self):
        mock_fn = MagicMock(return_value=_ok(stdout=""))
        with _patch_fn(mock_fn):
            _execute("find", {"path": "/tmp", "name": "*.txt"})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-name", cmd)
        self.assertIn("*.txt", cmd)

    def test_type_flag_in_command(self):
        mock_fn = MagicMock(return_value=_ok(stdout=""))
        with _patch_fn(mock_fn):
            _execute("find", {"path": "/tmp", "type": "f"})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-type", cmd)
        self.assertIn("f", cmd)

    def test_maxdepth_flag_in_command(self):
        mock_fn = MagicMock(return_value=_ok(stdout=""))
        with _patch_fn(mock_fn):
            _execute("find", {"path": "/tmp", "maxdepth": 2})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-maxdepth", cmd)
        self.assertIn("2", cmd)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="permission denied")):
            result = _execute("find", {"path": "/root"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# copy operation
# ---------------------------------------------------------------------------

class TestCopy(unittest.TestCase):
    def test_success(self):
        with _patch(_ok()):
            result = _execute("copy", {"src": "/tmp/a", "dst": "/tmp/b"})
        self.assertTrue(result.ok)
        self.assertIn("/tmp/a", result.summary)
        self.assertIn("/tmp/b", result.summary)

    def test_recursive_flag(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("copy", {"src": "/tmp/dir", "dst": "/tmp/dir2", "recursive": True})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-r", cmd)

    def test_no_recursive_flag_by_default(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("copy", {"src": "/tmp/a", "dst": "/tmp/b"})
        cmd = mock_fn.call_args[0][0]
        self.assertNotIn("-r", cmd)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="No such file")):
            result = _execute("copy", {"src": "/no/a", "dst": "/tmp/b"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# move operation
# ---------------------------------------------------------------------------

class TestMove(unittest.TestCase):
    def test_success(self):
        with _patch(_ok()):
            result = _execute("move", {"src": "/tmp/a", "dst": "/tmp/b"})
        self.assertTrue(result.ok)
        self.assertIn("Moved", result.summary)

    def test_failure(self):
        with _patch(_fail(exit_code=1)):
            result = _execute("move", {"src": "/no/src", "dst": "/tmp/dst"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# mkdir operation
# ---------------------------------------------------------------------------

class TestMkdir(unittest.TestCase):
    def test_success_with_parents(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            result = _execute("mkdir", {"path": "/tmp/new/sub", "parents": True})
        self.assertTrue(result.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-p", cmd)

    def test_success_without_parents(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("mkdir", {"path": "/tmp/newdir", "parents": False})
        cmd = mock_fn.call_args[0][0]
        self.assertNotIn("-p", cmd)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="Permission denied")):
            result = _execute("mkdir", {"path": "/root/denied"})
        self.assertFalse(result.ok)
        self.assertIn("/root/denied", result.summary)


# ---------------------------------------------------------------------------
# chmod operation
# ---------------------------------------------------------------------------

class TestChmod(unittest.TestCase):
    def test_success(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            result = _execute("chmod", {"mode": "755", "path": "/tmp/script.sh"})
        self.assertTrue(result.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertIn("chmod", cmd)
        self.assertIn("755", cmd)
        self.assertIn("/tmp/script.sh", cmd)

    def test_recursive_flag(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("chmod", {"mode": "644", "path": "/tmp/dir", "recursive": True})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-R", cmd)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="Operation not permitted")):
            result = _execute("chmod", {"mode": "000", "path": "/tmp/x"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# chown operation
# ---------------------------------------------------------------------------

class TestChown(unittest.TestCase):
    def test_success(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            result = _execute("chown", {"owner": "www-data", "path": "/var/www"})
        self.assertTrue(result.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertIn("chown", cmd)
        self.assertIn("www-data", cmd)

    def test_recursive_flag(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("chown", {"owner": "root:root", "path": "/tmp/dir", "recursive": True})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-R", cmd)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="Operation not permitted")):
            result = _execute("chown", {"owner": "nobody", "path": "/etc/passwd"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# write operation
# ---------------------------------------------------------------------------

class TestWrite(unittest.TestCase):
    def test_success(self):
        content = "hello world\n"
        mock_fn = MagicMock(return_value=_ok(stdout=content))
        with _patch_fn(mock_fn):
            result = _execute("write", {"path": "/tmp/out.txt", "content": content})
        self.assertTrue(result.ok)
        self.assertIn("/tmp/out.txt", result.summary)
        # Verify content was passed as stdin
        _call_kwargs = mock_fn.call_args
        self.assertIn("input", _call_kwargs.kwargs or {})

    def test_byte_count_in_summary(self):
        content = "x" * 50
        with _patch(_ok(stdout=content)):
            result = _execute("write", {"path": "/tmp/x.txt", "content": content})
        self.assertIn("50", result.summary)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="Permission denied")):
            result = _execute("write", {"path": "/etc/nope", "content": "data"})
        self.assertFalse(result.ok)


# ---------------------------------------------------------------------------
# remove operation
# ---------------------------------------------------------------------------

class TestRemove(unittest.TestCase):
    def test_plain_remove(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            result = _execute("remove", {"path": "/tmp/foo.txt"})
        self.assertTrue(result.ok)
        cmd = mock_fn.call_args[0][0]
        self.assertIn("rm", cmd)
        self.assertIn("/tmp/foo.txt", cmd)
        self.assertNotIn("-r", cmd)
        self.assertNotIn("-f", cmd)

    def test_recursive_flag(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("remove", {"path": "/tmp/dir", "recursive": True})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-r", cmd)

    def test_force_flag(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("remove", {"path": "/tmp/file", "force": True})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-f", cmd)

    def test_recursive_and_force(self):
        mock_fn = MagicMock(return_value=_ok())
        with _patch_fn(mock_fn):
            _execute("remove", {"path": "/tmp/dir", "recursive": True, "force": True})
        cmd = mock_fn.call_args[0][0]
        self.assertIn("-r", cmd)
        self.assertIn("-f", cmd)

    def test_failure(self):
        with _patch(_fail(exit_code=1, stderr="No such file or directory")):
            result = _execute("remove", {"path": "/tmp/ghost"})
        self.assertFalse(result.ok)
        self.assertIn("/tmp/ghost", result.summary)


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint(unittest.TestCase):
    AVC_STDERR = (
        "cp: cannot stat '/etc/foo': "
        "AVC avc:  denied  { read } for  pid=123 comm=\"cp\" "
        "name=\"foo\" dev=\"dm-0\" ino=12345"
    )

    def test_avc_in_stderr_surfaces_hint_on_copy(self):
        with _patch(_fail(exit_code=1, stderr=self.AVC_STDERR)):
            result = _execute("copy", {"src": "/etc/foo", "dst": "/tmp/foo"})
        self.assertTrue(
            "SELinux" in result.summary or "ausearch" in result.summary,
            f"Expected SELinux hint in: {result.summary!r}"
        )

    def test_avc_in_stderr_surfaces_hint_on_chmod(self):
        with _patch(_fail(exit_code=1, stderr=self.AVC_STDERR)):
            result = _execute("chmod", {"mode": "644", "path": "/tmp/x"})
        self.assertTrue(
            "SELinux" in result.summary or "ausearch" in result.summary
        )

    def test_clean_stderr_no_hint(self):
        with _patch(_fail(exit_code=1, stderr="No such file or directory")):
            result = _execute("remove", {"path": "/tmp/gone"})
        self.assertNotIn("ausearch", result.summary)


# ---------------------------------------------------------------------------
# Unknown operation
# ---------------------------------------------------------------------------

class TestUnknownOp(unittest.TestCase):
    def test_unknown_op_returns_exit_1(self):
        result = _execute("nonexistent_op", {})
        self.assertEqual(result.exit_code, 1)
        self.assertIn("nonexistent_op", result.summary)

    def test_unknown_op_summary_is_string(self):
        result = _execute("frobnicate", {})
        self.assertIsInstance(result.summary, str)
        self.assertGreater(len(result.summary), 0)


# ---------------------------------------------------------------------------
# I2 invariant: no AI/LLM/model/agent terms in descriptions or summaries
# ---------------------------------------------------------------------------

class TestI2NoAILanguage(unittest.TestCase):
    """Invariant I2: no forbidden AI/LLM/model/agent language anywhere."""

    def test_tool_description_is_i2_clean(self):
        spec = registry.get("files")
        _check_i2(spec.description, "files ToolSpec.description")

    def test_all_op_descriptions_are_i2_clean(self):
        spec = registry.get("files")
        for op_name, op_spec in spec.ops.items():
            _check_i2(op_spec.description, f"files.{op_name} OpSpec.description")
            for arg_spec in op_spec.args:
                _check_i2(arg_spec.description, f"files.{op_name}.{arg_spec.name} ArgSpec.description")

    def test_all_success_summaries_are_i2_clean(self):
        cases = [
            ("list",   {"path": "/tmp"}),
            ("read",   {"path": "/tmp/foo.txt"}),
            ("stat",   {"path": "/tmp/foo.txt"}),
            ("find",   {"path": "/tmp"}),
            ("copy",   {"src": "/tmp/a", "dst": "/tmp/b"}),
            ("move",   {"src": "/tmp/a", "dst": "/tmp/b"}),
            ("mkdir",  {"path": "/tmp/newdir"}),
            ("chmod",  {"mode": "755", "path": "/tmp/foo"}),
            ("chown",  {"owner": "root", "path": "/tmp/foo"}),
            ("write",  {"path": "/tmp/out.txt", "content": "hello"}),
            ("remove", {"path": "/tmp/foo.txt"}),
        ]
        for op, args in cases:
            with self.subTest(op=op):
                with _patch(_ok(stdout="some output")):
                    result = _execute(op, args)
                _check_i2(result.summary, f"files.{op} success summary")

    def test_all_failure_summaries_are_i2_clean(self):
        cases = [
            ("list",   {"path": "/tmp"}),
            ("read",   {"path": "/tmp/foo.txt"}),
            ("stat",   {"path": "/tmp/foo.txt"}),
            ("find",   {"path": "/tmp"}),
            ("copy",   {"src": "/tmp/a", "dst": "/tmp/b"}),
            ("move",   {"src": "/tmp/a", "dst": "/tmp/b"}),
            ("mkdir",  {"path": "/tmp/newdir"}),
            ("chmod",  {"mode": "755", "path": "/tmp/foo"}),
            ("chown",  {"owner": "root", "path": "/tmp/foo"}),
            ("write",  {"path": "/tmp/out.txt", "content": "hello"}),
            ("remove", {"path": "/tmp/foo.txt"}),
        ]
        for op, args in cases:
            with self.subTest(op=op):
                with _patch(_fail(exit_code=1, stderr="error")):
                    result = _execute(op, args)
                _check_i2(result.summary, f"files.{op} failure summary")


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch(unittest.TestCase):
    def test_dispatch_list(self):
        with _patch(_ok(stdout=".\n..\nfoo\n")):
            result = registry.dispatch("files", "list", {"path": "/tmp"})
        self.assertIsInstance(result, ToolResult)
        self.assertEqual(result.exit_code, 0)

    def test_dispatch_stat(self):
        with _patch(_ok(stdout="  File: /tmp\n")):
            result = registry.dispatch("files", "stat", {"path": "/tmp"})
        self.assertTrue(result.ok)

    def test_dispatch_missing_required_arg_raises(self):
        with self.assertRaises(TypeError):
            registry.dispatch("files", "read", {})

    def test_dispatch_unknown_op_raises(self):
        with self.assertRaises(ValueError):
            registry.dispatch("files", "teleport", {"path": "/tmp"})

    def test_dispatch_remove(self):
        with _patch(_ok()):
            result = registry.dispatch(
                "files", "remove", {"path": "/tmp/foo.txt"}
            )
        self.assertTrue(result.ok)


if __name__ == "__main__":
    unittest.main()
