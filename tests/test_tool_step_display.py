"""Phase-3 tests — live tool-call display ("running: <cmd>" + status line).

The loop announces a cleared op with io.tool_step("running: <synth cmd>")
BEFORE dispatch and reports the outcome with io.tool_step_result(<status>)
AFTER. Both are PRESENTATION ONLY (SC4): they add ZERO audit records, never
touch the gate, and a "running:" line NEVER appears for an op the gate
refused/declined (I3 honesty).

Coverage:
  SC2  A CONFIRMED-write turn -> a tool_step("running: ...") BEFORE and a
       tool_step_result AFTER; the command in the line matches
       synthesize_command (a NON-trivial render, not a default-deny floor).
  -    A DECLINED-write turn -> NO "running:" line; a "not run" status line.
  SC3/I2  Every captured tool_step / tool_step_result string passes
       prompt._AI_PATTERN (no forbidden AI/LLM/model/agent term).
  SC4  audit-count parity — display added ZERO audit records vs. the P0
       baseline behavior for the same scripted turns.
"""

from __future__ import annotations

import json

import pytest

import core.tools.services  # noqa: F401
import core.tools.packages  # noqa: F401
import core.tools.logs  # noqa: F401
from core.tools import registry, ToolResult
from core.agent.audit import AuditLog, iter_records
from core.agent.repl import Repl, synthesize_command
from core.agent.router import ParsedCall
from core.agent.permissions import OpClass
from core.agent import prompt as _prompt

# Reuse the canonical doubles from the integration spine tests.
from tests.test_repl import (
    FakeContext,
    ScriptedResponder,
    _stub_tool_results,
)


# --------------------------------------------------------------------------- #
# Step-capturing IO double                                                      #
# --------------------------------------------------------------------------- #

class StepIO:
    """FakeIO that ALSO captures tool_step / tool_step_result emissions.

    ``steps`` records the live "running: <cmd>" lines; ``step_results`` records
    the terse status lines. ``events`` records both in arrival order so a test
    can assert "running" came BEFORE the result for the same op.
    """

    def __init__(self, *, confirm: bool = True, typed_ok: bool = True) -> None:
        self._confirm = confirm
        self._typed_ok = typed_ok
        self.rendered: list[str] = []
        self.steps: list[str] = []
        self.step_results: list[str] = []
        self.events: list[tuple[str, str]] = []

    def render(self, text: str) -> None:
        self.rendered.append(text)

    def confirm(self, prompt: str) -> bool:
        return self._confirm

    def confirm_typed(self, prompt: str, word: str) -> bool:
        return self._typed_ok

    def tool_step(self, text: str) -> None:
        self.steps.append(text)
        self.events.append(("step", text))

    def tool_step_result(self, text: str) -> None:
        self.step_results.append(text)
        self.events.append(("result", text))

    # Every captured user-facing string (for the I2 sweep).
    def all_step_strings(self) -> list[str]:
        return list(self.steps) + list(self.step_results)


def _make_repl(tmp_path, responder, io, *, interactive=True):
    audit = AuditLog(str(tmp_path / "audit.jsonl"))
    return Repl(
        registry=registry,
        responder=responder,
        audit=audit,
        context=FakeContext(),
        io=io,
        tier_label="test-tier",
        interactive=interactive,
    ), audit


def _count_records(path) -> int:
    return sum(1 for _ in iter_records(str(path)))


# A NON-trivial write call whose synthesize_command renders a real argv
# ("systemctl restart nginx.service") — not a default-deny floor string.
_RESTART_NGINX = {
    "id": "c1", "name": "services",
    "arguments": json.dumps({"operation": "restart", "unit": "nginx.service"}),
}
# A pure READ ("systemctl status nginx.service") — the plan's non-trivial
# render example; clears the gate instantly (I8), no confirm.
_STATUS_NGINX = {
    "id": "c1", "name": "services",
    "arguments": json.dumps({"operation": "status", "unit": "nginx.service"}),
}


# --------------------------------------------------------------------------- #
# SC2 — confirmed write: running BEFORE, status AFTER, cmd matches synth        #
# --------------------------------------------------------------------------- #

def test_confirmed_write_shows_running_then_result(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [_RESTART_NGINX]),
        ("nginx restarted.", []),  # English answer terminates the turn
    ])
    io = StepIO(confirm=True)
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    # The op actually ran (gate cleared on confirm).
    assert outcome.tool_calls_made == 1
    assert outcome.refused == 0

    # A "running:" line appeared, then a status line — in that order.
    assert len(io.steps) == 1
    assert len(io.step_results) == 1
    assert io.events[0][0] == "step"
    # the result for this op arrives after the running line
    assert io.events.index(("step", io.steps[0])) < \
        io.events.index(("result", io.step_results[0]))

    # The command in the line matches synthesize_command — a non-trivial argv.
    expected = synthesize_command(
        ParsedCall("c1", "services", "restart",
                   {"unit": "nginx.service"}, OpClass.WRITE)
    )
    assert expected == "systemctl restart nginx.service"
    assert io.steps[0] == "running: " + expected
    assert "systemctl restart nginx.service" in io.steps[0]

    # The status line is the terse "done" (exit 0 from the stubbed dispatch).
    assert io.step_results[0] == "done"


