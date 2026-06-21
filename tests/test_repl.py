"""Tests for core/agent/repl.py — the integration spine.

Drives the full loop with a SCRIPTED responder (no model), a fake IO (no
terminal), and a real on-disk AuditLog (tmp_path). Asserts the wiring:
router -> permission gate -> dispatch -> audit -> tool-result feedback ->
English termination. No network, no live Linux, no model.

Coverage:
  * A read call clears the gate immediately and dispatches (I8), audited (I4).
  * A write call is gated: declined -> not dispatched, refused recorded (I3/I4);
    confirmed -> dispatched.
  * A destructive call needs the typed word; wrong word -> refused.
  * Non-interactive write -> REFUSED, never auto-run (I3).
  * A MISS turn re-asks (verbatim 0002 §5) and is audited, never crashes.
  * The loop terminates on an English answer.
  * synthesize_command maps calls onto the hardened permissions classifier.
  * Every op (read, refused, miss) produces an audit record (I4).
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


# --------------------------------------------------------------------------- #
# Test doubles                                                                  #
# --------------------------------------------------------------------------- #

class FakeContext:
    """Minimal TurnContext: a fixed snapshot string + invalidation counter."""

    def __init__(self, text: str = "Host: testbox") -> None:
        self.text = text
        self.invalidations = 0

    def snapshot_text(self, *, force: bool = False) -> str:
        return self.text

    def invalidate(self) -> None:
        self.invalidations += 1


class FakeIO:
    """Scripted IO: confirm/typed answers are pre-set; rendered text captured."""

    def __init__(self, *, confirm: bool = True, typed_ok: bool = True) -> None:
        self._confirm = confirm
        self._typed_ok = typed_ok
        self.rendered: list[str] = []

    def render(self, text: str) -> None:
        self.rendered.append(text)

    def confirm(self, prompt: str) -> bool:
        return self._confirm

    def confirm_typed(self, prompt: str, word: str) -> bool:
        return self._typed_ok


class ScriptedResponder:
    """Returns a pre-scripted sequence of (content, tool_calls) per call."""

    def __init__(self, script: list[tuple[str, list[dict]]]) -> None:
        self._script = list(script)
        self._i = 0

    def __call__(self, messages, tools):
        if self._i >= len(self._script):
            content, calls = "", []
        else:
            content, calls = self._script[self._i]
            self._i += 1

        class _R:
            pass

        r = _R()
        r.content = content
        r.tool_calls = calls
        return r


def _stub_tool_results(monkeypatch):
    """Make every registry.dispatch return a clean success without shelling out."""
    def fake_dispatch(tool, op, args):
        return ToolResult(exit_code=0, stdout="ok", stderr="", summary=f"{tool} {op} ok")

    monkeypatch.setattr(registry, "dispatch", fake_dispatch)


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


# --------------------------------------------------------------------------- #
# synthesize_command -> hardened classifier                                    #
# --------------------------------------------------------------------------- #

def test_synthesize_command_maps_classes():
    from core.agent import permissions as perm

    read = ParsedCall("c", "services", "status", {"unit": "sshd.service"}, OpClass.READ)
    assert perm.classify(synthesize_command(read)).op_class is OpClass.READ

    write = ParsedCall("c", "services", "restart", {"unit": "nginx.service"}, OpClass.WRITE)
    assert perm.classify(synthesize_command(write)).op_class is OpClass.WRITE

    destructive = ParsedCall("c", "packages", "remove", {"packages": ["kernel"]}, OpClass.DESTRUCTIVE)
    assert perm.classify(synthesize_command(destructive)).op_class is OpClass.DESTRUCTIVE


# --------------------------------------------------------------------------- #
# Read path (instant, no confirm)                                              #
# --------------------------------------------------------------------------- #

def test_read_call_dispatches_and_audits(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "status", "unit": "sshd.service"})}]),
        ("sshd is running.", []),  # English answer terminates the turn
    ])
    repl, audit = _make_repl(tmp_path, responder, FakeIO())
    outcome = repl.run_turn("is sshd running?")
    audit.close()

    assert outcome.tool_calls_made == 1
    assert outcome.refused == 0
    assert outcome.ended_in_english is True
    assert outcome.final_text == "sshd is running."

    records = list(iter_records(tmp_path / "audit.jsonl"))
    assert len(records) == 1
    assert records[0]["tool"] == "services"
    assert records[0]["permission_decision"] == "allow"
    assert records[0]["tier"] == "test-tier"


# --------------------------------------------------------------------------- #
# Write path (gated)                                                           #
# --------------------------------------------------------------------------- #

def test_write_confirmed_dispatches(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "restart", "unit": "nginx.service"})}]),
        ("nginx restarted.", []),
    ])
    repl, audit = _make_repl(tmp_path, responder, FakeIO(confirm=True))
    outcome = repl.run_turn("restart nginx")
    audit.close()

    assert outcome.tool_calls_made == 1
    assert outcome.refused == 0
    rec = list(iter_records(tmp_path / "audit.jsonl"))[0]
    assert rec["permission_decision"] == "confirm"


def test_write_declined_not_dispatched_but_audited(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "restart", "unit": "nginx.service"})}]),
        ("Okay, leaving nginx as is.", []),
    ])
    repl, audit = _make_repl(tmp_path, responder, FakeIO(confirm=False))
    outcome = repl.run_turn("restart nginx")
    audit.close()

    assert outcome.tool_calls_made == 0
    assert outcome.refused == 1
    rec = list(iter_records(tmp_path / "audit.jsonl"))[0]
    assert rec["exit_code"] == 2  # skipped-by-gate code
    assert "confirm" in rec["permission_decision"]


# --------------------------------------------------------------------------- #
# Destructive path (typed word)                                               #
# --------------------------------------------------------------------------- #

def test_destructive_wrong_word_refused(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "packages",
               "arguments": json.dumps({"operation": "remove", "packages": ["kernel"]})}]),
        ("Not removing the kernel.", []),
    ])
    repl, audit = _make_repl(tmp_path, responder, FakeIO(typed_ok=False))
    outcome = repl.run_turn("remove the kernel package")
    audit.close()

    assert outcome.tool_calls_made == 0
    assert outcome.refused == 1
    rec = list(iter_records(tmp_path / "audit.jsonl"))[0]
    assert "confirm_typed" in rec["permission_decision"]


def test_destructive_typed_word_dispatches(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "packages",
               "arguments": json.dumps({"operation": "remove", "packages": ["kernel"]})}]),
        ("Kernel removed.", []),
    ])
    repl, audit = _make_repl(tmp_path, responder, FakeIO(typed_ok=True))
    outcome = repl.run_turn("remove the kernel package")
    audit.close()
    assert outcome.tool_calls_made == 1


# --------------------------------------------------------------------------- #
# Non-interactive: writes/destructives REFUSED (I3)                            #
# --------------------------------------------------------------------------- #

def test_non_interactive_write_is_refused(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "restart", "unit": "nginx.service"})}]),
        ("done", []),
    ])
    repl, audit = _make_repl(tmp_path, responder, FakeIO(confirm=True), interactive=False)
    outcome = repl.run_turn("restart nginx")
    audit.close()
    # Even though IO would say yes, a non-interactive write is REFUSED at the gate.
    assert outcome.tool_calls_made == 0
    assert outcome.refused == 1


# --------------------------------------------------------------------------- #
# MISS path: re-ask, audited, never crash                                     #
# --------------------------------------------------------------------------- #

def test_miss_turn_reasks_and_audits(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services", "arguments": "{broken json"}]),
        ("", [{"id": "c2", "name": "services",
               "arguments": json.dumps({"operation": "status", "unit": "sshd.service"})}]),
        ("sshd is running.", []),
    ])
    repl, audit = _make_repl(tmp_path, responder, FakeIO())
    outcome = repl.run_turn("is sshd running?")
    audit.close()

    assert outcome.misses == 1
    assert outcome.tool_calls_made == 1  # recovered on the re-ask
    assert outcome.ended_in_english is True
    # The miss + the successful read are both audited (I4).
    records = list(iter_records(tmp_path / "audit.jsonl"))
    assert any(r["result"] and r["result"].startswith("miss:") for r in records)


def test_invalidate_on_successful_write(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    ctx = FakeContext()
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "restart", "unit": "nginx.service"})}]),
        ("done", []),
    ])
    audit = AuditLog(str(tmp_path / "audit.jsonl"))
    repl = Repl(registry=registry, responder=responder, audit=audit,
                context=ctx, io=FakeIO(confirm=True), tier_label="t")
    repl.run_turn("restart nginx")
    audit.close()
    # A successful mutation invalidates the context so the next turn sees reality.
    assert ctx.invalidations == 1


def test_round_cap_prevents_infinite_loop(tmp_path, monkeypatch):
    _stub_tool_results(monkeypatch)
    # A responder that ALWAYS calls a tool, never answers in English.
    forever = [("", [{"id": "c", "name": "services",
                      "arguments": json.dumps({"operation": "status", "unit": "x"})}])] * 50
    repl, audit = _make_repl(tmp_path, ScriptedResponder(forever), FakeIO())
    repl._max_rounds = 4
    outcome = repl.run_turn("loop")
    audit.close()
    assert outcome.rounds == 4  # capped, did not spin forever
