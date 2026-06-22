"""Phase-0 invariance baseline — FROZEN "before" oracle for the streaming build.

These tests pin the EXACT gate/audit/render/outcome values for five canonical
turns through Repl.run_turn() with the EXISTING buffered ScriptedResponder +
FakeIO doubles (imported from this module; the doubles live here per-spec so
P6 can import-and-run them against the streaming path without modification).

Any later phase that perturbs:
  - audit record count or permission_decision strings (SC4 / I3 / I4)
  - FakeIO.rendered content for the English answers (render() is called with
    the final English text — tool-step lines added in P3 go through NEW hooks,
    not render(), so those won't break this test)
  - TurnOutcome fields (tool_calls_made, refused, misses, rounds,
    ended_in_english)

...will break one of the explicit assertions below LOUDLY, making the
regression easy to pinpoint.

REUSE CONTRACT (P6): import ScriptedResponder, FakeIO, FakeContext,
_stub_tool_results, and _make_repl directly from here; run the five
scenario-level helpers against the streaming path unchanged.  If any helper
fails the assertion it means the streaming path perturbed gate/audit behavior.

DEFERRED: live 7B/14B Ollama round-trip FEEL -> DEFERRED-TO-MOSSAD (needs a
provisioned box + Ollama running a real model; not available on this dev host).
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
# Test doubles (importable by P6)                                              #
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
# Scenario 1 — READ (instant, no confirmation)                                 #
#                                                                               #
# FROZEN baseline numbers:                                                      #
#   audit_count = 1                                                             #
#   permission_decisions = ["allow"]                                            #
#   tool_calls_made = 1, refused = 0, misses = 0, rounds = 2                   #
#   ended_in_english = True                                                     #
#   rendered (English answer) = ["sshd is running."]                           #
# --------------------------------------------------------------------------- #

def test_baseline_read(tmp_path, monkeypatch):
    """READ: dispatches immediately, exactly 1 audit record with 'allow'."""
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "status", "unit": "sshd.service"})}]),
        ("sshd is running.", []),
    ])
    io = FakeIO()
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("is sshd running?")
    audit.close()

    records = list(iter_records(tmp_path / "audit.jsonl"))

    # --- FROZEN audit oracle ---
    assert len(records) == 1, f"expected 1 audit record, got {len(records)}"
    assert records[0]["permission_decision"] == "allow"
    assert records[0]["tool"] == "services"
    assert records[0]["tier"] == "test-tier"

    # --- FROZEN outcome oracle ---
    assert outcome.tool_calls_made == 1
    assert outcome.refused == 0
    assert outcome.misses == 0
    assert outcome.rounds == 2
    assert outcome.ended_in_english is True

    # --- FROZEN render oracle (English answer only) ---
    assert io.rendered == ["sshd is running."]


# --------------------------------------------------------------------------- #
# Scenario 2 — CONFIRMED WRITE                                                  #
#                                                                               #
# FROZEN baseline numbers:                                                      #
#   audit_count = 1                                                             #
#   permission_decisions = ["confirm"]                                          #
#   tool_calls_made = 1, refused = 0, misses = 0, rounds = 2                   #
#   ended_in_english = True                                                     #
#   rendered (English answer) = ["nginx restarted."]                           #
# --------------------------------------------------------------------------- #

def test_baseline_write_confirmed(tmp_path, monkeypatch):
    """CONFIRMED WRITE: gate clears on yes, exactly 1 audit record with 'confirm'."""
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "restart", "unit": "nginx.service"})}]),
        ("nginx restarted.", []),
    ])
    io = FakeIO(confirm=True)
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    records = list(iter_records(tmp_path / "audit.jsonl"))

    # --- FROZEN audit oracle ---
    assert len(records) == 1, f"expected 1 audit record, got {len(records)}"
    assert records[0]["permission_decision"] == "confirm"

    # --- FROZEN outcome oracle ---
    assert outcome.tool_calls_made == 1
    assert outcome.refused == 0
    assert outcome.misses == 0
    assert outcome.rounds == 2
    assert outcome.ended_in_english is True

    # --- FROZEN render oracle (English answer only) ---
    assert io.rendered == ["nginx restarted."]


# --------------------------------------------------------------------------- #
# Scenario 3 — DECLINED WRITE                                                   #
#                                                                               #
# FROZEN baseline numbers:                                                      #
#   audit_count = 1                                                             #
#   permission_decisions = ["confirm:declined"]                                 #
#   exit_code = 2  (gate-skipped convention)                                    #
#   tool_calls_made = 0, refused = 1, misses = 0, rounds = 2                   #
#   ended_in_english = True                                                     #
#   rendered (English answer) = ["Okay, leaving nginx as is."]                 #
# --------------------------------------------------------------------------- #

def test_baseline_write_declined(tmp_path, monkeypatch):
    """DECLINED WRITE: gate blocks, 1 audit record 'confirm:declined', exit_code=2."""
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services",
               "arguments": json.dumps({"operation": "restart", "unit": "nginx.service"})}]),
        ("Okay, leaving nginx as is.", []),
    ])
    io = FakeIO(confirm=False)
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("restart nginx")
    audit.close()

    records = list(iter_records(tmp_path / "audit.jsonl"))

    # --- FROZEN audit oracle ---
    assert len(records) == 1, f"expected 1 audit record, got {len(records)}"
    assert records[0]["permission_decision"] == "confirm:declined"
    assert records[0]["exit_code"] == 2

    # --- FROZEN outcome oracle ---
    assert outcome.tool_calls_made == 0
    assert outcome.refused == 1
    assert outcome.misses == 0
    assert outcome.rounds == 2
    assert outcome.ended_in_english is True

    # --- FROZEN render oracle (English answer only) ---
    assert io.rendered == ["Okay, leaving nginx as is."]


# --------------------------------------------------------------------------- #
# Scenario 4 — DESTRUCTIVE WRONG WORD                                           #
#                                                                               #
# FROZEN baseline numbers:                                                      #
#   audit_count = 1                                                             #
#   permission_decisions = ["confirm_typed:declined"]                           #
#   exit_code = 2                                                               #
#   tool_calls_made = 0, refused = 1, misses = 0, rounds = 2                   #
#   ended_in_english = True                                                     #
#   rendered (English answer) = ["Not removing the kernel."]                   #
# --------------------------------------------------------------------------- #

def test_baseline_destructive_wrong_word(tmp_path, monkeypatch):
    """DESTRUCTIVE + wrong typed word: 1 audit record 'confirm_typed:declined', exit_code=2."""
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "packages",
               "arguments": json.dumps({"operation": "remove", "packages": ["kernel"]})}]),
        ("Not removing the kernel.", []),
    ])
    io = FakeIO(typed_ok=False)
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("remove the kernel package")
    audit.close()

    records = list(iter_records(tmp_path / "audit.jsonl"))

    # --- FROZEN audit oracle ---
    assert len(records) == 1, f"expected 1 audit record, got {len(records)}"
    assert records[0]["permission_decision"] == "confirm_typed:declined"
    assert records[0]["exit_code"] == 2

    # --- FROZEN outcome oracle ---
    assert outcome.tool_calls_made == 0
    assert outcome.refused == 1
    assert outcome.misses == 0
    assert outcome.rounds == 2
    assert outcome.ended_in_english is True

    # --- FROZEN render oracle (English answer only) ---
    assert io.rendered == ["Not removing the kernel."]


# --------------------------------------------------------------------------- #
# Scenario 5 — MISS + RE-ASK                                                    #
#                                                                               #
# FROZEN baseline numbers:                                                      #
#   audit_count = 2  (1 miss record + 1 read dispatch record)                  #
#   permission_decisions = ["n/a", "allow"]                                    #
#   results[0] starts with "miss:"                                              #
#   tool_calls_made = 1, refused = 0, misses = 1, rounds = 3                   #
#   ended_in_english = True                                                     #
#   rendered (English answer) = ["sshd is running."]                           #
# --------------------------------------------------------------------------- #

def test_baseline_miss_reask(tmp_path, monkeypatch):
    """MISS + re-ask: 2 audit records (miss then read), recovered on re-ask."""
    _stub_tool_results(monkeypatch)
    responder = ScriptedResponder([
        ("", [{"id": "c1", "name": "services", "arguments": "{broken json"}]),
        ("", [{"id": "c2", "name": "services",
               "arguments": json.dumps({"operation": "status", "unit": "sshd.service"})}]),
        ("sshd is running.", []),
    ])
    io = FakeIO()
    repl, audit = _make_repl(tmp_path, responder, io)
    outcome = repl.run_turn("is sshd running?")
    audit.close()

    records = list(iter_records(tmp_path / "audit.jsonl"))

    # --- FROZEN audit oracle ---
    assert len(records) == 2, f"expected 2 audit records, got {len(records)}"
    assert records[0]["permission_decision"] == "n/a"
    assert records[0]["result"].startswith("miss:")
    assert records[1]["permission_decision"] == "allow"

    # --- FROZEN outcome oracle ---
    assert outcome.tool_calls_made == 1
    assert outcome.refused == 0
    assert outcome.misses == 1
    assert outcome.rounds == 3
    assert outcome.ended_in_english is True

    # --- FROZEN render oracle (English answer only) ---
    assert io.rendered == ["sshd is running."]
