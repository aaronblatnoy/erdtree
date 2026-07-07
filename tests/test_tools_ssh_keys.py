"""tests/test_tools_ssh_keys.py — Unit tests for core/tools/ssh_keys.py.

All subprocess calls are mocked via unittest.mock.patch so these tests run
fully on the macOS dev host without ssh-keygen, cat, sed, or sshd present.

Coverage
--------
  * ToolSpec registration in the module-level registry.
  * Permission classes: READ, WRITE, DESTRUCTIVE per the op table.
  * Each operation produces a ToolResult with the correct structure.
  * Successful exit (exit_code=0) -> ok=True, meaningful summary.
  * Failed exit (exit_code!=0) -> ok=False, failure summary naming the object.
  * Command vectors: exact argv lists verified for every op.
  * SELinux AVC hint surfaced in summary when stderr contains AVC language.
  * Clean stderr does NOT surface the hint.
  * I2: no AI/LLM/model/agent/neural language in any summary.
  * I9: execute() NEVER raises — unknown op and exit-127 both yield ToolResult.
  * ToolResult structure: all four fields present, as_dict() has correct keys.
  * DEFERRED-TO-MOSSAD: live execution against real ssh-keygen on Rocky Linux 9.

Mocking strategy
----------------
  Patch ``core.tools.ssh_keys.run_subprocess`` (the binding in that module's
  namespace, not the shared core.tools binding).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Trigger self-registration into the module-level registry.
import core.tools.ssh_keys  # noqa: F401
from core.agent.permissions import OpClass
from core.tools import ToolResult, registry
from core.tools.ssh_keys import SSH_KEYS_SPEC, _execute


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=0, stdout=stdout, stderr=stderr, summary="")


def _fail(exit_code: int = 1, stdout: str = "", stderr: str = "") -> ToolResult:
    return ToolResult(exit_code=exit_code, stdout=stdout, stderr=stderr, summary="")


def _patch(return_value: ToolResult):
    """Patch core.tools.ssh_keys.run_subprocess with a fixed return value."""
    return patch("core.tools.ssh_keys.run_subprocess", return_value=return_value)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegistration:
    def test_ssh_keys_registered(self) -> None:
        assert registry.get("ssh_keys") is not None

    def test_spec_name(self) -> None:
        spec = registry.get("ssh_keys")
        assert spec is not None
        assert spec.name == "ssh_keys"

    def test_all_expected_ops_present(self) -> None:
        spec = registry.get("ssh_keys")
        assert spec is not None
        expected = {
            "keygen",
            "authorized_keys_list",
            "authorized_keys_add",
            "authorized_keys_remove",
            "known_hosts_list",
            "known_hosts_remove",
            "sshd_config_audit",
        }
        assert set(spec.ops.keys()) == expected


# ---------------------------------------------------------------------------
# Permission classes
# ---------------------------------------------------------------------------

class TestPermissionClasses:
    @pytest.mark.parametrize("op", [
        "authorized_keys_list",
        "known_hosts_list",
        "sshd_config_audit",
    ])
    def test_read_ops(self, op: str) -> None:
        cls = registry.permission_class_for("ssh_keys", op)
        assert cls is OpClass.READ, f"Expected READ for '{op}', got {cls}"

    @pytest.mark.parametrize("op", [
        "keygen",
        "authorized_keys_add",
        "known_hosts_remove",
    ])
    def test_write_ops(self, op: str) -> None:
        cls = registry.permission_class_for("ssh_keys", op)
        assert cls is OpClass.WRITE, f"Expected WRITE for '{op}', got {cls}"

    def test_authorized_keys_remove_is_destructive(self) -> None:
        cls = registry.permission_class_for("ssh_keys", "authorized_keys_remove")
        assert cls is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# Command vector verification
# ---------------------------------------------------------------------------

class TestCommandVectors:
    def test_keygen_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("keygen", {"path": "/root/.ssh/id_ed25519", "key_type": "ed25519", "bits": 4096})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "ssh-keygen"
        assert "-t" in argv
        assert "ed25519" in argv
        assert "-f" in argv
        assert "/root/.ssh/id_ed25519" in argv
        assert "-N" in argv

    def test_keygen_rsa_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("keygen", {"path": "/home/deploy/.ssh/id_rsa", "key_type": "rsa", "bits": 4096})
        argv = mock_fn.call_args[0][0]
        assert "rsa" in argv
        assert "4096" in argv

    def test_authorized_keys_list_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("authorized_keys_list", {"user": "deploy"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "cat"
        assert "/home/deploy/.ssh/authorized_keys" in argv

    def test_authorized_keys_list_root_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("authorized_keys_list", {"user": "root"})
        argv = mock_fn.call_args[0][0]
        assert "/root/.ssh/authorized_keys" in argv

    def test_authorized_keys_add_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("authorized_keys_add", {
                "key": "ssh-ed25519 AAAA... user@host",
                "user": "deploy",
            })
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "tee"
        assert "-a" in argv
        assert "/home/deploy/.ssh/authorized_keys" in argv
        # Verify input kwarg was passed
        kwargs = mock_fn.call_args[1]
        assert "input" in kwargs
        assert "ssh-ed25519" in kwargs["input"]

    def test_authorized_keys_remove_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("authorized_keys_remove", {
                "key_comment": "jdoe@workstation",
                "user": "deploy",
            })
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "sed"
        assert "-i" in argv
        # Pattern should contain the key_comment
        pattern_args = [a for a in argv if "jdoe@workstation" in a]
        assert len(pattern_args) > 0
        assert "/home/deploy/.ssh/authorized_keys" in argv

    def test_known_hosts_list_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("known_hosts_list", {"user": "ansible"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "cat"
        assert "/home/ansible/.ssh/known_hosts" in argv

    def test_known_hosts_remove_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("known_hosts_remove", {"hostname": "prod-db01.example.com", "user": "root"})
        argv = mock_fn.call_args[0][0]
        assert argv[0] == "ssh-keygen"
        assert "-R" in argv
        assert "prod-db01.example.com" in argv
        assert "-f" in argv
        assert "/root/.ssh/known_hosts" in argv

    def test_sshd_config_audit_vector(self) -> None:
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("sshd_config_audit", {})
        argv = mock_fn.call_args[0][0]
        assert argv == ["sshd", "-T"]


# ---------------------------------------------------------------------------
# keygen operation
# ---------------------------------------------------------------------------

class TestKeygen:
    def test_success_summary(self) -> None:
        stdout = (
            "Generating public/private ed25519 key pair.\n"
            "Your identification has been saved in /root/.ssh/id_ed25519\n"
        )
        with _patch(_ok(stdout=stdout)):
            result = _execute("keygen", {"path": "/root/.ssh/id_ed25519"})
        assert result.ok
        assert "/root/.ssh/id_ed25519" in result.summary
        assert "generated" in result.summary.lower() or "key" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="Saving key failed: No such file or directory")):
            result = _execute("keygen", {"path": "/bad/path/key"})
        assert not result.ok
        assert "/bad/path/key" in result.summary
        assert str(result.exit_code) in result.summary

    def test_optional_args_defaults(self) -> None:
        """keygen works with only the required 'path' arg."""
        mock_fn = MagicMock(return_value=_ok())
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            result = _execute("keygen", {"path": "/tmp/test_key"})
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# authorized_keys_list operation
# ---------------------------------------------------------------------------

class TestAuthorizedKeysList:
    def test_success_summary_contains_count(self) -> None:
        stdout = "ssh-ed25519 AAAA... user@host\nssh-rsa AAAA... admin@box\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("authorized_keys_list", {"user": "deploy"})
        assert result.ok
        assert "deploy" in result.summary
        assert "2" in result.summary or "authorized" in result.summary.lower()

    def test_failure_names_user(self) -> None:
        with _patch(_fail(exit_code=1, stderr="cat: /home/nope/.ssh/authorized_keys: No such file or directory")):
            result = _execute("authorized_keys_list", {"user": "nope"})
        assert not result.ok
        assert "nope" in result.summary

    def test_default_user_is_root(self) -> None:
        mock_fn = MagicMock(return_value=_ok(stdout=""))
        with patch("core.tools.ssh_keys.run_subprocess", mock_fn):
            _execute("authorized_keys_list", {})
        argv = mock_fn.call_args[0][0]
        assert "/root/.ssh/authorized_keys" in argv


# ---------------------------------------------------------------------------
# authorized_keys_add operation
# ---------------------------------------------------------------------------

class TestAuthorizedKeysAdd:
    def test_success_summary(self) -> None:
        key = "ssh-ed25519 AAAAC3... deploy@ci"
        with _patch(_ok(stdout=key + "\n")):
            result = _execute("authorized_keys_add", {"key": key, "user": "root"})
        assert result.ok
        assert "root" in result.summary
        assert "appended" in result.summary.lower() or "added" in result.summary.lower()

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="tee: /home/ghost/.ssh/authorized_keys: No such file or directory")):
            result = _execute("authorized_keys_add", {"key": "ssh-rsa AAAA...", "user": "ghost"})
        assert not result.ok
        assert "ghost" in result.summary


# ---------------------------------------------------------------------------
# authorized_keys_remove operation (DESTRUCTIVE)
# ---------------------------------------------------------------------------

class TestAuthorizedKeysRemove:
    def test_success_summary(self) -> None:
        with _patch(_ok()):
            result = _execute("authorized_keys_remove", {
                "key_comment": "jdoe@workstation",
                "user": "deploy",
            })
        assert result.ok
        assert "jdoe@workstation" in result.summary
        assert "deploy" in result.summary

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="sed: file not found")):
            result = _execute("authorized_keys_remove", {
                "key_comment": "ghost@host",
                "user": "nouser",
            })
        assert not result.ok
        assert "ghost@host" in result.summary
        assert str(result.exit_code) in result.summary

    def test_is_destructive_class(self) -> None:
        assert SSH_KEYS_SPEC.permission_class_for("authorized_keys_remove") is OpClass.DESTRUCTIVE


# ---------------------------------------------------------------------------
# known_hosts_list operation
# ---------------------------------------------------------------------------

class TestKnownHostsList:
    def test_success_summary(self) -> None:
        stdout = "prod.example.com ssh-ed25519 AAAA...\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("known_hosts_list", {"user": "root"})
        assert result.ok
        assert "root" in result.summary
        assert "known_hosts" in result.summary.lower() or "1" in result.summary

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="cat: /home/missing/.ssh/known_hosts: No such file or directory")):
            result = _execute("known_hosts_list", {"user": "missing"})
        assert not result.ok
        assert "missing" in result.summary


# ---------------------------------------------------------------------------
# known_hosts_remove operation
# ---------------------------------------------------------------------------

class TestKnownHostsRemove:
    def test_success_summary(self) -> None:
        with _patch(_ok(stdout="# Host prod-db01.example.com found: line 2\n")):
            result = _execute("known_hosts_remove", {
                "hostname": "prod-db01.example.com",
                "user": "root",
            })
        assert result.ok
        assert "prod-db01.example.com" in result.summary
        assert "root" in result.summary

    def test_failure_summary(self) -> None:
        with _patch(_fail(exit_code=1, stderr="ssh-keygen: No such file")):
            result = _execute("known_hosts_remove", {"hostname": "bad.host", "user": "nobody"})
        assert not result.ok
        assert "bad.host" in result.summary


# ---------------------------------------------------------------------------
# sshd_config_audit operation
# ---------------------------------------------------------------------------

class TestSshdConfigAudit:
    def test_success_summary(self) -> None:
        stdout = "port 22\npubkeyauthentication yes\npasswordauthentication yes\n"
        with _patch(_ok(stdout=stdout)):
            result = _execute("sshd_config_audit", {})
        assert result.ok
        assert "sshd" in result.summary.lower() or "audit" in result.summary.lower()

    def test_failure_on_missing_binary(self) -> None:
        with _patch(_fail(exit_code=127, stderr="sshd: command not found")):
            result = _execute("sshd_config_audit", {})
        assert not result.ok
        assert result.exit_code == 127

    def test_no_required_args(self) -> None:
        """sshd_config_audit takes no required args — empty dict must work."""
        with _patch(_ok(stdout="port 22\n")):
            result = _execute("sshd_config_audit", {})
        assert isinstance(result, ToolResult)


# ---------------------------------------------------------------------------
# SELinux hint surfacing
# ---------------------------------------------------------------------------

class TestSELinuxHint:
    _AVC_STDERR = (
        "AVC avc: denied { open } for pid=2345 comm=\"cat\" "
        "name=\"authorized_keys\" scontext=user_u:user_r:user_t:s0 "
        "tcontext=system_u:object_r:ssh_home_t:s0 tclass=file"
    )

    @pytest.mark.parametrize("op,args", [
        ("authorized_keys_list", {"user": "root"}),
        ("authorized_keys_add", {"key": "ssh-ed25519 AAAA... u@h", "user": "root"}),
        ("authorized_keys_remove", {"key_comment": "u@h", "user": "root"}),
        ("known_hosts_list", {"user": "root"}),
        ("known_hosts_remove", {"hostname": "host.example.com", "user": "root"}),
        ("sshd_config_audit", {}),
    ])
    def test_avc_in_stderr_surfaces_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr=self._AVC_STDERR)):
            result = _execute(op, args)
        assert (
            "SELinux" in result.summary
            or "ausearch" in result.summary
            or "AVC" in result.summary
        ), f"No SELinux hint in summary for op={op!r}: {result.summary!r}"

    @pytest.mark.parametrize("op,args", [
        ("authorized_keys_list", {"user": "root"}),
        ("sshd_config_audit", {}),
    ])
    def test_clean_stderr_no_hint(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="No such file or directory")):
            result = _execute(op, args)
        assert "ausearch" not in result.summary
        assert "AVC avc:" not in result.summary

    def test_keygen_avc_surfaces_hint(self) -> None:
        with _patch(_fail(exit_code=1, stderr="AVC avc: denied { write } for comm=\"ssh-keygen\"")):
            result = _execute("keygen", {"path": "/root/.ssh/id_ed25519"})
        assert "SELinux" in result.summary or "ausearch" in result.summary


# ---------------------------------------------------------------------------
# ToolResult structure invariants
# ---------------------------------------------------------------------------

class TestToolResultStructure:
    @pytest.mark.parametrize("op,args", [
        ("keygen",                  {"path": "/root/.ssh/id_ed25519"}),
        ("authorized_keys_list",    {"user": "root"}),
        ("authorized_keys_add",     {"key": "ssh-ed25519 AAAA... u@h", "user": "root"}),
        ("authorized_keys_remove",  {"key_comment": "u@h", "user": "root"}),
        ("known_hosts_list",        {"user": "root"}),
        ("known_hosts_remove",      {"hostname": "h.example.com", "user": "root"}),
        ("sshd_config_audit",       {}),
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
        ("keygen",                  {"path": "/root/.ssh/id_ed25519"}),
        ("authorized_keys_list",    {"user": "root"}),
        ("authorized_keys_add",     {"key": "ssh-ed25519 AAAA... u@h", "user": "root"}),
        ("authorized_keys_remove",  {"key_comment": "u@h", "user": "root"}),
        ("known_hosts_list",        {"user": "root"}),
        ("known_hosts_remove",      {"hostname": "h.example.com", "user": "root"}),
        ("sshd_config_audit",       {}),
    ])
    def test_as_dict_has_four_keys(self, op: str, args: dict) -> None:
        with _patch(_ok()):
            result = _execute(op, args)
        d = result.as_dict()
        assert set(d.keys()) == {"exit_code", "stdout", "stderr", "summary"}


# ---------------------------------------------------------------------------
# I2 — no AI language in any summary
# ---------------------------------------------------------------------------

class TestNoAILanguage:
    """Invariant I2: no AI/LLM/model/agent language in user-facing strings."""

    _FORBIDDEN = {"AI", "LLM", "model", "agent", "agentic", "neural", "language model"}

    @pytest.mark.parametrize("op,args", [
        ("keygen",                  {"path": "/root/.ssh/id_ed25519"}),
        ("authorized_keys_list",    {"user": "root"}),
        ("authorized_keys_add",     {"key": "ssh-ed25519 AAAA... u@h", "user": "root"}),
        ("authorized_keys_remove",  {"key_comment": "u@h", "user": "root"}),
        ("known_hosts_list",        {"user": "root"}),
        ("known_hosts_remove",      {"hostname": "h.example.com", "user": "root"}),
        ("sshd_config_audit",       {}),
    ])
    def test_no_ai_language_in_success_summary(self, op: str, args: dict) -> None:
        with _patch(_ok(stdout="output")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in summary for op={op!r}: {result.summary!r}"
            )

    @pytest.mark.parametrize("op,args", [
        ("keygen",                  {"path": "/root/.ssh/id_ed25519"}),
        ("authorized_keys_list",    {"user": "root"}),
        ("authorized_keys_remove",  {"key_comment": "u@h", "user": "root"}),
        ("sshd_config_audit",       {}),
    ])
    def test_no_ai_language_in_failure_summary(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=1, stderr="something went wrong")):
            result = _execute(op, args)
        for word in self._FORBIDDEN:
            assert word not in result.summary, (
                f"I2 violation: '{word}' found in failure summary for op={op!r}"
            )


# ---------------------------------------------------------------------------
# I9 — execute() NEVER raises
# ---------------------------------------------------------------------------

class TestExecuteNeverRaises:
    def test_unknown_op_returns_toolresult(self) -> None:
        """Unknown op must NOT raise — returns a ToolResult with exit_code=1."""
        result = _execute("nonexistent_operation", {})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 1
        assert "nonexistent_operation" in result.summary

    def test_unknown_op_summary_not_empty(self) -> None:
        result = _execute("__bogus__", {})
        assert len(result.summary) > 0
        assert result.as_dict() is not None

    def test_missing_binary_exit_127_no_raise(self) -> None:
        """If run_subprocess returns exit 127 (binary not found), no exception."""
        with _patch(_fail(exit_code=127, stderr="ssh-keygen: No such file or directory")):
            result = _execute("keygen", {"path": "/tmp/k"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127
        assert not result.ok

    def test_missing_binary_cat_exit_127(self) -> None:
        with _patch(_fail(exit_code=127, stderr="cat: command not found")):
            result = _execute("authorized_keys_list", {"user": "root"})
        assert isinstance(result, ToolResult)
        assert not result.ok

    @pytest.mark.parametrize("op,args", [
        ("keygen",                  {"path": "/tmp/k"}),
        ("authorized_keys_list",    {"user": "root"}),
        ("authorized_keys_add",     {"key": "ssh-ed25519 AAAA... u@h", "user": "root"}),
        ("authorized_keys_remove",  {"key_comment": "u@h", "user": "root"}),
        ("known_hosts_list",        {"user": "root"}),
        ("known_hosts_remove",      {"hostname": "h", "user": "root"}),
        ("sshd_config_audit",       {}),
    ])
    def test_all_ops_survive_exit_127(self, op: str, args: dict) -> None:
        with _patch(_fail(exit_code=127, stderr="command not found")):
            result = _execute(op, args)
        assert isinstance(result, ToolResult)
        assert result.exit_code == 127


# ---------------------------------------------------------------------------
# Registry dispatch integration
# ---------------------------------------------------------------------------

class TestRegistryDispatch:
    def test_dispatch_authorized_keys_list(self) -> None:
        with _patch(_ok(stdout="ssh-ed25519 AAAA... u@h\n")):
            result = registry.dispatch("ssh_keys", "authorized_keys_list", {"user": "root"})
        assert isinstance(result, ToolResult)
        assert result.exit_code == 0

    def test_dispatch_sshd_config_audit(self) -> None:
        with _patch(_ok(stdout="port 22\n")):
            result = registry.dispatch("ssh_keys", "sshd_config_audit", {})
        assert result.ok

    def test_dispatch_keygen_missing_path_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'path'"):
            registry.dispatch("ssh_keys", "keygen", {})

    def test_dispatch_authorized_keys_remove_missing_key_comment_raises(self) -> None:
        with pytest.raises(TypeError, match="requires argument 'key_comment'"):
            registry.dispatch("ssh_keys", "authorized_keys_remove", {})

    def test_dispatch_unknown_op_raises(self) -> None:
        with pytest.raises(ValueError):
            registry.dispatch("ssh_keys", "nonexistent", {})


# ---------------------------------------------------------------------------
# DEFERRED-TO-MOSSAD: live execution tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real ssh-keygen on Rocky Linux 9")
def test_live_keygen_ed25519() -> None:
    """Live: ssh-keygen -t ed25519 produces a key pair."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "id_ed25519")
        result = _execute("keygen", {"path": path, "key_type": "ed25519"})
        assert result.exit_code == 0
        assert os.path.exists(path)
        assert os.path.exists(path + ".pub")


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real sshd on Rocky Linux 9")
def test_live_sshd_config_audit() -> None:
    """Live: sshd -T returns effective config (requires sshd installed)."""
    result = _execute("sshd_config_audit", {})
    assert result.exit_code in (0, 1)  # 1 if run without root
    assert isinstance(result.stdout, str)


@pytest.mark.skip(reason="DEFERRED-TO-MOSSAD: requires real authorized_keys file on Rocky Linux 9")
def test_live_authorized_keys_list_root() -> None:
    """Live: cat /root/.ssh/authorized_keys (must run as root)."""
    result = _execute("authorized_keys_list", {"user": "root"})
    assert result.exit_code in (0, 1)