def test_read_op_also_shows_running_line(tmp_path, monkeypatch):
    # The plan's non-trivial render example: systemctl status nginx. A read
    # clears the gate instantly (no confirm) and still announces "running:".
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [_STATUS_NGINX]),
        ("nginx is running.", []),
    ])
    io = StepIO()
    repl, audit = _make_repl(tmp_path, responder, io)
    repl.run_turn("is nginx up?")
    audit.close()

    assert io.steps == ["running: systemctl status nginx.service"]
    assert io.step_results == ["done"]


# --------------------------------------------------------------------------- #
# Declined write: NO "running:" line, a "not run" status                        #
# --------------------------------------------------------------------------- #

def test_declined_write_no_running_only_not_run(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [_RESTART_NGINX]),
        ("ok, leaving it.", []),
    ])
    io = StepIO(confirm=False)  # decline the confirm
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    # The op did NOT run.
    assert outcome.tool_calls_made == 0
    assert outcome.refused == 1

    # NO "running:" line for a refused/declined op (I3 honesty).
    assert io.steps == []
    assert all(not s.startswith("running:") for s in io.all_step_strings())

    # A neutral "not run" status line was emitted.
    assert io.step_results == ["not run"]


def test_non_interactive_refused_write_no_running(tmp_path, monkeypatch):
    # A write in non-interactive mode is REFUSED outright (never auto-run, I3).
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [_RESTART_NGINX]),
        ("not done.", []),
    ])
    io = StepIO()
    repl, audit = _make_repl(tmp_path, responder, io, interactive=False)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    assert outcome.refused == 1
    assert io.steps == []
    assert io.step_results == ["not run"]


# --------------------------------------------------------------------------- #
# SC3 / I2 — every captured tool-step string is I2-clean                        #
# --------------------------------------------------------------------------- #

def test_all_step_strings_are_i2_clean(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    # Drive a turn with a cleared op AND a declined op so we capture every
    # category of step string (running, done, not run).
    responder_ok = ScriptedResponder([
        ("", [_STATUS_NGINX]),
        ("up.", []),
    ])
    io_ok = StepIO()
    (tmp_path / "a").mkdir()
    repl_ok, audit_ok = _make_repl(tmp_path / "a", responder_ok, io_ok)
    repl_ok.run_turn("status nginx")
    audit_ok.close()

    responder_no = ScriptedResponder([
        ("", [_RESTART_NGINX]),
        ("left it.", []),
    ])
    io_no = StepIO(confirm=False)
    (tmp_path / "b").mkdir()
    repl_no, audit_no = _make_repl(tmp_path / "b", responder_no, io_no)
    repl_no.run_turn("restart nginx")
    audit_no.close()

    captured = io_ok.all_step_strings() + io_no.all_step_strings()
    assert captured, "expected at least one captured tool-step string"
    for s in captured:
        # _AI_PATTERN matches a forbidden term -> the assertion must NOT match.
        assert _prompt._AI_PATTERN.search(s) is None, \
            f"I2 violation in captured tool-step string: {s!r}"
        # Also route through the prompt module's import-time guard.
        _prompt._assert_no_ai_language(s, label="tool-step")


# --------------------------------------------------------------------------- #
# SC4 — display added ZERO audit records (audit-count parity)                    #
# --------------------------------------------------------------------------- #

def test_display_adds_zero_audit_records_confirmed(tmp_path, monkeypatch):
    # One cleared op -> exactly ONE audit record (the op). The tool-step display
    # writes NOTHING to the audit log.
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [_RESTART_NGINX]),
        ("done.", []),
    ])
    io = StepIO(confirm=True)
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    # Display emitted 2 lines (running + done) but added ZERO audit records.
    assert io.steps and io.step_results
    assert outcome.audit_records == 1
    assert _count_records(tmp_path / "audit.jsonl") == 1


def test_display_adds_zero_audit_records_declined(tmp_path, monkeypatch):
    # One declined op -> exactly ONE audit record (the refused op). The
    # "not run" status line writes NOTHING to the audit log.
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [_RESTART_NGINX]),
        ("ok.", []),
    ])
    io = StepIO(confirm=False)
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    assert io.step_results == ["not run"]
    assert outcome.refused == 1
    assert outcome.audit_records == 1
    assert _count_records(tmp_path / "audit.jsonl") == 1


def test_io_without_step_hooks_still_works(tmp_path, monkeypatch):
    # BACK-COMPAT: an IO that implements ONLY render/confirm/confirm_typed (no
    # tool_step hooks) degrades to a no-op — the turn completes unchanged.
    _stub_tool_results(monkeypatch)

    class BareIO:
        def __init__(self):
            self.rendered = []

        def render(self, text):
            self.rendered.append(text)

        def confirm(self, prompt):
            return True

        def confirm_typed(self, prompt, word):
            return True

    responder = ScriptedResponder([
        ("", [_RESTART_NGINX]),
        ("done.", []),
    ])
    io = BareIO()
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    assert outcome.tool_calls_made == 1
    assert outcome.audit_records == 1
    assert _count_records(tmp_path / "audit.jsonl") == 1
