import json
from core.agent import nocallguard as g
from core.tools import registry, ToolResult
import core.tools.services  # noqa: F401
from core.agent.audit import AuditLog
from core.agent.repl import Repl
from tests.test_repl import FakeContext, FakeIO, ScriptedResponder


def test_detects_fabricated_results():
    assert g.looks_like_result("crond.service started; active (running); PID 1420")
    assert g.looks_like_result("haproxy.service: failed since Thu 2026-07-07 14:32:05 UTC")
    assert not g.looks_like_result("The nofail option lets boot continue if the device is missing.")


def test_plain_questions_pass():
    assert not g.should_block("what does nofail do in fstab", "It lets boot continue when the device is absent.", 0)


def test_action_without_call_is_blocked():
    assert g.should_block("ok, get it running again", "Sure, it is fine now.", 0)
    assert not g.should_block("restart nginx", "nginx restarted", 1)


def _repl(tmp_path, script):
    return Repl(registry=registry, responder=ScriptedResponder(script), audit=AuditLog(str(tmp_path / "a.jsonl")),
                context=FakeContext(), io=FakeIO(confirm=True), tier_label="t", interactive=True)


def test_repl_reasks_then_executes(tmp_path, monkeypatch):
    ran = []
    monkeypatch.setattr(registry, "dispatch", lambda t, o, a: (ran.append((t, o)), ToolResult(0, "ok", "", "ok"))[1])
    repl = _repl(tmp_path, [
        ("crond.service started; active (running); PID 1420", []),
        ("", [{"id": "c1", "name": "services", "arguments": json.dumps({"operation": "start", "unit": "crond.service"})}]),
        ("crond.service is running.", []),
    ])
    out = repl.run_turn("ok, get it running again")
    assert ran == [("services", "start")]
    assert "PID 1420" not in (out.final_text or "")


def test_repl_never_shows_fabrication(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "dispatch", lambda t, o, a: ToolResult(0, "ok", "", "ok"))
    repl = _repl(tmp_path, [("nginx restarted; PID 99", []), ("nginx restarted; PID 99", [])])
    out = repl.run_turn("restart nginx")
    assert out.final_text == g.NOTHING_RAN_TEXT and out.tool_calls_made == 0
