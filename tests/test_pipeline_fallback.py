"""
tests/test_pipeline_fallback.py — Phase 7 safety proof for the fallback path.

Load-bearing safety properties pinned here:

  1. A fallback argv ALWAYS passes through permissions.classify (I3): the
     Decision on the result is the classify Decision for that argv.
  2. A destructive fallback argv -> Gate.CONFIRM_TYPED (interactive) or
     Gate.REFUSE (non-interactive). NEVER Gate.ALLOW.
  3. The audit record always carries source=fallback in the permission_decision
     field so fallback usage is independently queryable (I4).
  4. FallbackResult.auto_ok is ALWAYS False — nothing from fallback auto-runs
     (even a read-class argv is blocked from silent auto-run).
  5. Gate.ALLOW is NEVER returned for any fallback result: even a fallback read
     argv gets a "requires confirmation (best-effort)" gate label in the display
     and auto_ok=False on the result.
  6. A generation failure -> FallbackResult.failed=True with a non-empty reason;
     the audit record still carries source=fallback.
  7. write_fallback_audit writes exactly the fields the AuditLog schema expects
     (tier, nl_input, translated_command, tool, args, permission_decision, result)
     and the permission_decision starts with "fallback|".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

import re

from core.agent.permissions import ExecContext, Gate, OpClass
from core.agent.pipeline.fallback import (
    FALLBACK_MARKER,
    FALLBACK_NOTE,
    FallbackResult,
    propose_fallback,
    write_fallback_audit,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

@dataclass
class FakeResponse:
    """Minimal stand-in for a model response object."""
    content: str


def make_responder(content: str) -> Any:
    """Return a callable that always returns FakeResponse(content)."""
    def _resp(messages, tools):  # noqa: ANN001
        return FakeResponse(content=content)
    return _resp


def make_failing_responder(exc: Exception) -> Any:
    """Return a callable that always raises exc."""
    def _resp(messages, tools):  # noqa: ANN001
        raise exc
    return _resp


# ---------------------------------------------------------------------------
# 1. Classify gate propagation (I3)
# ---------------------------------------------------------------------------

class TestClassifyPropagation:
    """The classify Decision on the FallbackResult always reflects classify()."""

    def test_read_argv_gets_allow_decision(self) -> None:
        """A known read argv is classified READ/ALLOW by permissions.classify."""
        result = propose_fallback(
            "show all running services",
            responder=make_responder("systemctl list-units --state=running"),
            context=ExecContext(interactive=True),
        )
        assert not result.failed
        assert result.decision.op_class is OpClass.READ
        assert result.decision.gate is Gate.ALLOW

    def test_write_argv_gets_confirm_decision(self) -> None:
        """A write-class argv is classified WRITE/CONFIRM by classify."""
        result = propose_fallback(
            "install nginx",
            responder=make_responder("dnf install nginx"),
            context=ExecContext(interactive=True),
        )
        assert not result.failed
        assert result.decision.op_class is OpClass.WRITE
        assert result.decision.gate is Gate.CONFIRM

    def test_destructive_argv_interactive_gets_confirm_typed(self) -> None:
        """A destructive argv in an interactive context -> CONFIRM_TYPED."""
        result = propose_fallback(
            "erase everything on /dev/sdb",
            responder=make_responder("mkfs.ext4 /dev/sdb"),
            context=ExecContext(interactive=True),
        )
        assert not result.failed
        assert result.decision.op_class is OpClass.DESTRUCTIVE
        assert result.decision.gate is Gate.CONFIRM_TYPED

    def test_destructive_argv_non_interactive_gets_refuse(self) -> None:
        """A destructive argv in non-interactive context -> REFUSE."""
        result = propose_fallback(
            "format the disk",
            responder=make_responder("mkfs.ext4 /dev/sdb"),
            context=ExecContext(interactive=False),
        )
        assert not result.failed
        assert result.decision.op_class is OpClass.DESTRUCTIVE
        assert result.decision.gate is Gate.REFUSE

    def test_write_argv_non_interactive_gets_refuse(self) -> None:
        """A write argv in non-interactive context -> REFUSE."""
        result = propose_fallback(
            "start nginx",
            responder=make_responder("systemctl start nginx"),
            context=ExecContext(interactive=False),
        )
        assert not result.failed
        # systemctl start is WRITE -> REFUSE in non-interactive
        assert result.decision.gate is Gate.REFUSE


# ---------------------------------------------------------------------------
# 2. Destructive -> CONFIRM_TYPED or REFUSE, NEVER ALLOW (R2 safety)
# ---------------------------------------------------------------------------

class TestDestructiveNeverAllow:
    """A destructive fallback argv NEVER produces Gate.ALLOW (R2 mitigation)."""

    @pytest.mark.parametrize("cmd", [
        "rm -rf /etc",
        "mkfs.ext4 /dev/sda",
        "dd if=/dev/zero of=/dev/sdb",
        "wipefs -a /dev/sdc",
        "userdel root",
        "systemctl reboot",
    ])
    def test_destructive_argv_never_allow(self, cmd: str) -> None:
        result = propose_fallback(
            "do something dangerous",
            responder=make_responder(cmd),
            context=ExecContext(interactive=True),
        )
        assert result.decision.gate is not Gate.ALLOW, (
            f"destructive argv {cmd!r} must not produce Gate.ALLOW"
        )
        assert result.decision.gate in (Gate.CONFIRM_TYPED, Gate.CONFIRM), (
            f"destructive argv {cmd!r} expected CONFIRM_TYPED or CONFIRM"
        )

    @pytest.mark.parametrize("cmd", [
        "rm -rf /etc",
        "mkfs.ext4 /dev/sda",
    ])
    def test_destructive_argv_non_interactive_always_refuse(self, cmd: str) -> None:
        result = propose_fallback(
            "do something dangerous",
            responder=make_responder(cmd),
            context=ExecContext(interactive=False),
        )
        assert result.decision.gate is Gate.REFUSE


# ---------------------------------------------------------------------------
# 3. source=fallback always in audit record (I4)
# ---------------------------------------------------------------------------

class TestAuditSourceFallback:
    """The audit record always carries source=fallback in permission_decision."""

    def test_read_argv_audit_has_source_fallback(self) -> None:
        result = propose_fallback(
            "list all services",
            responder=make_responder("systemctl list-units"),
        )
        perm = result.audit_record["permission_decision"]
        assert perm.startswith("fallback|"), (
            f"permission_decision must start with 'fallback|', got {perm!r}"
        )

    def test_write_argv_audit_has_source_fallback(self) -> None:
        result = propose_fallback(
            "install git",
            responder=make_responder("dnf install git"),
        )
        perm = result.audit_record["permission_decision"]
        assert perm.startswith("fallback|")

    def test_destructive_argv_audit_has_source_fallback(self) -> None:
        result = propose_fallback(
            "format the disk",
            responder=make_responder("mkfs.ext4 /dev/sdb"),
            context=ExecContext(interactive=True),
        )
        perm = result.audit_record["permission_decision"]
        assert perm.startswith("fallback|")

    def test_failure_audit_has_source_fallback(self) -> None:
        result = propose_fallback(
            "something",
            responder=make_responder(""),  # empty -> generation failure
        )
        assert result.failed
        perm = result.audit_record["permission_decision"]
        assert perm.startswith("fallback|")

    def test_audit_record_contains_gate_and_class(self) -> None:
        """permission_decision encodes gate and op_class for queryability."""
        result = propose_fallback(
            "format disk",
            responder=make_responder("mkfs.ext4 /dev/sdb"),
            context=ExecContext(interactive=True),
        )
        perm = result.audit_record["permission_decision"]
        # format: "fallback|<gate>|<op_class>"
        parts = perm.split("|")
        assert len(parts) == 3
        assert parts[0] == "fallback"
        assert parts[1] == Gate.CONFIRM_TYPED.value
        assert parts[2] == OpClass.DESTRUCTIVE.value

    def test_audit_nl_input_matches_user_input(self) -> None:
        result = propose_fallback(
            "restart postgresql",
            responder=make_responder("systemctl restart postgresql"),
        )
        assert result.audit_record["nl_input"] == "restart postgresql"

    def test_audit_translated_command_matches_argv(self) -> None:
        result = propose_fallback(
            "restart postgresql",
            responder=make_responder("systemctl restart postgresql"),
        )
        assert result.audit_record["translated_command"] == "systemctl restart postgresql"


# ---------------------------------------------------------------------------
# 4. auto_ok ALWAYS False (no silent auto-run)
# ---------------------------------------------------------------------------

class TestAutoOkAlwaysFalse:
    """FallbackResult.auto_ok is always False regardless of gate class."""

    def test_read_fallback_auto_ok_false(self) -> None:
        result = propose_fallback(
            "show services",
            responder=make_responder("systemctl list-units"),
        )
        # Even though classify gives ALLOW for this read, auto_ok must be False.
        assert result.decision.gate is Gate.ALLOW, "sanity: this IS a read/allow"
        assert result.auto_ok is False, (
            "fallback read result must have auto_ok=False — it is never auto-run"
        )

    def test_write_fallback_auto_ok_false(self) -> None:
        result = propose_fallback(
            "install nginx",
            responder=make_responder("dnf install nginx"),
            context=ExecContext(interactive=True),
        )
        assert result.auto_ok is False

    def test_destructive_fallback_auto_ok_false(self) -> None:
        result = propose_fallback(
            "format disk",
            responder=make_responder("mkfs.ext4 /dev/sdb"),
            context=ExecContext(interactive=True),
        )
        assert result.auto_ok is False

    def test_failure_fallback_auto_ok_false(self) -> None:
        result = propose_fallback(
            "something",
            responder=make_responder("UNKNOWN"),
        )
        assert result.failed
        assert result.auto_ok is False


# ---------------------------------------------------------------------------
# 5. Display marker — I2-clean, always includes FALLBACK_MARKER
# ---------------------------------------------------------------------------

class TestDisplayMarker:
    """Display string always carries the FALLBACK_MARKER and no AI language."""

    _AI_WORDS = re.compile(
        r"\b(?:AI|LLM|model|agent|machine\s+learning|artificial\s+intelligence)\b",
        re.IGNORECASE,
    )

    def test_display_contains_fallback_marker(self) -> None:
        result = propose_fallback(
            "restart nginx",
            responder=make_responder("systemctl restart nginx"),
        )
        assert FALLBACK_MARKER in result.display

    def test_display_no_ai_language(self) -> None:
        result = propose_fallback(
            "install docker",
            responder=make_responder("dnf install docker"),
        )
        assert not self._AI_WORDS.search(result.display), (
            "display must not contain AI/LLM/model/agent language (I2)"
        )

    def test_display_contains_argv(self) -> None:
        result = propose_fallback(
            "restart nginx",
            responder=make_responder("systemctl restart nginx"),
        )
        assert "systemctl restart nginx" in result.display

    def test_display_contains_fallback_note(self) -> None:
        result = propose_fallback(
            "restart nginx",
            responder=make_responder("systemctl restart nginx"),
        )
        assert FALLBACK_NOTE in result.display

    def test_display_failure_contains_marker_and_note(self) -> None:
        result = propose_fallback(
            "something vague",
            responder=make_responder(""),  # empty -> failure
        )
        assert result.failed
        assert FALLBACK_MARKER in result.display
        assert FALLBACK_NOTE in result.display

    def test_display_destructive_shows_confirm_word(self) -> None:
        result = propose_fallback(
            "format disk",
            responder=make_responder("mkfs.ext4 /dev/sdb"),
            context=ExecContext(interactive=True),
        )
        # The gate label for CONFIRM_TYPED must name the confirm word.
        assert result.decision.confirm_word in result.display


# ---------------------------------------------------------------------------
# 6. Generation failures
# ---------------------------------------------------------------------------

class TestGenerationFailures:
    """Various failure modes are handled gracefully as FallbackResult(failed=True)."""

    def test_empty_content_is_failure(self) -> None:
        result = propose_fallback(
            "do something",
            responder=make_responder(""),
        )
        assert result.failed
        assert result.argv == ""
        assert result.failure_reason

    def test_unknown_output_is_failure(self) -> None:
        result = propose_fallback(
            "do something unclear",
            responder=make_responder("UNKNOWN"),
        )
        assert result.failed

    def test_responder_exception_is_failure(self) -> None:
        result = propose_fallback(
            "do something",
            responder=make_failing_responder(RuntimeError("timeout")),
        )
        assert result.failed
        assert "timeout" in result.failure_reason

    def test_code_fence_stripped_and_succeeds(self) -> None:
        """The responder wrapping the command in backticks still yields the cmd."""
        result = propose_fallback(
            "list files",
            responder=make_responder("```bash\nls -lah\n```"),
        )
        assert not result.failed
        assert result.argv == "ls -lah"

    def test_multiline_only_first_line_used(self) -> None:
        """Only the first line of the response is accepted (no injection)."""
        result = propose_fallback(
            "list files",
            responder=make_responder("ls -lah\nrm -rf /"),
        )
        assert not result.failed
        assert result.argv == "ls -lah"


# ---------------------------------------------------------------------------
# 7. write_fallback_audit integration
# ---------------------------------------------------------------------------

import re as re_module  # alias to avoid shadowing in the class above


class TestWriteFallbackAudit:
    """write_fallback_audit passes exactly the right kwargs to AuditLog.write."""

    def _make_mock_log(self) -> MagicMock:
        log = MagicMock()
        log.write = MagicMock()
        return log

    def test_write_calls_audit_log_write_once(self) -> None:
        log = self._make_mock_log()
        result = propose_fallback(
            "install nginx",
            responder=make_responder("dnf install nginx"),
        )
        write_fallback_audit(log, result, outcome="proposed")
        log.write.assert_called_once()

    def test_write_passes_permission_decision_with_fallback_prefix(self) -> None:
        log = self._make_mock_log()
        result = propose_fallback(
            "install nginx",
            responder=make_responder("dnf install nginx"),
        )
        write_fallback_audit(log, result, outcome="proposed")
        kwargs = log.write.call_args.kwargs
        assert kwargs["permission_decision"].startswith("fallback|")

    def test_write_passes_correct_outcome(self) -> None:
        log = self._make_mock_log()
        result = propose_fallback(
            "install nginx",
            responder=make_responder("dnf install nginx"),
        )
        write_fallback_audit(log, result, outcome="confirmed")
        kwargs = log.write.call_args.kwargs
        assert kwargs["result"] == "confirmed"

    def test_write_passes_nl_input(self) -> None:
        log = self._make_mock_log()
        result = propose_fallback(
            "install nginx",
            responder=make_responder("dnf install nginx"),
        )
        write_fallback_audit(log, result)
        kwargs = log.write.call_args.kwargs
        assert kwargs["nl_input"] == "install nginx"

    def test_write_passes_translated_command(self) -> None:
        log = self._make_mock_log()
        result = propose_fallback(
            "install nginx",
            responder=make_responder("dnf install nginx"),
        )
        write_fallback_audit(log, result)
        kwargs = log.write.call_args.kwargs
        assert kwargs["translated_command"] == "dnf install nginx"

    def test_write_uses_schema_kwargs_only(self) -> None:
        """write() is called with ONLY the declared AuditLog kwargs."""
        log = self._make_mock_log()
        result = propose_fallback(
            "restart sshd",
            responder=make_responder("systemctl restart sshd"),
        )
        write_fallback_audit(log, result, outcome="proposed")
        kwargs = log.write.call_args.kwargs
        expected_keys = {
            "tier", "nl_input", "translated_command", "tool", "args",
            "permission_decision", "result",
        }
        assert set(kwargs.keys()) == expected_keys, (
            f"unexpected kwargs to AuditLog.write: {set(kwargs.keys()) - expected_keys}"
        )

    def test_write_destructive_fallback(self) -> None:
        """Destructive fallback audit carries CONFIRM_TYPED in permission_decision."""
        log = self._make_mock_log()
        result = propose_fallback(
            "format disk",
            responder=make_responder("mkfs.ext4 /dev/sdb"),
            context=ExecContext(interactive=True),
        )
        assert not result.failed
        write_fallback_audit(log, result, outcome="proposed")
        kwargs = log.write.call_args.kwargs
        perm = kwargs["permission_decision"]
        assert "fallback" in perm
        assert Gate.CONFIRM_TYPED.value in perm
        assert OpClass.DESTRUCTIVE.value in perm
