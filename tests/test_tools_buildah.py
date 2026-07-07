"""tests/test_tools_buildah.py — Unit tests for core/tools/buildah.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without buildah present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: images=READ; from/copy/run/commit/push/build=WRITE; rm=DESTRUCTIVE.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (non-zero) -> ok=False, failure summary naming the object + exit code.
  * Command vectors: exact argv list checked for each op.
  * SELinux AVC hint surfaced when stderr contains AVC language.
  * I2 compliance: no AI/LLM/model/agent/agentic/neural/language-model in summaries.
  * I9: execute() NEVER raises — unknown op and missing binary (exit 127) degrade cleanly.
  * DEFERRED-TO-MOSSAD: live execution tests skipped on macOS dev host.

Mocking strategy
----------------
  We patch ``core.tools.buildah.run_subprocess`` (the function in the
  buildah module's namespace, where the ``from core.tools import run_subprocess``
  binding lives) to return controlled ToolResult fixtures.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration in the module-level registry.
import core.tools.buildah  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.buildah import BUILDAH_SPEC, _execute


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch_run(return_value: ToolResult):
    """Patch core.tools.buildah.run_subprocess with a fixed return value."""
    return patch("core.tools.buildah.run_subprocess", return_value=return_value)


def _patch_mock():
    """Patch core.tools.buildah.run_subprocess with a MagicMock (for call-arg inspection)."""
    return patch("core.tools.buildah.run_subprocess")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_buildah_registered_in_registry(self) -> None:
        assert registry.get("buildah") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("buildah")
        assert spec is not None
        assert spec.name == "buildah"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("buildah")
        assert spec is not None
        expected = {"images", "from", "copy", "run", "commit", "push", "build", "rm"}
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", ["images"])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("buildah", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["from", "copy", "run", "commit", "push", "build"])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("buildah", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    @pytest.mark.parametrize("op", ["rm"])
    def test_destructive_ops(self, op: str) -> None:
        cls = registry.permission_class_for("buildah", op)
        assert cls is OpClass.DESTRUCTIVE, f"Expected DESTRUCTIVE for '{op}', got {cls}"

    def test_spec_permission_class_for_rm(self) -> None:
        assert BUILDAH_SPEC.permission_class_for("rm") is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vectors — exact argv assertions
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_images_no_all(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="IMAGE NAME\n"))
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("images", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "images"]

    def test_images_with_all(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="IMAGE NAME\n"))
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("images", {"all": True})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "images", "--all"]

    def test_from_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="ubi9-working-container\n"))
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("from", {"image": "ubi9"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "from", "ubi9"]

    def test_copy_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("copy", {"container": "myapp-wc", "src": "./app", "dst": "/app"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "copy", "myapp-wc", "./app", "/app"]

    def test_run_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("run", {"container": "ubi9-wc", "command": "dnf install -y nginx"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "run", "ubi9-wc", "--", "dnf install -y nginx"]

    def test_commit_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("commit", {"container": "myapp-wc", "image": "myapp:1.0"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "commit", "myapp-wc", "myapp:1.0"]

    def test_push_argv(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("push", {"image": "quay.io/myorg/myapp:1.0"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "push", "quay.io/myorg/myapp:1.0"]

    def test_build_default_context(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("build", {"tag": "myapp:latest"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "build", "-t", "myapp:latest", "."]

    def test_build_custom_context(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("build", {"tag": "myapp:2.0", "context": "./docker"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "build", "-t", "myapp:2.0", "./docker"]

    def test_rm_named_container(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="myapp-wc\n"))
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("rm", {"container": "myapp-wc"})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "rm", "myapp-wc"]

    def test_rm_all_flag(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout="container1\ncontainer2\n"))
        with patch("core.tools.buildah.run_subprocess", mock_fn):
            _execute("rm", {"all": True})
        argv = mock_fn.call_args[0][0]
        assert argv == ["buildah", "rm", "--all"]


# ---------------------------------------------------------------------------
# Exit-code mapping — success and failure summaries
# ---------------------------------------------------------------------------

class TestExitCodeMapping:
    def test_images_success(self) -> None:
        with _patch_run(_ok(stdout="IMAGE NAME\ndocker.io/library/nginx latest\n")):
            result = _execute("images", {})
        assert result.ok
        assert "image" in result.summary.lower()

    def test_images_failure(self) -> None:
        with _patch_run(_fail(exit_code=125, stderr="storage not initialized")):
            result = _execute("images", {})
        assert not result.ok
        assert "125" in result.summary

    def test_from_success(self) -> None:
        with _patch_run(_ok(stdout="ubi9-working-container\n")):
            result = _execute("from", {"image": "ubi9"})
        assert result.ok
        assert "ubi9" in result.summary

    def test_from_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="image not found")):
            result = _execute("from", {"image": "badimg:latest"})
        assert not result.ok
        assert "badimg:latest" in result.summary
        assert "1" in result.summary

    def test_copy_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("copy", {"container": "myapp-wc", "src": "./app", "dst": "/app"})
        assert result.ok
        assert "myapp-wc" in result.summary

    def test_copy_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="container not known")):
            result = _execute("copy", {"container": "ghost-wc", "src": "x", "dst": "y"})
        assert not result.ok
        assert "ghost-wc" in result.summary

    def test_run_success(self) -> None:
        with _patch_run(_ok(stdout="Complete!\n")):
            result = _execute("run", {"container": "ubi9-wc", "command": "dnf install -y nginx"})
        assert result.ok
        assert "ubi9-wc" in result.summary

    def test_run_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="command returned non-zero exit code")):
            result = _execute("run", {"container": "myapp-wc", "command": "false"})
        assert not result.ok
        assert "myapp-wc" in result.summary

    def test_commit_success(self) -> None:
        with _patch_run(_ok(stdout="abc123def456\n")):
            result = _execute("commit", {"container": "myapp-wc", "image": "myapp:1.0"})
        assert result.ok
        assert "myapp-wc" in result.summary
        assert "myapp:1.0" in result.summary

    def test_commit_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="container not known")):
            result = _execute("commit", {"container": "ghost-wc", "image": "myapp:1.0"})
        assert not result.ok
        assert "ghost-wc" in result.summary

    def test_push_success(self) -> None:
        with _patch_run(_ok()):
            result = _execute("push", {"image": "quay.io/myorg/myapp:1.0"})
        assert result.ok
        assert "quay.io/myorg/myapp:1.0" in result.summary

    def test_push_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="unauthorized")):
            result = _execute("push", {"image": "quay.io/myorg/myapp:1.0"})
        assert not result.ok
        assert "quay.io/myorg/myapp:1.0" in result.summary
        assert "1" in result.summary

    def test_build_success(self) -> None:
        with _patch_run(_ok(stdout="Successfully tagged myapp:latest\nabc123\n")):
            result = _execute("build", {"tag": "myapp:latest"})
        assert result.ok
        assert "myapp:latest" in result.summary

    def test_build_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="no Containerfile found")):
            result = _execute("build", {"tag": "myapp:latest"})
        assert not result.ok
        assert "myapp:latest" in result.summary

    def test_rm_success(self) -> None:
        with _patch_run(_ok(stdout="myapp-wc\n")):
            result = _execute("rm", {"container": "myapp-wc"})
        assert result.ok
        assert "myapp-wc" in result.summary

    def test_rm_failure(self) -> None:
        with _patch_run(_fail(exit_code=1, stderr="container not known")):
            result = _execute("rm", {"container": "ghost-wc"})
        assert not result.ok
        assert "ghost-wc" in result.summary
        assert "1" in result.summary

    def test_rm_all_success(self) -> None:
        with _patch_run(_ok(stdout="c1\nc2\n")):
            result = _execute("rm", {"all": True})
        assert result.ok
        assert "all" in result.summary.lower() or "container" in result.summary.lower()


# ---------------------------------------------------------------------------
# I2-clean summaries — no AI/LLM/model/agent language
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in any user-facing string."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("images",  {}),
        ("from",    {"image": "ubi9"}),
        ("copy",    {"container": "myapp-wc", "src": "./app", "dst": "/app"}),
        ("run",     {"container": "ubi9-wc", "command": "echo hello"}),
        ("commit",  {"container": "myapp-wc", "image": "myapp:1.0"}),
        ("push",    {"image": "myapp:1.0"}),
        ("build",   {"tag": "myapp:latest"}),
        ("rm",      {"container": "myapp-wc"}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in success summary for op='{op}': {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("images",  {}),
        ("from",    {"image": "ubi9"}),
        ("copy",    {"container": "myapp-wc", "src": "./app", "dst": "/app"}),
        ("run",     {"container": "ubi9-wc", "command": "echo hello"}),
        ("commit",  {"container": "myapp-wc", "image": "myapp:1.0"}),
        ("push",    {"image": "myapp:1.0"}),
        ("build",   {"tag": "myapp:latest"}),
        ("rm",      {"container": "myapp-wc"}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="something failed")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op='{op}': {result.summary!r}"
            )


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "Error: open /var/lib/containers/storage: "
        "AVC avc: denied { read } for pid=1234 "
        "comm=\"buildah\" scontext=unconfined_u:unconfined_r:unconfined_t:s0"
    )

    @pytest.mark.parametrize("op,args", [
        ("images",  {}),
        ("from",    {"image": "ubi9"}),
        ("copy",    {"container": "myapp-wc", "src": "./app", "dst": "/app"}),
        ("run",     {"container": "ubi9-wc", "command": "echo hi"}),
        ("commit",  {"container": "myapp-wc", "image": "myapp:1.0"}),
        ("push",    {"image": "myapp:1.0"}),
        ("build",   {"tag": "myapp:latest"}),
        ("rm",      {"container": "myapp-wc"}),
    ])
    def test_avc_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"SELinux hint not found in summary for op='{op}': {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("images",  {}),
        ("from",    {"image": "ubi9"}),
        ("rm",      {"container": "myapp-wc"}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch_run(_fail(exit_code=1, stderr="container not found")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary, (
            f"Unexpected SELinux hint in summary for op='{op}': {result.summary!r}"
        )


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("images",  {}),
        ("from",    {"image": "ubi9"}),
        ("copy",    {"container": "myapp-wc", "src": "./app", "dst": "/app"}),
        ("run",     {"container": "ubi9-wc", "command": "echo hello"}),
        ("commit",  {"container": "myapp-wc", "image": "myapp:1.0"}),
        ("push",    {"image": "myapp:1.0"}),
        ("build",   {"tag": "myapp:latest"}),
        ("rm",      {"container": "myapp-wc"}),
    ])
    def test_result_has_required_fields(self, op: str, args: dict) -> None:
        with _patch_run(_ok(stdout=f"{op} output")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code is not None
        assert isinstance(result.stdout, str)
        assert isinstance(result.stderr, str)
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("images",  {}),
        ("from",    {"image": "ubi9"}),
        ("copy",    {"container": "myapp-wc", "src": "./app", "dst": "/app"}),
        ("run",     {"container": "ubi9-wc", "command": "echo hello"}),
        ("commit",  {"container": "myapp-wc", "image": "myapp:1.0"}),
        ("push",    {"image": "myapp:1.0"}),
        ("build",   {"tag": "myapp:latest"}),
        ("rm",      {"container": "myapp-wc"}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch_run(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_well_formed_result(self) -> None:
        """Unknown op must not raise — returns a ToolResult with exit_code=1."""
        result = _execute("nonexistent_op", {"foo": "bar"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0
        assert result.as_dict().keys() == {"exit_code", "stdout", "stderr", "summary"}

    def test_missing_binary_exit_127_degrades_cleanly(self) -> None:
        """run_subprocess returning exit 127 (binary not found) must not raise."""
        missing_binary_result = ToolResult(
            exit_code=127,
            stdout="",
            stderr="buildah: command not found",
            summary="",
        )
        with _patch_run(missing_binary_result):
            result = _execute("images", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok
        assert isinstance(result.summary, str)
        assert len(result.summary) > 0

    @pytest.mark.parametrize("op,args", [
        ("from",   {"image": "ubi9"}),
        ("rm",     {"container": "myapp-wc"}),
        ("build",  {"tag": "myapp:latest"}),
    ])
    def test_exit_127_on_real_ops_degrades_cleanly(self, op: str, args: dict) -> None:
        """Exit 127 on each real op must degrade to a well-formed failure ToolResult."""
        missing = ToolResult(exit_code=127, stdout="", stderr="buildah: command not found", summary="")
        with _patch_run(missing):
            result = _execute(op, args)
        assert result.exit_code == 127
        assert not result.ok
        assert len(result.summary) > 0


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_images(self) -> None:
        with _patch_run(_ok(stdout="IMAGE NAME\n")):
            result = registry.dispatch("buildah", "images", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_from(self) -> None:
        with _patch_run(_ok(stdout="ubi9-working-container\n")):
            result = registry.dispatch("buildah", "from", {"image": "ubi9"})
        assert result.ok

    def test_dispatch_rm(self) -> None:
        with _patch_run(_ok(stdout="myapp-wc\n")):
            result = registry.dispatch("buildah", "rm", {"container": "myapp-wc"})
        assert result.ok


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real buildah on Rocky Linux 9")
def test_live_images() -> None:
    """Live: buildah images returns a populated ToolResult."""
    result = _execute("images", {})
    assert result.exit_code in (0, 1, 125)
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real buildah on Rocky Linux 9")
def test_live_from_ubi9() -> None:
    """Live: buildah from ubi9 creates a working container."""
    result = _execute("from", {"image": "registry.access.redhat.com/ubi9/ubi:9.3"})
    assert result.exit_code == 0
    assert "working-container" in result.stdout.lower() or len(result.stdout) > 0


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real buildah on Rocky Linux 9")
def test_live_rm_requires_existing_container() -> None:
    """Live: buildah rm on a non-existent container returns a non-zero exit code."""
    result = _execute("rm", {"container": "definitely-does-not-exist-container"})
    assert result.exit_code != 0
    assert not result.ok
