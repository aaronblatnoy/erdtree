"""tests/test_tools_podman.py — Unit tests for core/tools/podman.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without podman present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: ps/images/inspect/logs are READ; pull/run/stop/exec/
    build/push are WRITE; rm/rmi are DESTRUCTIVE.
  * Command vectors: argv passed to run_subprocess is exactly the expected list,
    including the '-f' flag on rm (destructive shape must appear verbatim).
  * Exit-code mapping: success (exit_code=0 -> .ok, success summary) and
    failure (non-zero -> not .ok, failure summary naming the object).
  * SELinux AVC hint surfaces in summary when stderr contains AVC language;
    clean stderr does NOT produce the hint.
  * execute() NEVER raises (I9): bogus op and exit 127 (missing binary) both
    degrade to a well-formed ToolResult with no exception.
  * I2: no AI/LLM/model/agent/agentic/neural language in any summary.
  * ToolResult structure: non-None exit_code, str fields, non-empty summary,
    as_dict() returns exactly {exit_code, stdout, stderr, summary}.
  * logs: lines argument is clamped to [1, 500]; default is 50.
  * DEFERRED-TO-MOSSAD: live execution skipped on the macOS dev host.

Mocking strategy
----------------
  Patch ``core.tools.podman.run_subprocess`` (the binding in the podman
  module's namespace, where the ``from core.tools import run_subprocess``
  binding lives) so every _op_* function is intercepted without launching
  a real process.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.podman  # noqa: F401  (side-effect: registry.register)
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.podman import PODMAN_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Return a context-manager patch on core.tools.podman.run_subprocess."""
    return patch("core.tools.podman.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_podman_registered(self) -> None:
        assert registry.get("podman") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("podman")
        assert spec is not None
        assert spec.name == "podman"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("podman")
        assert spec is not None
        expected = {
            "ps", "images", "inspect", "logs",
            "pull", "run", "stop", "exec", "build", "push",
            "rm", "rmi",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["ps", "images", "inspect", "logs"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("podman", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["pull", "run", "stop", "exec", "build", "push"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("podman", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["rm", "rmi"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("podman", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"


# ---------------------------------------------------------------------------
# Command vectors — assert argv sent to run_subprocess
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_ps_default(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="CONTAINER ID\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("ps", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "ps"]

    def test_ps_all(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="CONTAINER ID\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("ps", {"all": True})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "ps", "--all"]

    def test_images_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="REPOSITORY\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("images", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "images"]

    def test_inspect_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="[{}]"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("inspect", {"target": "web-app"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "inspect", "web-app"]

    def test_logs_vector_default_lines(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("logs", {"container": "api"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "logs", "--tail", "50", "api"]

    def test_logs_vector_custom_lines(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("logs", {"container": "api", "lines": 100})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "logs", "--tail", "100", "api"]

    def test_logs_lines_clamped_to_max(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("logs", {"container": "api", "lines": 9999})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "logs", "--tail", "500", "api"]

    def test_logs_lines_clamped_to_min(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("logs", {"container": "api", "lines": 0})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "logs", "--tail", "1", "api"]

    def test_pull_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("pull", {"image": "nginx:1.25"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "pull", "nginx:1.25"]

    def test_run_detached_with_name(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="abc123\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("run", {"image": "nginx:1.25", "name": "web", "detach": True})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "run", "--detach", "--name", "web", "nginx:1.25"]

    def test_run_no_name_no_detach(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("run", {"image": "ubi9:latest", "detach": False})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "run", "ubi9:latest"]

    def test_stop_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="web\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("stop", {"container": "web"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "stop", "web"]

    def test_exec_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="output\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("exec", {"container": "api", "command": "ls /app"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "exec", "api", "ls", "/app"]

    def test_build_with_tag(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Successfully tagged myapp:1.0\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("build", {"context": ".", "tag": "myapp:1.0"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "build", "-t", "myapp:1.0", "."]

    def test_build_without_tag(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("build", {"context": "/opt/myapp"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "build", "/opt/myapp"]

    def test_push_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("push", {"image": "registry.example.com/myapp:1.0"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "push", "registry.example.com/myapp:1.0"]

    def test_rm_vector_always_has_force_flag(self) -> None:
        """rm MUST always include -f so the destructive argv shape is present."""
        mock_fn = MagicMock(return_value=_ok(stdout="abc123\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("rm", {"container": "web-app"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "rm", "-f", "web-app"]
        # Verify -f is at index 2 (the literal destructive shape the classifier gates on)
        assert argv[2] == "-f"

    def test_rmi_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="Deleted: abc\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            _execute("rmi", {"image": "nginx:1.24"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["podman", "rmi", "nginx:1.24"]


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure summaries
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    @pytest.mark.parametrize("op,args,success_kw", [
        ("ps",      {},                       "container"),
        ("images",  {},                       "image"),
        ("inspect", {"target": "web"},        "web"),
        ("logs",    {"container": "api"},     "api"),
        ("pull",    {"image": "ubi9:latest"}, "ubi9:latest"),
        ("run",     {"image": "ubi9:latest"}, "ubi9:latest"),
        ("stop",    {"container": "api"},     "api"),
        ("exec",    {"container": "api", "command": "ls"}, "api"),
        ("build",   {"context": "."},         "context"),
        ("push",    {"image": "myapp:1.0"},   "myapp:1.0"),
        ("rm",      {"container": "old"},     "old"),
        ("rmi",     {"image": "myapp:0.9"},   "myapp:0.9"),
    ])
    def test_success_ok_true(self, op: str, args: dict, success_kw: str) -> None:
        with _patch_run(_ok(stdout="output")):
            result = _execute(op, args)
        assert result.ok, f"Expected ok=True for op='{op}'"

    @pytest.mark.parametrize("op,args", [
        ("ps",      {}),
        ("images",  {}),
        ("inspect", {"target": "web"}),
        ("logs",    {"container": "api"}),
        ("pull",    {"image": "ubi9:latest"}),
        ("run",     {"image": "ubi9:latest"}),
        ("stop",    {"container": "api"}),
        ("exec",    {"container": "api", "command": "ls"}),
        ("build",   {"context": "."}),
        ("push",    {"image": "myapp:1.0"}),
        ("rm",      {"container": "old"}),
        ("rmi",     {"image": "myapp:0.9"}),
    ])
    def test_failure_ok_false(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="error")):
            result = _execute(op, args)
        assert not result.ok, f"Expected ok=False for op='{op}'"
        assert result.exit_code == 1

    def test_failure_summary_contains_exit_code(self) -> None:
        with _patch_run(_fail(exit_code=125, stderr="not found")):
            result = _execute("inspect", {"target": "my-ctr"})
        assert not result.ok
        assert "125" in result.summary
        assert "my-ctr" in result.summary

    def test_success_summary_not_empty(self) -> None:
        with _patch_run(_ok(stdout="CONTAINER ID\nweb\n")):
            result = _execute("ps", {})
        assert result.ok
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("ps",      {}),
        ("images",  {}),
        ("inspect", {"target": "web"}),
        ("logs",    {"container": "api"}),
        ("pull",    {"image": "ubi9:latest"}),
        ("run",     {"image": "ubi9:latest"}),
        ("stop",    {"container": "api"}),
        ("exec",    {"container": "api", "command": "ls"}),
        ("build",   {"context": "."}),
        ("push",    {"image": "myapp:1.0"}),
        ("rm",      {"container": "old"}),
        ("rmi",     {"image": "myapp:0.9"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout="output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("ps",      {}),
        ("images",  {}),
        ("inspect", {"target": "t"}),
        ("logs",    {"container": "c"}),
        ("pull",    {"image": "img:tag"}),
        ("run",     {"image": "img:tag"}),
        ("stop",    {"container": "c"}),
        ("exec",    {"container": "c", "command": "ls"}),
        ("build",   {"context": "."}),
        ("push",    {"image": "img:tag"}),
        ("rm",      {"container": "c"}),
        ("rmi",     {"image": "img:tag"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "Error: error creating container: "
        "AVC avc: denied { read } for pid=1234 "
        "comm=\"podman\" scontext=user_u:user_r:user_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("inspect", {"target": "web"}),
        ("pull",    {"image": "ubi9:latest"}),
        ("run",     {"image": "ubi9:latest"}),
        ("stop",    {"container": "api"}),
        ("rm",      {"container": "old"}),
        ("rmi",     {"image": "img:tag"}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"Expected SELinux hint in summary for op='{op}': {result.summary!r}"

    def test_logs_avc_in_stdout_surfaces_hint(self) -> None:
        avc_stdout = (
            "2026-07-04T00:01:00Z app[1]: AVC avc: denied { open } for pid=2"
        )
        with _patch_run(_ok(stdout=avc_stdout)):
            result = _execute("logs", {"container": "api"})
        assert "SELinux" in result.summary or "ausearch" in result.summary

    def test_clean_stderr_no_hint(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="Error: container not found.")):
            result = _execute("inspect", {"target": "web"})
        assert "ausearch" not in result.summary
        assert "SELinux" not in result.summary


# ---------------------------------------------------------------------------
# I2 — no AI/LLM/model/agent language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("ps",      {}),
        ("images",  {}),
        ("inspect", {"target": "web"}),
        ("logs",    {"container": "api"}),
        ("pull",    {"image": "ubi9:latest"}),
        ("run",     {"image": "ubi9:latest"}),
        ("stop",    {"container": "api"}),
        ("exec",    {"container": "api", "command": "ls"}),
        ("build",   {"context": "."}),
        ("push",    {"image": "myapp:1.0"}),
        ("rm",      {"container": "old"}),
        ("rmi",     {"image": "myapp:0.9"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': "
                f"{result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("ps",      {}),
        ("inspect", {"target": "web"}),
        ("run",     {"image": "ubi9:latest"}),
        ("rm",      {"container": "old"}),
        ("rmi",     {"image": "myapp:0.9"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="error occurred")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': "
                f"{result.summary!r}"
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
        assert not result.ok

    def test_missing_binary_exit_127_returns_toolresult(self) -> None:
        """Simulate podman not installed (exit 127 — command not found)."""
        missing = ToolResult(
            exit_code=127, stdout="", stderr="", summary="command not found: podman"
        )
        with _patch_run(missing):
            result = _execute("ps", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_timeout_exit_124_returns_toolresult(self) -> None:
        timeout_result = ToolResult(
            exit_code=124, stdout="", stderr="", summary="timed out"
        )
        with _patch_run(timeout_result):
            result = _execute("build", {"context": "."})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 124
        assert not result.ok


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_ps(self) -> None:
        with _patch_run(_ok(stdout="CONTAINER ID\n")):
            result = registry.dispatch("podman", "ps", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_images(self) -> None:
        with _patch_run(_ok(stdout="REPOSITORY\n")):
            result = registry.dispatch("podman", "images", {})
        assert result.ok

    def test_dispatch_inspect_missing_target_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'target'"):
            registry.dispatch("podman", "inspect", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("podman", "nonexistent_op", {})

    def test_dispatch_rm(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="abc123\n"))
        with patch("core.tools.podman.run_subprocess", mock_fn):
            result = registry.dispatch("podman", "rm", {"container": "web-app"})
        assert result.ok
        # Verify -f was in the argv (destructive shape)
        argv = mock_fn.call_args[0][0]
        assert "-f" in argv


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real podman on Rocky Linux 9")
def test_live_ps() -> None:
    """Live: podman ps returns a populated ToolResult."""
    result = _execute("ps", {})
    assert result.exit_code in (0, 1, 125, 127)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real podman on Rocky Linux 9")
def test_live_images() -> None:
    """Live: podman images returns a populated ToolResult."""
    result = _execute("images", {})
    assert result.exit_code == 0
    assert "REPOSITORY" in result.stdout or result.stdout == ""


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real podman on Rocky Linux 9")
def test_live_pull_ubi9() -> None:
    """Live: podman pull of ubi9 requires network access and registry credentials."""
    result = _execute("pull", {"image": "registry.access.redhat.com/ubi9:latest"})
    assert result.exit_code is not None
